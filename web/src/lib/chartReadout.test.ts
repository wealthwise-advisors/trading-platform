import { describe, expect, it } from "vitest"
import {
  formatReadoutDate, formatReadoutNumber, nearestBarIndex, priceLines, readoutLines, seriesByAxis,
  volumeSplitLines, vwapBlock, type ReadoutRow,
} from "./chartReadout"
import type { OHLCVRecord } from "./types"

// thinkorswim, /ES 1m, 2026-11-09 11:33.
const bar: OHLCVRecord = { t: "2026-11-09T11:33:00", o: 7572, h: 7575.75, l: 7572, c: 7575.5, v: 2606 }
const value = (lines: { label: string; value: string }[], label: string) => lines.find((l) => l.label === label)?.value

describe("formatting", () => {
  it.each([
    ["2026-11-09T11:33:00", "11/9/26 11:33 AM"],
    ["2026-11-09T00:05:00", "11/9/26 12:05 AM"],
    ["2026-11-09T12:00:00", "11/9/26 12:00 PM"],
    ["2026-01-02T15:45:00", "1/2/26 3:45 PM"],
    ["not a date", "not a date"],
  ])("%s -> %s", (t, want) => expect(formatReadoutDate(t)).toBe(want))

  it("numbers", () => {
    expect(formatReadoutNumber(2026.25)).toBe("2,026.25")
    expect(formatReadoutNumber(2606, 0)).toBe("2,606")
  })

  it("a missing value reads N/A, as thinkorswim's does", () => {
    expect(formatReadoutNumber(null)).toBe("N/A")
    expect(formatReadoutNumber(NaN)).toBe("N/A")
  })
})

describe("priceLines", () => {
  it("is the candle, with its range", () => {
    const lines = priceLines(bar)
    expect(lines.map((l) => l.label)).toEqual(["Date", "Open", "High", "Low", "Close", "Range"])
    expect(value(lines, "Close")).toBe("7,575.50")
    expect(value(lines, "Range")).toBe("3.75")
  })
})

describe("volumeSplitLines", () => {
  it("sir's 11:33 candle", () => {
    const lines = volumeSplitLines(bar)
    expect(value(lines, "Buyers")).toBe("2,432 (93.33%)")
    expect(value(lines, "Sellers")).toBe("174 (6.67%)")
  })

  it("no volume reads N/A", () => {
    expect(value(volumeSplitLines({ ...bar, v: null }), "Buyers")).toBe("N/A")
  })
})

describe("seriesByAxis", () => {
  const t = ["a", "b"]

  it("groups per-bar traces by row and keeps the drawn colour", () => {
    const out = seriesByAxis([
      { name: "EMA9", x: t, y: [1, 2], yaxis: "y", line: { color: "#fff" } },
      { name: "RSI(2)", x: t, y: [3, 4], yaxis: "y2" },
    ], t)
    expect(out.get("y")).toEqual([{ label: "EMA9", values: [1, 2], digits: 2, color: "#fff" }])
    expect(out.get("y2")?.[0].label).toBe("RSI(2)")
  })

  it("leaves out traces with their own x: swings and trade markers are not readings", () => {
    expect(seriesByAxis([{ name: "Long Entry", x: ["a"], y: [1], yaxis: "y" }], t).size).toBe(0)
  })

  it("volume is whole contracts", () => {
    expect(seriesByAxis([{ name: "Vol", x: t, y: [1, 2], yaxis: "y6" }], t).get("y6")?.[0].digits).toBe(0)
  })
})

describe("nearestBarIndex", () => {
  const xs = [10, 20, 30]

  it.each([[0, 0], [10, 0], [14, 0], [16, 1], [20, 1], [29, 2], [99, 2]])("%s -> %s", (v, want) => {
    expect(nearestBarIndex(xs, v)).toBe(want)
  })

  it("a tie goes to the earlier bar", () => expect(nearestBarIndex(xs, 15)).toBe(0))
  it("no bars", () => expect(nearestBarIndex([], 5)).toBe(-1))
})

describe("readoutLines", () => {
  const series = [{ label: "RSI", values: [50, 98.2077], digits: 2 }]
  const fixed = [{ label: "OverBought", value: "94" }]

  it("an oscillator row is its reading and its levels, at that bar", () => {
    const row: ReadoutRow = { axis: "y2", title: "RSI (2)", series, fixed }
    expect(readoutLines(row, bar, 1)).toEqual([
      { label: "RSI", value: "98.21", color: undefined }, { label: "OverBought", value: "94" },
    ])
  })

  it("the price row starts with the candle", () => {
    const row: ReadoutRow = { axis: "y", title: "ES", series: [], fixed: [] }
    expect(readoutLines(row, bar, 0).map((l) => l.label)[0]).toBe("Date")
  })

  it("only the volume row gets buyers and sellers", () => {
    const row: ReadoutRow = { axis: "y6", title: "VolumeAvg (20)", series: [], fixed: [] }
    expect(readoutLines(row, bar, 0, "y6").map((l) => l.label)).toEqual(["Buyers", "Sellers"])
    expect(readoutLines(row, bar, 0, "y5")).toEqual([])
  })
})

describe("the VWAP studies -- sir's 11:34 box", () => {
  const C = { head: "#a", upper: "#b", lower: "#c" }
  // His 2-sigma distance, from the +/-1 line: 7553.92 - 7501.3 = 52.62.
  const mid = 7501.3, upper2 = 7501.3 + 2 * 52.62

  it.each([[0.5, "7,527.61", "7,474.99"], [1, "7,553.92", "7,448.68"], [1.5, "7,580.23", "7,422.37"]])(
    "+/-%s", (dev, up, down) => {
      const lines = vwapBlock(dev, mid, upper2, C)
      expect(lines[0].label).toBe(`VWAP (-${dev.toFixed(1)}, ${dev.toFixed(1)}, DAY)`)
      expect(value(lines, "VWAP")).toBe("7,501.30")
      expect(value(lines, "UpperBand")).toBe(up)
      expect(value(lines, "LowerBand")).toBe(down)
    },
  )

  it("no VWAP reads N/A", () => {
    expect(value(vwapBlock(1, null, null, C), "UpperBand")).toBe("N/A")
  })

  it("the box runs in thinkorswim's order", () => {
    const row: ReadoutRow = {
      axis: "y", title: "ES", series: [], fixed: [], vwap: { mid: [mid], upper2: [upper2] },
      profile: [{ label: "POC", value: "N/A" }, { label: "VAHigh", value: "N/A" }, { label: "VALow", value: "N/A" }],
    }
    expect(readoutLines(row, bar, 0).map((l) => l.label)).toEqual([
      "Date", "Open", "High", "Low", "Close", "Range",
      "VWAP (-0.5, 0.5, DAY)", "VWAP", "UpperBand", "LowerBand",
      "VolumeProfile", "POC", "VAHigh", "VALow",
      "VWAP (-1.0, 1.0, DAY)", "VWAP", "UpperBand", "LowerBand",
      "VWAP (-1.5, 1.5, DAY)", "VWAP", "UpperBand", "LowerBand",
    ])
  })
})
