/**
 * POC one-sidedness across timeframes.
 *
 * The scenario in the first test is the one this feature was asked for, kept
 * verbatim: some timeframes' POC above 7842.75, the rest below it, and the two
 * groups each identifiable by a single colour.
 */
import { describe, expect, it } from "vitest"

import {
  DEFAULT_POC_PALETTE,
  POC_SIDE_COLOR,
  buildPocConsensus,
  pocConsensusLabel,
  pocLevelColor,
  sideOf,
} from "./pocConsensus"

const rows = (m: Record<string, number | null>) =>
  Object.entries(m).map(([tf, poc]) => ({ tf, poc }))

describe("sideOf", () => {
  it("decides on the whole number, not the raw float", () => {
    // THE CONTRADICTION THIS PREVENTS. deviationColors groups 7842.75 and
    // 7842.10 as the SAME level. If the side were taken from the float, the
    // side column would call one of them ABOVE while the colour grouping one
    // cell to its left called them equal.
    expect(sideOf(7842.75, 7842.1)).toBe("at")
    expect(sideOf(7842.1, 7842.75)).toBe("at")
    expect(sideOf(7843.0, 7842.75)).toBe("above")
    expect(sideOf(7841.99, 7842.0)).toBe("below")
  })

  it("truncates toward zero, so negatives do not flip sides", () => {
    // Math.floor would put -1.2 on a different level from -1.8.
    expect(sideOf(-1.2, -1.8)).toBe("at")
    expect(sideOf(-1.2, -2.6)).toBe("above")
  })
})

describe("buildPocConsensus", () => {
  it("splits the asked-for case into two identifiable groups", () => {
    const c = buildPocConsensus(
      rows({
        "1m": 7845.25, "30m": 7844.0, "45m": 7843.5,
        "5m": 7840.75, "15m": 7839.0, "1h": 7841.25, "4h": 7838.5,
      }),
      7842.75,
    )
    expect(c.above.sort()).toEqual(["1m", "30m", "45m"])
    expect(c.below.sort()).toEqual(["15m", "1h", "4h", "5m"])
    expect(c.at).toEqual([])
    expect(c.counted).toBe(7)
    expect(c.oneSided).toBe(false)
    expect(c.dominantSide).toBe("below")
    // One colour per side, so a group is read by scanning the column.
    for (const tf of c.above) expect(POC_SIDE_COLOR[c.sides.get(tf)!]).toBe(POC_SIDE_COLOR.above)
    for (const tf of c.below) expect(POC_SIDE_COLOR[c.sides.get(tf)!]).toBe(POC_SIDE_COLOR.below)
    expect(POC_SIDE_COLOR.above).not.toBe(POC_SIDE_COLOR.below)
    expect(pocConsensusLabel(c)).toBe("3↑ / 4↓")
  })

  it("flags a genuinely one-sided table", () => {
    const c = buildPocConsensus(
      rows({ "1m": 7850.0, "5m": 7851.5, "15m": 7849.25, "1h": 7855.0 }),
      7842.75,
    )
    expect(c.oneSided).toBe(true)
    expect(c.dominantSide).toBe("above")
    expect(pocConsensusLabel(c)).toBe("ONE-SIDED ↑ 4/4")
  })

  it("a POC sitting ON the reference level breaks one-sidedness", () => {
    // Everything else is above, but 7842.30 is the reference's own level, so
    // the table is not agreeing on a direction -- one row has no direction.
    const c = buildPocConsensus(
      rows({ "1m": 7850.0, "5m": 7851.5, "15m": 7842.3 }),
      7842.75,
    )
    expect(c.at).toEqual(["15m"])
    expect(c.oneSided).toBe(false)
    expect(c.dominantSide).toBe("above")
  })

  it("spells out the all-on-level case instead of a bare glyph count", () => {
    // The glyph format would render this as "3•", which reads as a typo.
    const c = buildPocConsensus(
      rows({ "1m": 7842.75, "5m": 7842.1, "15m": 7842.99 }),
      7842.5,
    )
    expect(c.at.length).toBe(3)
    expect(pocConsensusLabel(c)).toBe("3 ON LEVEL")
  })

  it("one timeframe is never a consensus", () => {
    const c = buildPocConsensus(rows({ "1m": 7850.0 }), 7842.75)
    expect(c.counted).toBe(1)
    expect(c.oneSided).toBe(false)
    expect(pocConsensusLabel(c)).toBeNull()
  })

  it("an exact tie names no dominant side", () => {
    const c = buildPocConsensus(
      rows({ "1m": 7850.0, "5m": 7851.0, "15m": 7830.0, "1h": 7831.0 }),
      7842.75,
    )
    expect(c.dominantSide).toBeNull()
    expect(c.oneSided).toBe(false)
  })

  it("skips timeframes with no profile instead of defaulting them", () => {
    const c = buildPocConsensus(
      [
        { tf: "1m", poc: 7850.0 },
        { tf: "5m", poc: null },
        { tf: "15m", poc: undefined },
        { tf: "1h", poc: Number.NaN },
        { tf: "4h", poc: 7851.0 },
      ],
      7842.75,
    )
    expect(c.counted).toBe(2)
    expect(c.sides.has("5m")).toBe(false)
    expect(c.sides.has("1h")).toBe(false)
    expect(c.oneSided).toBe(true)
  })

  it("without a reference it still groups levels but takes no sides", () => {
    const c = buildPocConsensus(rows({ "1m": 7850.0, "5m": 7850.4 }), null)
    expect(c.reference).toBeNull()
    expect(c.sides.size).toBe(0)
    expect(c.counted).toBe(0)
    expect(pocConsensusLabel(c)).toBeNull()
    // The level grouping does not depend on the reference.
    expect(pocLevelColor(c, 7850.0)).toBe(pocLevelColor(c, 7850.4))
  })
})

describe("pocLevelColor", () => {
  it("shares a colour across timeframes on the same level, and only then", () => {
    const c = buildPocConsensus(
      rows({ "1m": 7842.75, "5m": 7842.1, "15m": 7841.96 }),
      7842.75,
    )
    expect(pocLevelColor(c, 7842.75)).toBe(pocLevelColor(c, 7842.1))
    expect(pocLevelColor(c, 7842.75)).not.toBe(pocLevelColor(c, 7841.96))
  })

  it("opens on the pre-grouping sky blue, so a single-level table is unchanged", () => {
    const c = buildPocConsensus(rows({ "1m": 7842.75, "5m": 7842.1 }), 7842.75)
    expect(c.levelColors.size).toBe(1)
    expect(pocLevelColor(c, 7842.75)).toBe(DEFAULT_POC_PALETTE[0])
    expect(DEFAULT_POC_PALETTE[0]).toBe("#38bdf8")
  })

  it("colours by the Nth-LOWEST level, so order is price order not arrival", () => {
    const a = buildPocConsensus(rows({ "1m": 7845.0, "5m": 7840.0 }), 7842.75)
    const b = buildPocConsensus(rows({ "1m": 7840.0, "5m": 7845.0 }), 7842.75)
    expect(pocLevelColor(a, 7840.0)).toBe(pocLevelColor(b, 7840.0))
    expect(pocLevelColor(a, 7845.0)).toBe(pocLevelColor(b, 7845.0))
    expect(pocLevelColor(a, 7840.0)).toBe(DEFAULT_POC_PALETTE[0])
  })

  it("gives every level on screen a distinct colour, past the palette", () => {
    const many = Object.fromEntries(
      Array.from({ length: 14 }, (_, i) => [`tf${i}`, 7800 + i]),
    )
    const c = buildPocConsensus(rows(many), 7842.75)
    const colors = [...c.levelColors.values()]
    expect(colors.length).toBe(14)
    expect(new Set(colors).size).toBe(14)
  })

  it("returns null for a missing POC rather than a palette colour", () => {
    const c = buildPocConsensus(rows({ "1m": 7842.75 }), 7842.75)
    expect(pocLevelColor(c, null)).toBeNull()
    expect(pocLevelColor(c, Number.NaN)).toBeNull()
  })
})
