import { afterEach, describe, expect, it, vi } from "vitest"
import {
  ALL_VWAP_LEVELS, DEFAULT_VWAP_LEVELS, VWAP_LEVELS_STORE_KEY, loadVwapLevels, saveVwapLevels,
  toggleVwapLevel, vwapLevelColors,
} from "./vwapLevels"

afterEach(() => vi.unstubAllGlobals())

const store = (values: Record<string, string>) => vi.stubGlobal("localStorage", {
  getItem: (k: string) => values[k] ?? null,
  setItem: (k: string, v: string) => { values[k] = v },
})

describe("vwap levels", () => {
  it("+/-1 and +/-2 are the default", () => expect(DEFAULT_VWAP_LEVELS).toEqual([1, 2]))

  it("offers the same levels as Market Grid", () => {
    expect(ALL_VWAP_LEVELS).toEqual([0.5, 1, 1.5, 2, 2.5, 3, 4, 5])
  })

  it("nothing saved is the default", () => {
    store({})
    expect(loadVwapLevels()).toEqual([1, 2])
  })

  it("round-trips, including nothing selected", () => {
    store({})
    saveVwapLevels([0.5, 2.5])
    expect(loadVwapLevels()).toEqual([0.5, 2.5])
    saveVwapLevels([])
    expect(loadVwapLevels()).toEqual([])
  })

  it.each(["not json", "null", "{}", "7"])("corrupt value %s is the default", (raw) => {
    store({ [VWAP_LEVELS_STORE_KEY]: raw })
    expect(loadVwapLevels()).toEqual([1, 2])
  })

  it("levels the app does not offer are dropped", () => {
    store({ [VWAP_LEVELS_STORE_KEY]: '[1, 99, "x"]' })
    expect(loadVwapLevels()).toEqual([1])
  })

  it("storage that throws is survivable", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => { throw new Error("denied") }, setItem: () => { throw new Error("full") },
    })
    expect(loadVwapLevels()).toEqual([1, 2])
    expect(() => saveVwapLevels([1])).not.toThrow()
  })

  it("toggling adds in order and removes", () => {
    expect(toggleVwapLevel([1, 2], 0.5)).toEqual([0.5, 1, 2])
    expect(toggleVwapLevel([1, 2], 1)).toEqual([2])
  })

  it("+/-1 is sir's cyan; every level has colours", () => {
    expect(vwapLevelColors(1).upper).toBe("#22d3ee")
    expect(vwapLevelColors(4).upper).toBeTruthy()
  })
})
