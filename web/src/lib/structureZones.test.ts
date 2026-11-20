import { describe, expect, it } from "vitest"
import { avgWord, structureZones } from "./structureZones"

describe("structureZones -- sir's four zones across the timeframes", () => {
  const rows = [
    { vwap: 7428.23, poc: 7436.89, vah: 7450.69, val: 7413.19 },
    { vwap: 7425.33, poc: 7424.08, vah: 7437.53, val: 7394.77 },
    { vwap: 7426.0, poc: 7431.77, vah: 7444.0, val: 7400.0 },
  ]
  const z = structureZones(rows)

  it("resistance: VA High's high and average", () => {
    expect(z.resistance!.high).toBe(7450.69)
    expect(z.resistance!.avg).toBeCloseTo((7450.69 + 7437.53 + 7444) / 3, 6)
  })

  it("breakout: from the highest VWAP to the lowest VA High", () => {
    expect(z.breakout).toEqual({ vwapHigh: 7428.23, vahLow: 7437.53 })
  })

  it("equilibrium core and support floor: high, average, low", () => {
    expect([z.core!.high, z.core!.low]).toEqual([7436.89, 7424.08])
    expect([z.support!.high, z.support!.low]).toEqual([7413.19, 7394.77])
    expect(z.support!.avg).toBeCloseTo((7413.19 + 7394.77 + 7400) / 3, 6)
  })

  it("missing values are skipped; nothing at all gives no zone", () => {
    expect(structureZones([{ poc: 7400 }, { poc: null }]).core).toEqual({ high: 7400, avg: 7400, low: 7400 })
    expect(structureZones([{}])).toEqual({ resistance: null, breakout: null, core: null, support: null })
  })
})

describe("avgWord", () => {
  it.each([["above", "High"], ["below", "Low"], ["equal", "Neutral"]] as const)("%s -> %s", (side, word) => {
    expect(avgWord(side)).toBe(word)
  })
})
