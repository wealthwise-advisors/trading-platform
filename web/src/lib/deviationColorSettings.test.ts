import { describe, it, expect, beforeEach, vi } from "vitest"
import {
  loadPalettes, savePalettes, resetPalettes, factoryPalettes,
  DEVIATION_COLOR_STORE_KEY, EDITABLE_SLOTS,
} from "./deviationColorSettings"
import { DEFAULT_UPPER_PALETTE, DEFAULT_LOWER_PALETTE } from "./deviationColors"

// jsdom is not configured for these lib tests, so stand up the smallest
// localStorage that behaves like the real one.
function installStorage(initial: Record<string, string> = {}) {
  const store = new Map(Object.entries(initial))
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
    key: (i: number) => [...store.keys()][i] ?? null,
    get length() { return store.size },
  })
  return store
}

beforeEach(() => { installStorage() })

describe("defaults", () => {
  it("returns the factory palettes when nothing is stored", () => {
    const p = loadPalettes()
    expect(p.upper).toEqual(DEFAULT_UPPER_PALETTE.slice(0, EDITABLE_SLOTS))
    expect(p.lower).toEqual(DEFAULT_LOWER_PALETTE.slice(0, EDITABLE_SLOTS))
  })

  it("offers the same number of editable slots on both sides", () => {
    const f = factoryPalettes()
    expect(f.upper).toHaveLength(EDITABLE_SLOTS)
    expect(f.lower).toHaveLength(EDITABLE_SLOTS)
  })
})

describe("persistence", () => {
  it("round-trips a custom choice", () => {
    const p = factoryPalettes()
    p.upper[0] = "#123456"
    p.lower[2] = "#abcdef"
    expect(savePalettes(p)).toBe(true)
    const back = loadPalettes()
    expect(back.upper[0]).toBe("#123456")
    expect(back.lower[2]).toBe("#abcdef")
  })

  it("survives a simulated reload — load reads from storage, not memory", () => {
    const p = factoryPalettes(); p.upper[1] = "#0f0f0f"
    savePalettes(p)
    installStorage(JSON.parse(JSON.stringify({
      [DEVIATION_COLOR_STORE_KEY]: JSON.stringify(p),
    })))
    expect(loadPalettes().upper[1]).toBe("#0f0f0f")
  })

  it("upper and lower persist independently", () => {
    const p = factoryPalettes(); p.upper[0] = "#111111"
    savePalettes(p)
    const back = loadPalettes()
    expect(back.upper[0]).toBe("#111111")
    expect(back.lower).toEqual(DEFAULT_LOWER_PALETTE.slice(0, EDITABLE_SLOTS))
  })
})

describe("reset", () => {
  it("restores factory colours and clears storage", () => {
    const p = factoryPalettes(); p.upper[0] = "#123456"
    savePalettes(p)
    const after = resetPalettes()
    expect(after).toEqual(factoryPalettes())
    expect(localStorage.getItem(DEVIATION_COLOR_STORE_KEY)).toBeNull()
    expect(loadPalettes()).toEqual(factoryPalettes())
  })
})

describe("robustness — bad storage never breaks the table", () => {
  it("corrupt JSON falls back to factory", () => {
    installStorage({ [DEVIATION_COLOR_STORE_KEY]: "{not json" })
    expect(loadPalettes()).toEqual(factoryPalettes())
  })

  it("wrong shape falls back to factory", () => {
    installStorage({ [DEVIATION_COLOR_STORE_KEY]: JSON.stringify({ upper: "nope", lower: 42 }) })
    expect(loadPalettes()).toEqual(factoryPalettes())
  })

  it("non-hex entries are replaced per slot, valid ones kept", () => {
    installStorage({ [DEVIATION_COLOR_STORE_KEY]: JSON.stringify({
      upper: ["#abc", "javascript:alert(1)", "#00ff00"], lower: [],
    }) })
    const p = loadPalettes()
    expect(p.upper[0]).toBe("#abc")
    expect(p.upper[1]).toBe(DEFAULT_UPPER_PALETTE[1])   // rejected
    expect(p.upper[2]).toBe("#00ff00")
  })

  it("a short stored array keeps factory colours for the rest", () => {
    installStorage({ [DEVIATION_COLOR_STORE_KEY]: JSON.stringify({ upper: ["#000000"], lower: [] }) })
    const p = loadPalettes()
    expect(p.upper[0]).toBe("#000000")
    expect(p.upper).toHaveLength(EDITABLE_SLOTS)
    expect(p.upper[7]).toBe(DEFAULT_UPPER_PALETTE[7])
  })

  it("reports failure instead of throwing when storage is unavailable", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => { throw new Error("denied") },
      setItem: () => { throw new Error("denied") },
      removeItem: () => { throw new Error("denied") },
    })
    expect(loadPalettes()).toEqual(factoryPalettes())
    expect(savePalettes(factoryPalettes())).toBe(false)
    expect(() => resetPalettes()).not.toThrow()
  })
})
