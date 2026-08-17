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

  it("several Upper columns each group independently", () => {
    const g = buildDeviationColorGroups([
      up(100.1, 100.9, 101.2),
      up(100.4, 102.7),
      up(100.8),
    ])
    // Within a column, 100 and 101 are separate groups.
    expect(colorFor(g, 0, 100.1)).toBe(colorFor(g, 0, 100.9))
    expect(colorFor(g, 0, 100.1)).not.toBe(colorFor(g, 0, 101.2))
    // Across columns the palette restarts, so slot 1 recurs BY DESIGN --
    // colour means "lowest group in THIS column", and columns are never
    // compared with each other.
    expect(colorFor(g, 0, 100.1)).toBe(colorFor(g, 1, 100.4))
    expect(colorFor(g, 1, 100.4)).toBe(colorFor(g, 2, 100.8))
  })

  it("several Lower columns each group independently", () => {
    const g = buildDeviationColorGroups([lo(50.1, 50.9), lo(50.4, 51.1)])
    expect(colorFor(g, 0, 50.1)).toBe(colorFor(g, 0, 50.9))
    expect(colorFor(g, 1, 50.4)).not.toBe(colorFor(g, 1, 51.1))
    expect(colorFor(g, 0, 50.1)).toBe(colorFor(g, 1, 50.4))   // slot 1 recurs
  })

  it("keeps sides apart even when every column holds the same numbers", () => {
    const vals = [10.1, 11.1]
    const g = buildDeviationColorGroups([up(...vals), lo(...vals), up(...vals), lo(...vals)])
    const uppers = [colorFor(g, 0, 10.1), colorFor(g, 0, 11.1), colorFor(g, 2, 10.1), colorFor(g, 2, 11.1)]
    const lowers = [colorFor(g, 1, 10.1), colorFor(g, 1, 11.1), colorFor(g, 3, 10.1), colorFor(g, 3, 11.1)]
    // The guarantee that matters: no Upper colour is ever a Lower colour.
    expect(uppers.filter((c) => lowers.includes(c))).toEqual([])
    // Two slots per column, and the slots restart, so two distinct colours
    // per side -- not four. Columns repeating a colour is intended.
    expect(new Set(uppers).size).toBe(2)
    expect(new Set(lowers).size).toBe(2)
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
    expect(g.perColumn.filter(c => c.side === "upper").flatMap(c => c.groups)).toEqual([8123, 8124, 8125])
    expect(g.perColumn.filter(c => c.side === "lower").flatMap(c => c.groups)).toEqual([7950, 7951])
    expect(colorFor(g, 0, 8125.43)).toBe(colorFor(g, 0, 8125.91))
    expect(colorFor(g, 1, 7951.32)).toBe(colorFor(g, 1, 7951.77))
  })

  it("nothing is special-cased to the screenshot's prices", () => {
    const shift = (c: DeviationColumn): DeviationColumn =>
      ({ side: c.side, values: c.values.map((v) => (v as number) + 1000) })
    const a = buildDeviationColorGroups(ONE_LEVEL)
    const b = buildDeviationColorGroups(ONE_LEVEL.map(shift))
    expect(a.perColumn.filter(c => c.side === "upper").flatMap(c => c.groups)).toHaveLength(b.perColumn.filter(c => c.side === "upper").flatMap(c => c.groups).length)
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
    expect(g.perColumn.filter(c => c.side === "upper").flatMap(c => c.groups)).toEqual([7842])
    expect(g.perColumn.filter(c => c.side === "lower").flatMap(c => c.groups)).toEqual([])
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

  it("many columns stay inside the curated palette instead of overflowing", () => {
    // 10 columns x 2 groups. Under the old side-wide numbering this needed 20
    // slots and spilled into generated colours -- which is how four
    // indistinguishable greens reached the screen. Per column it needs 2.
    const cols = Array.from({ length: 10 }, (_, i) => up(i * 100 + 0.5, i * 100 + 1.5))
    const g = buildDeviationColorGroups(cols)
    const seen = cols.flatMap((c, i) => c.values.map((v) => colorFor(g, i, v as number)))
    expect(new Set(seen)).toEqual(new Set([DEFAULT_UPPER_PALETTE[0], DEFAULT_UPPER_PALETTE[1]]))
    for (let i = 0; i < 10; i++) {
      expect(colorFor(g, i, i * 100 + 0.5)).not.toBe(colorFor(g, i, i * 100 + 1.5))
    }
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

  it("custom slot 1 is used by every column, since slots restart", () => {
    const g = buildDeviationColorGroups([up(10.1), up(20.1)], {
      upperPalette: ["#111111", "#222222"],
    })
    expect(colorFor(g, 0, 10.1)).toBe("#111111")
    expect(colorFor(g, 1, 20.1)).toBe("#111111")
  })

  it("custom slots advance WITHIN a column", () => {
    const g = buildDeviationColorGroups([up(10.1, 11.1)], {
      upperPalette: ["#111111", "#222222"],
    })
    expect(colorFor(g, 0, 10.1)).toBe("#111111")
    expect(colorFor(g, 0, 11.1)).toBe("#222222")
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

// ---------------------------------------------------------------------------
// Generated overflow colours must be DISTINGUISHABLE, not merely unequal.
//
// The previous formula stepped by the golden ANGLE (137.5 deg) and took a
// modulo of the 140 deg band, so each successive group advanced by -2.5 deg.
// Slots 11-14 came out at hues 137.6 / 135.1 / 132.6 / 130.1 -- four distinct
// strings that are all the same green on screen. The old test only asserted
// the strings differed, so it passed while the UI was wrong.
// ---------------------------------------------------------------------------
describe("generated colours are far enough apart to see", () => {
  const hueOf = (c: string) => Number(/hsl\(([\d.]+)/.exec(c)?.[1] ?? NaN)

  for (const side of ["upper", "lower"] as const) {
    it(`${side}: consecutive generated hues differ by a visible margin`, () => {
      const base = side === "upper" ? DEFAULT_UPPER_PALETTE : DEFAULT_LOWER_PALETTE
      const hues: number[] = []
      for (let i = base.length; i < base.length + 12; i++) {
        hues.push(hueOf(colorForSlot(side, i)))
      }
      for (let i = 1; i < hues.length; i++) {
        expect(Math.abs(hues[i] - hues[i - 1])).toBeGreaterThan(12)
      }
    })

    it(`${side}: 12 generated colours span most of the band`, () => {
      const base = side === "upper" ? DEFAULT_UPPER_PALETTE : DEFAULT_LOWER_PALETTE
      const hues = Array.from({ length: 12 }, (_, k) => hueOf(colorForSlot(side, base.length + k)))
      // The exact regression: this spread was 7.5 degrees.
      expect(Math.max(...hues) - Math.min(...hues)).toBeGreaterThan(100)
    })

    it(`${side}: no two of 20 generated colours are near-identical`, () => {
      const base = side === "upper" ? DEFAULT_UPPER_PALETTE : DEFAULT_LOWER_PALETTE
      const cols = Array.from({ length: 20 }, (_, k) => colorForSlot(side, base.length + k))
      for (let i = 0; i < cols.length; i++) {
        for (let j = i + 1; j < cols.length; j++) {
          const sameHue = Math.abs(hueOf(cols[i]) - hueOf(cols[j])) < 6
          // Near-equal hues are only acceptable when lightness separates them.
          if (sameHue) expect(cols[i]).not.toBe(cols[j])
        }
      }
    })
  }

  it("reproduces the reported case: 4 sigma levels, no green-on-green", () => {
    // The exact tape from the screenshot: 4 upper columns, 6 rows.
    const cols = [
      up(7781.96, 7782.56, 7783.30, 7782.68, 7790.92, 7782.78),
      up(7785.07, 7785.81, 7786.66, 7785.78, 7795.63, 7785.91),
      up(7788.19, 7789.06, 7790.02, 7788.89, 7800.34, 7789.05),
      up(7791.30, 7792.32, 7793.39, 7792.00, 7805.05, 7792.18),
    ]
    const g = buildDeviationColorGroups(cols)
    // Upper +2.0s held 7791 / 7792 / 7793 / 7805 and painted them all green.
    const last = [7791.30, 7792.32, 7793.39, 7805.05].map((v) => colorFor(g, 3, v))
    expect(new Set(last).size).toBe(4)
    // And they come from the curated palette now, not generated at all.
    for (const c of last) expect(DEFAULT_UPPER_PALETTE).toContain(c as string)
  })
})

// ---------------------------------------------------------------------------
// ONE GROUPING, TWO TABLES
//
// Live state (one row per TIMEFRAME, now) and the Consolidated tape (one row per
// BAR, over time) show the same deviation columns from different angles. Both
// read from a single grouping built from both value sets, so a whole number wears
// one colour across the whole page.
//
// Grouping them separately is the tempting simplification and it breaks the only
// thing the colour is for: 7816 coming out gold in one table and green in the
// other means "same colour" stops implying "same level" the moment your eye moves
// between the two tables.
// ---------------------------------------------------------------------------
describe("Live state and the tape share one grouping", () => {
  // Column order both tables render: [+1s, -1s, +2s, -2s]
  const tapeUpper1 = [7816.4, 7817.9, 7820.1]
  const liveUpper1 = [7816.8, 7822.3]        // 7816 also appears in Live state
  const columns = [
    { side: "upper" as const, values: [...tapeUpper1, ...liveUpper1] },
    { side: "lower" as const, values: [7783.9, 7784.2, 7781.0, 7783.1] },
  ]

  it("gives a whole number ONE colour regardless of which table it came from", () => {
    const g = buildDeviationColorGroups(columns)
    // 7816.4 is a tape value, 7816.8 a Live state value: same integer part.
    expect(colorFor(g, 0, 7816.4)).toBe(colorFor(g, 0, 7816.8))
  })

  it("still separates different whole numbers", () => {
    const g = buildDeviationColorGroups(columns)
    expect(colorFor(g, 0, 7816.4)).not.toBe(colorFor(g, 0, 7817.9))
    expect(colorFor(g, 0, 7816.4)).not.toBe(colorFor(g, 0, 7822.3))
  })

  it("a value only present in Live state still gets a colour", () => {
    // It would be null if the grouping had been built from the tape alone --
    // which is exactly the bug this shared grouping avoids.
    const g = buildDeviationColorGroups(columns)
    expect(colorFor(g, 0, 7822.3)).not.toBeNull()
  })

  it("upper and lower still never share a colour across the page", () => {
    const g = buildDeviationColorGroups(columns)
    const uppers = [7816.4, 7817.9, 7820.1, 7822.3].map((v) => colorFor(g, 0, v))
    const lowers = [7783.9, 7781.0].map((v) => colorFor(g, 1, v))
    for (const u of uppers) expect(lowers).not.toContain(u)
  })

  it("each column is still grouped on its own", () => {
    // A whole number shared between +1s and +2s is coincidence, not agreement,
    // so the two columns are allowed to colour it differently.
    const same = [
      { side: "upper" as const, values: [7816.2] },
      { side: "upper" as const, values: [7816.7] },
    ]
    const g = buildDeviationColorGroups(same)
    expect(g.perColumn.length).toBe(2)
    expect(g.byColumn[0].get(7816)).toBeDefined()
    expect(g.byColumn[1].get(7816)).toBeDefined()
  })

  it("an empty tape does not stop Live state values being coloured", () => {
    // Before Play is pressed the tape is empty but the panes may already hold
    // bands, so the grouping must cope with only the Live state half present.
    const g = buildDeviationColorGroups([
      { side: "upper" as const, values: liveUpper1 },
      { side: "lower" as const, values: [] },
    ])
    expect(colorFor(g, 0, 7816.8)).not.toBeNull()
    expect(colorFor(g, 1, 7783.9)).toBeNull()   // nothing in that column yet
  })
})
