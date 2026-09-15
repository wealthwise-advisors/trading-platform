import { afterEach, describe, expect, it, vi } from "vitest"
// ?raw rather than node:fs: the app build type-checks tests with browser types only.
import factoryJson from "../../../tests/fixtures/chart_settings_factory.json?raw"
import {
  DEFAULT_OSCILLATORS, VP_STORE_KEY, buildChartSettings, initialChartSettings,
  loadSavedVpSettings, vpFactorySettings,
} from "./chartExportSettings"
import { api } from "./api"

// The same file api/schemas/chart_settings.py is tested against, so the web and
// the report cannot disagree about the shape or the defaults.
const FIXTURE = JSON.parse(factoryJson)

function withStorage(values: Record<string, string>) {
  vi.stubGlobal("localStorage", { getItem: (k: string) => values[k] ?? null })
}

afterEach(() => vi.unstubAllGlobals())

describe("the settings contract", () => {
  it("factory settings are the shared fixture", () => {
    expect(buildChartSettings(DEFAULT_OSCILLATORS, true, vpFactorySettings())).toEqual(FIXTURE)
  })

  it("with nothing saved, a report exported before the chart mounts gets the factory settings", () => {
    expect(initialChartSettings()).toEqual(FIXTURE)
  })
})

describe("loadSavedVpSettings", () => {
  it("applies a saved default and passes on only the dialog's own fields", () => {
    withStorage({ [VP_STORE_KEY]: JSON.stringify({ bins: 96, show: { poc: false }, somethingOld: 1 }) })
    const loaded = loadSavedVpSettings()!
    expect(loaded.bins).toBe(96)
    // An older default's `show` flags are carried into plots, then dropped.
    expect(loaded.plots.poc.show).toBe(false)
    expect(Object.keys(loaded).sort()).toEqual(Object.keys(vpFactorySettings()).sort())
  })

  it("is what a report exported before the chart mounts is drawn with", () => {
    withStorage({ [VP_STORE_KEY]: JSON.stringify({ opacity: 80 }) })
    expect(initialChartSettings().volumeProfile.opacity).toBe(80)
  })

  it("null for nothing saved or corrupt storage", () => {
    withStorage({})
    expect(loadSavedVpSettings()).toBeNull()
    withStorage({ [VP_STORE_KEY]: "{not json" })
    expect(loadSavedVpSettings()).toBeNull()
  })
})

describe("api.reportUrl", () => {
  it("is unchanged without settings", () => {
    expect(api.reportUrl("abc", "pdf")).toBe("/api/backtests/abc/report?format=pdf")
  })

  it("carries the settings intact", () => {
    const s = buildChartSettings({ rsi2: false, stochrsi: true, rsi13: false, mfi: true }, true, vpFactorySettings())
    s.volumeProfile.plots.poc.color = "#ff8800"
    const url = new URL(api.reportUrl("abc", "html", s), "http://x")
    expect(url.searchParams.get("format")).toBe("html")
    expect(JSON.parse(url.searchParams.get("chart")!)).toEqual(s)
  })
})
