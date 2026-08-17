import { describe, it, expect } from "vitest"
import {
  buildDeviationColorGroups, colorFor, wholePart, colorForSlot,
  paletteCollisions, DEFAULT_UPPER_PALETTE, DEFAULT_LOWER_PALETTE,
  type DeviationColumn,
} from "./deviationColors"

// Columns are supplied in render order: [+d0, -d0, +d1, -d1, ...].
const up = (...values: Array<number | null | undefined>): DeviationColumn =>
  ({ side: "upper", values })
const lo = (...values: Array<number | null | undefined>): DeviationColumn =>
  ({ side: "lower", values })

// The 2026-08-13 12:20 CT tape, 4 timeframes, +-2.0 sigma.
//        Upper +2.0s              Lower -2.0s
// 5m     7842.52                  7776.56
// 10m    7842.14                  7777.04
// 15m    7841.96                  7777.22
// 20m    7841.59                  7777.74
const UPPER2 = up(7842.52, 7842.14, 7841.96, 7841.59)
const LOWER2 = lo(7776.56, 7777.04, 7777.22, 7777.74)
const ONE_LEVEL = [UPPER2, LOWER2]
const g1 = () => buildDeviationColorGroups(ONE_LEVEL)

describe("Test 1 — same integer in a column shares a colour", () => {
  it("Upper 7842.52 and 7842.14", () => {
    const g = g1()
    expect(colorFor(g, 0, 7842.52)).toBe(colorFor(g, 0, 7842.14))
  })
})

describe("Test 2 — different integers in a column differ", () => {
  it("Upper 7842 vs 7841", () => {
    const g = g1()
    expect(colorFor(g, 0, 7842.52)).not.toBe(colorFor(g, 0, 7841.96))
    expect(colorFor(g, 0, 7841.96)).toBe(colorFor(g, 0, 7841.59))
  })
})

describe("Test 3 — same Lower integer shares a colour", () => {
  it("all three 7777.xx", () => {
    const g = g1()
    expect(colorFor(g, 1, 7777.04)).toBe(colorFor(g, 1, 7777.22))
    expect(colorFor(g, 1, 7777.22)).toBe(colorFor(g, 1, 7777.74))
  })
})

describe("Test 4 — different Lower integers differ", () => {
  it("7777 vs 7776", () => {
    const g = g1()
    expect(colorFor(g, 1, 7777.04)).not.toBe(colorFor(g, 1, 7776.56))
  })
})

describe("Test 5 — Upper and Lower never share a colour", () => {
  it("the same integer on both sides gets two colours", () => {
    const g = buildDeviationColorGroups([up(7842.52), lo(7842.41)])
    expect(colorFor(g, 0, 7842.52)).not.toBe(colorFor(g, 1, 7842.41))
  })

  it("default palettes are disjoint", () => {
    expect(paletteCollisions(DEFAULT_UPPER_PALETTE, DEFAULT_LOWER_PALETTE)).toEqual([])
  })

  it("no upper colour equals any lower colour, generated overflow included", () => {
    const u = Array.from({ length: 40 }, (_, i) => colorForSlot("upper", i))
    const l = Array.from({ length: 40 }, (_, i) => colorForSlot("lower", i))
    expect(u.filter((c) => l.includes(c))).toEqual([])
  })
})

// ---------------------------------------------------------------------------
// The correction: each sigma column is grouped on its own.
// ---------------------------------------------------------------------------
describe("per-sigma-column grouping", () => {
  // Upper +1s and Upper +2s both containing 7842 must NOT be one group.
  const COLS = [
    up(7842.5, 7842.2),   // col 0 — Upper +1s
    lo(7700.1, 7700.9),   // col 1 — Lower -1s
    up(7842.7, 7841.9),   // col 2 — Upper +2s
    lo(7600.4, 7601.6),   // col 3 — Lower -2s
  ]

  it("the same integer in two Upper columns is not one shared group", () => {
    const g = buildDeviationColorGroups(COLS)
    expect(colorFor(g, 0, 7842.5)).not.toBe(colorFor(g, 2, 7842.7))
  })

  it("grouping inside a column is unaffected by other columns", () => {
    const g = buildDeviationColorGroups(COLS)
    expect(colorFor(g, 0, 7842.5)).toBe(colorFor(g, 0, 7842.2))
    expect(colorFor(g, 2, 7842.7)).not.toBe(colorFor(g, 2, 7841.9))
  })

  it("a value only ever matches within its own column", () => {
    const g = buildDeviationColorGroups(COLS)
    expect(colorFor(g, 1, 7842.5)).toBeNull()
  })

  it("several Upper columns each keep their own grouping", () => {
    const g = buildDeviationColorGroups([
      up(100.1, 100.9, 101.2),
      up(100.4, 102.7),
      up(100.8),
    ])
    expect(colorFor(g, 0, 100.1)).toBe(colorFor(g, 0, 100.9))
    expect(colorFor(g, 0, 100.1)).not.toBe(colorFor(g, 1, 100.4))
    expect(colorFor(g, 1, 100.4)).not.toBe(colorFor(g, 2, 100.8))
  })

  it("several Lower columns each keep their own grouping", () => {
    const g = buildDeviationColorGroups([lo(50.1, 50.9), lo(50.4, 51.1)])
    expect(colorFor(g, 0, 50.1)).toBe(colorFor(g, 0, 50.9))
    expect(colorFor(g, 0, 50.1)).not.toBe(colorFor(g, 1, 50.4))
  })

  it("keeps sides apart even when every column holds the same numbers", () => {
    const vals = [10.1, 11.1]
    const g = buildDeviationColorGroups([up(...vals), lo(...vals), up(...vals), lo(...vals)])
    const uppers = [colorFor(g, 0, 10.1), colorFor(g, 0, 11.1), colorFor(g, 2, 10.1), colorFor(g, 2, 11.1)]
    const lowers = [colorFor(g, 1, 10.1), colorFor(g, 1, 11.1), colorFor(g, 3, 10.1), colorFor(g, 3, 11.1)]
    expect(uppers.filter((c) => lowers.includes(c))).toEqual([])
    // No two distinct groups on a side share a colour, across columns.
    expect(new Set(uppers).size).toBe(4)
    expect(new Set(lowers).size).toBe(4)
  })
})

describe("Test 6 — any number of timeframes", () => {
  for (const n of [1, 2, 4, 8, 12]) {
    it(`${n} timeframe(s)`, () => {
      const u = Array.from({ length: n }, (_, i) => 7800 + i + 0.5)
      const l = Array.from({ length: n }, (_, i) => 7700 + i + 0.5)
      const g = buildDeviationColorGroups([up(...u), lo(...l)])
      expect(new Set(u.map((v) => colorFor(g, 0, v))).size).toBe(n)
      expect(new Set(l.map((v) => colorFor(g, 1, v))).size).toBe(n)
    })
  }

  it("one timeframe still colours its single group with slot 1", () => {
    const g = buildDeviationColorGroups([up(7842.52), lo(7776.56)])
    expect(colorFor(g, 0, 7842.52)).toBe(DEFAULT_UPPER_PALETTE[0])
    expect(colorFor(g, 1, 7776.56)).toBe(DEFAULT_LOWER_PALETTE[0])
  })
})

describe("Test 7 — any deviation selection", () => {
  it("+-1 alone groups the same way as +-2 alone", () => {
    const g = buildDeviationColorGroups([up(7830.2, 7830.9, 7829.4), lo(7789.1, 7789.8, 7790.2)])
    expect(colorFor(g, 0, 7830.2)).toBe(colorFor(g, 0, 7830.9))
    expect(colorFor(g, 0, 7830.2)).not.toBe(colorFor(g, 0, 7829.4))
    expect(colorFor(g, 1, 7789.1)).toBe(colorFor(g, 1, 7789.8))
  })

  it("adding a third level does not disturb the first two", () => {
    const two = [up(7830.2, 7829.4), lo(7789.1, 7789.8)]
    const three = [...two, up(7850.1, 7850.9), lo(7770.2, 7771.3)]
    const a = buildDeviationColorGroups(two)
    const b = buildDeviationColorGroups(three)
    expect(colorFor(a, 0, 7830.2)).toBe(colorFor(b, 0, 7830.2))
    expect(colorFor(a, 1, 7789.1)).toBe(colorFor(b, 1, 7789.1))
  })
})

describe("Test 8 — recalculates for a different dataset", () => {
  it("another date, groups derived afresh", () => {
    const g = buildDeviationColorGroups([
      up(8125.43, 8125.91, 8124.27, 8123.88),
      lo(7951.32, 7951.77, 7950.42),
    ])
    expect(g.upperGroups).toEqual([8123, 8124, 8125])
    expect(g.lowerGroups).toEqual([7950, 7951])
    expect(colorFor(g, 0, 8125.43)).toBe(colorFor(g, 0, 8125.91))
    expect(colorFor(g, 1, 7951.32)).toBe(colorFor(g, 1, 7951.77))
  })

  it("nothing is special-cased to the screenshot's prices", () => {
    const shift = (c: DeviationColumn): DeviationColumn =>
      ({ side: c.side, values: c.values.map((v) => (v as number) + 1000) })
    const a = buildDeviationColorGroups(ONE_LEVEL)
    const b = buildDeviationColorGroups(ONE_LEVEL.map(shift))
    expect(a.upperGroups).toHaveLength(b.upperGroups.length)
    expect(colorFor(a, 0, 7842.52)).toBe(colorFor(b, 0, 8842.52))
  })
})

describe("Test 9 — missing values are safe", () => {
  it("null, undefined, NaN and Infinity get no colour", () => {
    const g = buildDeviationColorGroups([up(null, undefined, NaN, Infinity, 7842.5), lo(NaN)])
    expect(colorFor(g, 0, null)).toBeNull()
    expect(colorFor(g, 0, undefined)).toBeNull()
    expect(colorFor(g, 0, NaN)).toBeNull()
    expect(colorFor(g, 0, Infinity)).toBeNull()
    expect(g.upperGroups).toEqual([7842])
    expect(g.lowerGroups).toEqual([])
  })

  it("an empty column list does not throw", () => {
    const g = buildDeviationColorGroups([])
    expect(g.byColumn).toEqual([])
    expect(colorFor(g, 0, 1)).toBeNull()
  })

  it("an out-of-range column index yields null, not a crash", () => {
    expect(colorFor(g1(), 99, 7842.5)).toBeNull()
  })
})

describe("Test 10 — deterministic", () => {
  it("same input, same output", () => {
    const runs = Array.from({ length: 25 }, () => {
      const g = g1()
      return [7842.52, 7841.96].map((v) => colorFor(g, 0, v))
        .concat([7777.04, 7776.56].map((v) => colorFor(g, 1, v))).join("|")
    })
    expect(new Set(runs).size).toBe(1)
  })

  it("row order within a column does not matter", () => {
    const a = buildDeviationColorGroups(ONE_LEVEL)
    const b = buildDeviationColorGroups([
      up(7841.59, 7841.96, 7842.14, 7842.52),
      lo(7777.74, 7777.22, 7777.04, 7776.56),
    ])
    expect(colorFor(a, 0, 7842.52)).toBe(colorFor(b, 0, 7842.52))
    expect(colorFor(a, 1, 7776.56)).toBe(colorFor(b, 1, 7776.56))
  })

  it("within a column, slot 1 is the lowest group", () => {
    const g = g1()
    expect(colorFor(g, 0, 7841.59)).toBe(DEFAULT_UPPER_PALETTE[0])
    expect(colorFor(g, 0, 7842.52)).toBe(DEFAULT_UPPER_PALETTE[1])
    expect(colorFor(g, 1, 7776.56)).toBe(DEFAULT_LOWER_PALETTE[0])
  })
})

describe("whole-number extraction", () => {
  it("decimals are ignored", () => {
    for (const v of [7842.01, 7842.14, 7842.52, 7842.99]) expect(wholePart(v)).toBe(7842)
  })
  it("truncates toward zero for negatives", () => {
    expect(wholePart(-1.2)).toBe(-1)
    expect(wholePart(-1.8)).toBe(-1)
    const g = buildDeviationColorGroups([up(-1.2, -1.8)])
    expect(colorFor(g, 0, -1.2)).toBe(colorFor(g, 0, -1.8))
  })
  it("does not group across a whole-number boundary", () => {
    const g = buildDeviationColorGroups([up(7841.99, 7842.01)])
    expect(colorFor(g, 0, 7841.99)).not.toBe(colorFor(g, 0, 7842.01))
  })
})

describe("more groups than the palette holds", () => {
  const n = DEFAULT_UPPER_PALETTE.length + 12

  it("never repeats a colour because the palette ran out", () => {
    const vals = Array.from({ length: n }, (_, i) => 7000 + i + 0.5)
    const g = buildDeviationColorGroups([up(...vals)])
    expect(new Set(vals.map((v) => colorFor(g, 0, v))).size).toBe(n)
  })

  it("groups spread over many columns still never repeat within a side", () => {
    const cols = Array.from({ length: 10 }, (_, i) => up(i * 100 + 0.5, i * 100 + 1.5))
    const g = buildDeviationColorGroups(cols)
    const seen = cols.flatMap((c, i) => c.values.map((v) => colorFor(g, i, v as number)))
    expect(new Set(seen).size).toBe(20)
  })

  it("overflow colours stay in their side's hue band", () => {
    const hue = (c: string) => Number(/hsl\(([\d.]+)/.exec(c)?.[1] ?? NaN)
    for (let i = DEFAULT_UPPER_PALETTE.length; i < n; i++) {
      expect(hue(colorForSlot("upper", i))).toBeGreaterThanOrEqual(25)
      expect(hue(colorForSlot("upper", i))).toBeLessThan(165)
    }
    for (let i = DEFAULT_LOWER_PALETTE.length; i < n; i++) {
      expect(hue(colorForSlot("lower", i))).toBeGreaterThanOrEqual(195)
      expect(hue(colorForSlot("lower", i))).toBeLessThan(355)
    }
  })
})

describe("user-supplied palettes", () => {
  it("custom colours are used in slot order", () => {
    const g = buildDeviationColorGroups(ONE_LEVEL, {
      upperPalette: ["#111111", "#222222"],
      lowerPalette: ["#333333", "#444444"],
    })
    expect(colorFor(g, 0, 7841.59)).toBe("#111111")
    expect(colorFor(g, 0, 7842.52)).toBe("#222222")
    expect(colorFor(g, 1, 7776.56)).toBe("#333333")
    expect(colorFor(g, 1, 7777.04)).toBe("#444444")
  })

  it("custom slots carry across columns on the same side", () => {
    const g = buildDeviationColorGroups([up(10.1), up(20.1)], {
      upperPalette: ["#111111", "#222222"],
    })
    expect(colorFor(g, 0, 10.1)).toBe("#111111")
    expect(colorFor(g, 1, 20.1)).toBe("#222222")
  })

  it("a short custom palette overflows without repeating", () => {
    const vals = [10.1, 11.1, 12.1, 13.1]
    const g = buildDeviationColorGroups([up(...vals)], { upperPalette: ["#111111"] })
    expect(new Set(vals.map((v) => colorFor(g, 0, v))).size).toBe(4)
  })

  it("collisions are reported, not corrected", () => {
    expect(paletteCollisions(["#e3b341", "#58A6FF"], ["#58a6ff"])).toEqual(["#58A6FF"])
    expect(paletteCollisions(["#e3b341"], ["#f06292"])).toEqual([])
  })
})
