// @vitest-environment jsdom
import { describe as group, expect, it } from "vitest"
import { describe, loadScans, saveScans } from "./scanText"

group("scanner conditions in words", () => {
  it("reads every kind as a sentence", () => {
    expect(describe({ kind: "indicator", name: "rsi2", op: "crosses_below", value: 10 })).toBe("RSI(2) crosses below 10")
    expect(describe({ kind: "change_pct", bars: 12, op: "above", value: 0.5 })).toBe("Price change over 12 bars above 0.5%")
    expect(describe({ kind: "volume_vs_avg", op: "above", value: 2 })).toBe("Volume above 2x its 20-bar average")
    expect(describe({ kind: "breakout", bars: 20, direction: "high" })).toBe("Close breaks the 20-bar high")
    expect(describe({ kind: "vwap", position: "below_lower" })).toBe("Close below the lower VWAP band")
  })
  it("saved scans round-trip, and junk reads as none", () => {
    saveScans([{ name: "A", timeframe: "5m", combine: "all", symbols: ["ES"], conditions: [] }])
    expect(loadScans()[0].name).toBe("A")
    localStorage.setItem("saved-scans", "{bad")
    expect(loadScans()).toEqual([])
  })
})
