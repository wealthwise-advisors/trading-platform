/**
 * The two POC columns, against the cases sir described on 2026-10-11.
 */
import { describe, expect, it } from "vitest"

import {
  POC_LEVEL_PALETTE, barsClosedBy, buildLevelColorMap, buildPocColumns, levelColor, sideVsAverage,
} from "./pocColumns"

const rows = (m: Record<string, number | null>) =>
  Object.entries(m).map(([tf, poc]) => ({ tf, poc }))

describe("POC Match — same whole number, same colour", () => {
  it("seven of eleven on one level share a colour; the other four do not", () => {
    // The example as given: eleven timeframes, seven agreeing before the
    // decimal point, four elsewhere.
    const c = buildPocColumns(rows({
      "1m": 7842.75, "3m": 7842.10, "5m": 7842.50, "10m": 7842.00,
      "15m": 7842.99, "20m": 7842.25, "25m": 7842.40,
      "30m": 7840.50, "45m": 7845.25, "1h": 7838.75, "2h": 7845.90,
    }))
    const seven = ["1m", "3m", "5m", "10m", "15m", "20m", "25m"]
    const color = c.level.get("1m")!.color
    for (const tf of seven) {
      expect(c.level.get(tf)!.level).toBe(7842)
      expect(c.level.get(tf)!.color).toBe(color)
      expect(c.level.get(tf)!.count).toBe(7)
    }
    for (const tf of ["30m", "45m", "1h", "2h"]) {
      expect(c.level.get(tf)!.color).not.toBe(color)
    }
    // 45m and 2h are both 7845.xx -- a second, smaller group of two.
    expect(c.level.get("45m")!.color).toBe(c.level.get("2h")!.color)
    expect(c.level.get("45m")!.count).toBe(2)
    expect(c.counted).toBe(11)
  })

  it("decides on the digits before the decimal, not on closeness", () => {
    // 7842.99 and 7843.01 are 0.02 apart and still different levels;
    // 7842.01 and 7842.99 are 0.98 apart and the same level.
    const c = buildPocColumns(rows({ a: 7842.99, b: 7843.01, c: 7842.01 }))
    expect(c.level.get("a")!.color).not.toBe(c.level.get("b")!.color)
    expect(c.level.get("a")!.color).toBe(c.level.get("c")!.color)
  })

  it("colours by price order, so the same levels get the same colours either way round", () => {
    const one = buildPocColumns(rows({ x: 7845, y: 7840 }))
    const two = buildPocColumns(rows({ x: 7840, y: 7845 }))
    expect(one.level.get("y")!.color).toBe(two.level.get("x")!.color)
    // The lowest level opens on the palette's first colour.
    expect(one.level.get("y")!.color).toBe(POC_LEVEL_PALETTE[0])
  })

  it("the first eight levels get eight different colours, and neighbours never match", () => {
    const many = Object.fromEntries(Array.from({ length: 14 }, (_, i) => [`t${i}`, 7800 + i]))
    const c = buildPocColumns(rows(many))
    const sorted = [...c.level.values()].sort((a, b) => a.level - b.level)
    expect(new Set(sorted.slice(0, 8).map((l) => l.color)).size).toBe(8)
    for (let i = 1; i < sorted.length; i++) expect(sorted[i].color).not.toBe(sorted[i - 1].color)
  })

  it("gives the Live table's levels the first colours, ahead of the tape's", () => {
    const tape = [7800, 7801, 7802, 7803, 7850]
    const live = [7850, 7802]
    const colors = buildLevelColorMap([...live, ...tape], live)
    expect(colors.get(7802)).toBe(POC_LEVEL_PALETTE[0])
    expect(colors.get(7850)).toBe(POC_LEVEL_PALETTE[1])
    expect(colors.get(7800)).toBe(POC_LEVEL_PALETTE[2])
  })

  it("never uses green or red, which mean above/below in the next column", () => {
    // Checked past the palette too: eleven timeframes can sit on eleven
    // levels, and the generated colours are where green would sneak in.
    const hueOf = (c: string) => {
      if (c.startsWith("hsl(")) return parseFloat(c.slice(4))
      const [r, g, b] = [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16) / 255)
      const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn
      if (d === 0) return -1
      const h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4
      return (h * 60 + 360) % 360
    }
    for (let i = 0; i < 30; i++) {
      const h = hueOf(levelColor(i))
      expect(h >= 85 && h <= 165, `level ${i} is green (hue ${h})`).toBe(false)
      expect(h >= 340 || (h >= 0 && h <= 20), `level ${i} is red (hue ${h})`).toBe(false)
    }
    void POC_LEVEL_PALETTE
  })
})

describe("POC vs Avg — green above the average, red below", () => {
  it("takes the mean of the selected timeframes' POCs as the reference", () => {
    const c = buildPocColumns(rows({ "1m": 7840, "5m": 7842, "15m": 7844, "1h": 7846 }))
    expect(c.average).toBe(7843)
    expect(c.side.get("1m")).toBe("below")
    expect(c.side.get("5m")).toBe("below")
    expect(c.side.get("15m")).toBe("above")
    expect(c.side.get("1h")).toBe("above")
    expect(c.diff.get("1h")).toBeCloseTo(3, 10)
    expect(c.diff.get("1m")).toBeCloseTo(-3, 10)
  })

  it("works for any number selected, not only eleven", () => {
    const four = buildPocColumns(rows({ a: 10, b: 20, c: 30, d: 40 }))
    expect(four.average).toBe(25)
    const five = buildPocColumns(rows({ a: 10, b: 20, c: 30, d: 40, e: 50 }))
    expect(five.average).toBe(30)
    expect(five.side.get("c")).toBe("equal")
  })

  it("compares the raw value, not the whole number", () => {
    // Average 7842.5. 7842.9 IS above it, though both round down to 7842.
    const c = buildPocColumns(rows({ a: 7842.1, b: 7842.9 }))
    expect(c.average).toBeCloseTo(7842.5, 10)
    expect(c.side.get("b")).toBe("above")
    expect(c.side.get("a")).toBe("below")
  })

  it("a POC that IS the average is neither colour", () => {
    // Every timeframe on the same POC: nothing is above or below anything.
    const c = buildPocColumns(rows({ a: 7842.25, b: 7842.25, c: 7842.25 }))
    for (const tf of ["a", "b", "c"]) expect(c.side.get(tf)).toBe("equal")
  })

  it("is not fooled by floating-point noise in the mean", () => {
    // 0.1 + 0.2 + 0.3 averaged is not exactly 0.2 in binary floating point.
    const c = buildPocColumns(rows({ a: 0.1, b: 0.2, c: 0.3 }))
    expect(c.side.get("b")).toBe("equal")
  })
})

describe("missing data", () => {
  it("skips a timeframe with no POC rather than averaging it in as zero", () => {
    const c = buildPocColumns([
      { tf: "1m", poc: 7840 }, { tf: "5m", poc: null },
      { tf: "15m", poc: undefined }, { tf: "1h", poc: Number.NaN }, { tf: "4h", poc: 7844 },
    ])
    expect(c.counted).toBe(2)
    expect(c.average).toBe(7842)
    expect(c.level.has("5m")).toBe(false)
    expect(c.side.has("1h")).toBe(false)
  })

  it("with no POCs at all there is no average and nothing coloured", () => {
    const c = buildPocColumns(rows({ a: null, b: null }))
    expect(c.average).toBeNull()
    expect(c.counted).toBe(0)
    expect(c.level.size).toBe(0)
  })
})

describe("shared level colours -- one level, one colour, in every table", () => {
  it("gives the same level the same colour wherever it appears", () => {
    // The Live state table and the Consolidated tape draw from one map, so a
    // level read in one is the same colour in the other.
    const shared = buildLevelColorMap([5823.43, 5708.05, 5823.9, 5801.2])
    const live = buildPocColumns(rows({ "5m": 5823.43, "20m": 5708.05 }), shared)
    expect(live.level.get("5m")!.color).toBe(shared.get(5823))
    expect(live.level.get("20m")!.color).toBe(shared.get(5708))
  })

  it("colours by price order and skips missing values", () => {
    const m = buildLevelColorMap([5810, null, undefined, Number.NaN, 5800])
    expect([...m.keys()]).toEqual([5800, 5810])
    expect(m.get(5800)).toBe(POC_LEVEL_PALETTE[0])
  })
})

describe("sideVsAverage", () => {
  it("is green above, red below, neither on the average", () => {
    expect(sideVsAverage(10, 7)).toEqual({ side: "above", diff: 3 })
    expect(sideVsAverage(4, 7)).toEqual({ side: "below", diff: -3 })
    expect(sideVsAverage(0.1 + 0.2, 0.3).side).toBe("equal")
  })
})

describe("barsClosedBy -- each timeframe's state at a past moment", () => {
  const min = 60_000
  // Four 5m bars opening at 09:30, 09:35, 09:40, 09:45 (ms offsets).
  const opens = [0, 5, 10, 15].map((m) => m * min)

  it("counts only bars that had CLOSED by the moment", () => {
    expect(barsClosedBy(opens, 5, 4 * min)).toBe(0)   // 09:34: first bar still open
    expect(barsClosedBy(opens, 5, 5 * min)).toBe(1)   // 09:35: first bar just closed
    expect(barsClosedBy(opens, 5, 14 * min)).toBe(2)
    expect(barsClosedBy(opens, 5, 60 * min)).toBe(4)
  })

  it("handles a coarser bar that has not closed yet", () => {
    // A 15m bar opening at 0 is not closed at 14 minutes, closed at 15.
    expect(barsClosedBy([0], 15, 14 * min)).toBe(0)
    expect(barsClosedBy([0], 15, 15 * min)).toBe(1)
  })

  it("an empty pane has nothing closed", () => {
    expect(barsClosedBy([], 5, 99 * min)).toBe(0)
  })
})
