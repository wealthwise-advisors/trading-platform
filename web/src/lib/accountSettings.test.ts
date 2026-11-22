// @vitest-environment jsdom
/**
 * Settings and chart templates on the server: start-up pull, the first-time import,
 * saving changes back, the "changed on another device" case, and templates.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const server = vi.hoisted(() => ({
  settings: {} as Record<string, unknown>, version: 0, offline: false,
  templates: [] as { name: string; saved_at: string; is_default: boolean; template: Record<string, unknown> }[],
}))

vi.mock("@/lib/api", () => ({
  api: {
    getSettings: async () => {
      if (server.offline) throw new Error("offline")
      return { settings: server.settings, version: server.version, updated_at: null }
    },
    listTemplates: async () => server.templates,
  },
}))

import {
  STUDIES_STORE_KEY, SETTING_STORE_KEYS, applyTemplate, captureTemplate, loadStudies, pullSettings, snapshot,
  startSync, useChartTemplateEpoch, useSettingsNotice,
} from "./accountSettings"

/** The PUT the sync sends: 409 when the version is stale, as the server does. */
function fakePut() {
  return vi.fn(async (_url: string, init: RequestInit) => {
    const body = JSON.parse(String(init.body))
    if (body.version !== server.version) return new Response("{}", { status: 409 })
    server.settings = body.settings
    server.version += 1
    return new Response(JSON.stringify({ settings: body.settings, version: server.version }), { status: 200 })
  })
}

beforeEach(() => {
  localStorage.clear()
  server.settings = {}; server.version = 0; server.templates = []; server.offline = false
  vi.stubGlobal("fetch", fakePut())
  vi.useFakeTimers()
})
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

describe("start-up", () => {
  it("the server's copy replaces this browser's", async () => {
    localStorage.setItem(SETTING_STORE_KEYS.zone, "0")
    server.settings = { zone: "-60", watchlist: '["ES","NQ"]' }; server.version = 4
    await pullSettings()
    expect(localStorage.getItem(SETTING_STORE_KEYS.zone)).toBe("-60")
    expect(localStorage.getItem(SETTING_STORE_KEYS.watchlist)).toBe('["ES","NQ"]')
  })

  it("the first time, this browser's settings become the account's", async () => {
    localStorage.setItem(SETTING_STORE_KEYS.chartStyle, '{"type":"bars"}')
    await pullSettings()
    expect(server.version).toBe(1)
    expect(server.settings).toEqual({ chartStyle: '{"type":"bars"}' })
  })

  it("the default template is put on the chart", async () => {
    server.version = 1
    server.templates = [{ name: "A", saved_at: "", is_default: true, template: { studies: { bb: true } } }]
    await pullSettings()
    expect(loadStudies()).toEqual({ bb: true })
  })

  it("without the server the browser keeps its own settings", async () => {
    server.offline = true
    localStorage.setItem(SETTING_STORE_KEYS.zone, "-60")
    await expect(pullSettings()).resolves.toBeUndefined()
    expect(localStorage.getItem(SETTING_STORE_KEYS.zone)).toBe("-60")
  })
})

describe("never losing a browser's own settings", () => {
  it("a fresh browser with nothing of its own saves nothing", async () => {
    await pullSettings()
    expect(server.version).toBe(0)
  })

  it("a setting only this browser has is kept, and sent up on the next sync", async () => {
    server.version = 1; server.settings = { zone: "-60" }
    localStorage.setItem(SETTING_STORE_KEYS.watchlist, '["ES"]')
    await pullSettings()
    expect(localStorage.getItem(SETTING_STORE_KEYS.watchlist)).toBe('["ES"]')
    const stop = startSync(1000)
    await vi.advanceTimersByTimeAsync(1100)
    stop()
    expect(server.settings).toEqual({ zone: "-60", watchlist: '["ES"]' })
  })

  it("a change made just before a reload is kept and saved, not overwritten by the older server copy", async () => {
    server.version = 1; server.settings = { volumeAvg: '{"on":true}' }
    await pullSettings()                                         // agreed: on
    localStorage.setItem(SETTING_STORE_KEYS.volumeAvg, '{"on":false}')
    await pullSettings()                                         // reload before the sync ran
    expect(localStorage.getItem(SETTING_STORE_KEYS.volumeAvg)).toBe('{"on":false}')
    expect(server.settings).toEqual({ volumeAvg: '{"on":false}' })
  })
})

describe("saving changes back", () => {
  it("a change in browser storage reaches the server", async () => {
    server.version = 1; server.settings = { zone: "0" }
    await pullSettings()
    const stop = startSync(1000)
    localStorage.setItem(SETTING_STORE_KEYS.zone, "-60")
    await vi.advanceTimersByTimeAsync(1100)
    stop()
    expect(server.settings).toEqual({ zone: "-60" })
    expect(server.version).toBe(2)
  })

  it("changed on another device: that copy is loaded, not overwritten, and the app says so", async () => {
    server.version = 1; server.settings = { zone: "0" }
    await pullSettings()
    server.version = 2; server.settings = { zone: "-120" }        // another device saved meanwhile
    const stop = startSync(1000)
    localStorage.setItem(SETTING_STORE_KEYS.zone, "-60")
    await vi.advanceTimersByTimeAsync(1100)
    stop()
    expect(server.settings).toEqual({ zone: "-120" })
    expect(localStorage.getItem(SETTING_STORE_KEYS.zone)).toBe("-120")
    expect(useSettingsNotice.getState().text).toMatch(/another tab or on another device/)
  })

  it("nothing changed, nothing sent", async () => {
    server.version = 1; server.settings = { zone: "0" }
    await pullSettings()
    const put = fakePut(); vi.stubGlobal("fetch", put)
    const stop = startSync(1000)
    await vi.advanceTimersByTimeAsync(3100)
    stop()
    expect(put).not.toHaveBeenCalled()
  })
})

describe("templates", () => {
  it("capture holds the chart settings, the live Volume Profile and the studies", () => {
    localStorage.setItem(SETTING_STORE_KEYS.chartStyle, '{"type":"bars"}')
    localStorage.setItem(SETTING_STORE_KEYS.zone, "-60")                 // not a chart setting
    const t = captureTemplate({ vwap: false }, { bins: 24 })
    expect(t).toEqual({ chartStyle: '{"type":"bars"}', volumeProfile: '{"bins":24}', studies: { vwap: false } })
  })

  it("apply writes the setup and remounts the chart", () => {
    const before = useChartTemplateEpoch.getState().epoch
    applyTemplate({ name: "A", saved_at: "", is_default: false,
                    template: { chartStyle: '{"type":"line"}', studies: { rsi2: false } } })
    expect(localStorage.getItem(SETTING_STORE_KEYS.chartStyle)).toBe('{"type":"line"}')
    expect(JSON.parse(localStorage.getItem(STUDIES_STORE_KEY)!)).toEqual({ rsi2: false })
    expect(useChartTemplateEpoch.getState().epoch).toBe(before + 1)
  })

  it("only settings the app knows are synced", () => {
    localStorage.setItem("something-else", "1")
    localStorage.setItem(SETTING_STORE_KEYS.journal, "{}")
    expect(Object.keys(snapshot())).toEqual(["journal"])
  })
})
