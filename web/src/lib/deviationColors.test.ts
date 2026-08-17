import { describe, it, expect } from "vitest"
import {
  buildDeviationColorGroups, colorFor, wholePart, colorForSlot,
  paletteCollisions, DEFAULT_UPPER_PALETTE, DEFAULT_LOWER_PALETTE,
} from "./deviationColors"

// Values taken from the 2026-08-13 12:20 CT tape, 4 timeframes, +-2.0 sigma.
const UPPER = [7842.52, 7842.14, 7841.96, 7841.59]   // 5m, 10m, 15m, 20m
const LOWER = [7776.56, 7777.04, 7777.22, 7777.74]

const build = (u = UPPER, l = LOWER) => buildDeviationColorGroups(u, l)
type V = number | null | undefined
const cu = (g: ReturnType<typeof build>, v: V) => colorFor(g, "upper", v)
const cl = (g: ReturnType<typeof build>, v: V) => colorFor(g, "lower", v)

describe("Test 1 — same Upper integer shares a colour", () => {
  it("7842.52 and 7842.14 match", () => {
    const g = build()
    expect(cu(g, 7842.52)).toBe(cu(g, 7842.14))
  })
})

describe("Test 2 — different Upper integers differ", () => {
  it("7842.52 and 7841.96 differ", () => {
    const g = build()
    expect(cu(g, 7842.52)).not.toBe(cu(g, 7841.96))
  })
  it("7841.96 and 7841.59 still match each other", () => {
    const g = build()
    expect(cu(g, 7841.96)).toBe(cu(g, 7841.59))
  })
})

describe("Test 3 — same Lower integer shares a colour", () => {
  it("all three 7777.xx match", () => {
    const g = build()
    expect(cl(g, 7777.04)).toBe(cl(g, 7777.22))
    expect(cl(g, 7777.22)).toBe(cl(g, 7777.74))
  })
})

describe("Test 4 — different Lower integers differ", () => {
  it("7777.04 and 7776.56 differ", () => {
    const g = build()
    expect(cl(g, 7777.04)).not.toBe(cl(g, 7776.56))
  })
})

describe("Test 5 — Upper and Lower never share a colour", () => {
  it("the same integer on both sides gets two colours", () => {
    const g = buildDeviationColorGroups([7842.52], [7842.41])
    expect(cu(g, 7842.52)).not.toBe(cl(g, 7842.41))
  })

  it("default palettes do not overlap at all", () => {
    expect(paletteCollisions(DEFAULT_UPPER_PALETTE, DEFAULT_LOWER_PALETTE)).toEqual([])
  })

  it("no upper colour equals any lower colour, including generated overflow", () => {
    const ups = Array.from({ length: 40 }, (_, i) => colorForSlot("upper", i))
    const los = Array.from({ length: 40 }, (_, i) => colorForSlot("lower", i))
    expect(ups.filter((c) => los.includes(c))).toEqual([])
  })

  it("keeps sides apart even when both hold identical value sets", () => {
    const same = [100.1, 101.1, 102.1]
    const g = buildDeviationColorGroups(same, same)
    for (const v of same) expect(cu(g, v)).not.toBe(cl(g, v))
  })
})

describe("Test 6 — any number of timeframes", () => {
  for (const n of [1, 2, 4, 8, 12]) {
    it(`${n} timeframe(s): every distinct integer gets its own colour`, () => {
      const u = Array.from({ length: n }, (_, i) => 7800 + i + 0.5)
      const l = Array.from({ length: n }, (_, i) => 7700 + i + 0.5)
      const g = buildDeviationColorGroups(u, l)
      expect(g.upperOrder).toHaveLength(n)
      expect(new Set(u.map((v) => cu(g, v))).size).toBe(n)
      expect(new Set(l.map((v) => cl(g, v))).size).toBe(n)
    })
  }

  it("one timeframe still colours its single group", () => {
    const g = buildDeviationColorGroups([7842.52], [7776.56])
    expect(cu(g, 7842.52)).toBe(DEFAULT_UPPER_PALETTE[0])
    expect(cl(g, 7776.56)).toBe(DEFAULT_LOWER_PALETTE[0])
  })
})

describe("Test 7 — any deviation selection", () => {
  it("+-1 and +-2 both group the same way", () => {
    // +-1 sits nearer the VWAP, so the numbers differ entirely.
    const g1 = buildDeviationColorGroups([7830.2, 7830.9, 7829.4], [7789.1, 7789.8, 7790.2])
    expect(cu(g1, 7830.2)).toBe(cu(g1, 7830.9))
    expect(cu(g1, 7830.2)).not.toBe(cu(g1, 7829.4))
    expect(cl(g1, 7789.1)).toBe(cl(g1, 7789.8))
    expect(cl(g1, 7789.1)).not.toBe(cl(g1, 7790.2))
  })

  it("several levels at once pool per side, not per column", () => {
    // +-1 and +-2 shown together: four columns, two sides.
    const upper = [7830.2, 7830.9, 7842.5, 7842.1]
    const lower = [7789.1, 7789.8, 7776.5, 7777.0]
    const g = buildDeviationColorGroups(upper, lower)
    expect(g.upperOrder).toEqual([7830, 7842])
    expect(g.lowerOrder).toEqual([7776, 7777, 7789])
    expect(cu(g, 7830.2)).toBe(cu(g, 7830.9))
    expect(cu(g, 7842.5)).toBe(cu(g, 7842.1))
  })
})

describe("Test 8 — recalculates for a different dataset", () => {
  it("a different date produces different groups from the same code", () => {
    const g = buildDeviationColorGroups(
      [8125.43, 8125.91, 8124.27, 8123.88],
      [7951.32, 7951.77, 7950.42],
    )
    expect(g.upperOrder).toEqual([8123, 8124, 8125])
    expect(g.lowerOrder).toEqual([7950, 7951])
    expect(cu(g, 8125.43)).toBe(cu(g, 8125.91))
    expect(cu(g, 8124.27)).not.toBe(cu(g, 8123.88))
    expect(cl(g, 7951.32)).toBe(cl(g, 7951.77))
    expect(cl(g, 7951.32)).not.toBe(cl(g, 7950.42))
  })

  it("no value from the original screenshot is special-cased", () => {
    // Shifting every price by a constant must not change the shape.
    const shift = (a: number[]) => a.map((v) => v + 1000)
    const a = buildDeviationColorGroups(UPPER, LOWER)
    const b = buildDeviationColorGroups(shift(UPPER), shift(LOWER))
    expect(a.upperOrder.map((k) => a.upper.get(k)))
      .toEqual(b.upperOrder.map((k) => b.upper.get(k)))
  })
})

describe("Test 9 — missing values are safe", () => {
  it("null, undefined and NaN get no colour and no group", () => {
    const g = buildDeviationColorGroups([null, undefined, NaN, 7842.5], [NaN, 7776.5])
    expect(cu(g, null)).toBeNull()
    expect(cu(g, undefined)).toBeNull()
    expect(cu(g, NaN)).toBeNull()
    expect(g.upperOrder).toEqual([7842])
    expect(cu(g, 7842.5)).not.toBeNull()
  })

  it("an entirely empty side does not throw", () => {
    const g = buildDeviationColorGroups([null, NaN], [])
    expect(g.upperOrder).toEqual([])
    expect(g.lowerOrder).toEqual([])
  })

  it("Infinity is treated as missing", () => {
    const g = buildDeviationColorGroups([Infinity, -Infinity], [])
    expect(g.upperOrder).toEqual([])
  })
})

describe("Test 10 — deterministic", () => {
  it("same input, same output, every time", () => {
    const runs = Array.from({ length: 25 }, () => {
      const g = build()
      return [...UPPER.map((v) => cu(g, v)), ...LOWER.map((v) => cl(g, v))].join("|")
    })
    expect(new Set(runs).size).toBe(1)
  })

  it("input order does not affect the mapping", () => {
    const a = buildDeviationColorGroups(UPPER, LOWER)
    const b = buildDeviationColorGroups([...UPPER].reverse(), [...LOWER].reverse())
    for (const v of UPPER) expect(colorFor(a, "upper", v)).toBe(colorFor(b, "upper", v))
    for (const v of LOWER) expect(colorFor(a, "lower", v)).toBe(colorFor(b, "lower", v))
  })

  it("groups are ordered ascending, so slot 1 is always the lowest", () => {
    const g = build()
    expect(g.upperOrder).toEqual([7841, 7842])
    expect(g.lowerOrder).toEqual([7776, 7777])
    expect(cu(g, 7841.59)).toBe(DEFAULT_UPPER_PALETTE[0])
    expect(cu(g, 7842.52)).toBe(DEFAULT_UPPER_PALETTE[1])
  })
})

describe("whole-number extraction", () => {
  it("ignores the decimals entirely", () => {
    for (const v of [7842.01, 7842.14, 7842.52, 7842.99]) expect(wholePart(v)).toBe(7842)
  })

  it("truncates toward zero for negatives, so -1.2 and -1.8 group together", () => {
    expect(wholePart(-1.2)).toBe(-1)
    expect(wholePart(-1.8)).toBe(-1)
    expect(wholePart(-1.0)).toBe(-1)
    const g = buildDeviationColorGroups([-1.2, -1.8], [])
    expect(cu(g, -1.2)).toBe(cu(g, -1.8))
  })

  it("does not group across a whole-number boundary", () => {
    const g = buildDeviationColorGroups([7841.99, 7842.01], [])
    expect(cu(g, 7841.99)).not.toBe(cu(g, 7842.01))
  })
})

describe("more groups than the palette holds", () => {
  const n = DEFAULT_UPPER_PALETTE.length + 12

  it("never repeats a colour just because the palette ran out", () => {
    const u = Array.from({ length: n }, (_, i) => 7000 + i + 0.5)
    const g = buildDeviationColorGroups(u, [])
    const colors = u.map((v) => cu(g, v))
    expect(new Set(colors).size).toBe(n)
  })

  it("overflow colours stay inside their own side's hue band", () => {
    const hue = (c: string) => Number(/hsl\(([\d.]+)/.exec(c)?.[1] ?? NaN)
    for (let i = DEFAULT_UPPER_PALETTE.length; i < n; i++) {
      const h = hue(colorForSlot("upper", i))
      expect(h).toBeGreaterThanOrEqual(25)
      expect(h).toBeLessThan(165)
    }
    for (let i = DEFAULT_LOWER_PALETTE.length; i < n; i++) {
      const h = hue(colorForSlot("lower", i))
      expect(h).toBeGreaterThanOrEqual(195)
      expect(h).toBeLessThan(355)
    }
  })
})

describe("user-supplied palettes", () => {
  it("custom colours are used in slot order", () => {
    const g = buildDeviationColorGroups(UPPER, LOWER, {
      upperPalette: ["#111111", "#222222"],
      lowerPalette: ["#333333", "#444444"],
    })
    expect(cu(g, 7841.59)).toBe("#111111")   // lowest upper group -> slot 1
    expect(cu(g, 7842.52)).toBe("#222222")
    expect(cl(g, 7776.56)).toBe("#333333")
    expect(cl(g, 7777.04)).toBe("#444444")
  })

  it("a short custom palette still overflows without repeating", () => {
    const u = [10.1, 11.1, 12.1, 13.1]
    const g = buildDeviationColorGroups(u, [], { upperPalette: ["#111111"] })
    expect(new Set(u.map((v) => cu(g, v))).size).toBe(4)
  })

  it("reports collisions rather than silently changing the choice", () => {
    expect(paletteCollisions(["#e3b341", "#58A6FF"], ["#58a6ff"])).toEqual(["#58A6FF"])
    expect(paletteCollisions(["#e3b341"], ["#f06292"])).toEqual([])
  })
})
