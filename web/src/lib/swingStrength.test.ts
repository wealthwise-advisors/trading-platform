import { describe, expect, it } from "vitest"
import { strengthLines, swingAt, swingStrength, type SwingSpan } from "./swingStrength"
import type { OHLCVRecord } from "./types"

const T = (m: number) => `2026-11-09T10:${String(m).padStart(2, "0")}:00`
const bar = (m: number, o: number, h: number, l: number, c: number, v: number | null): OHLCVRecord =>
  ({ t: T(m), o, h, l, c, v })

describe("swingStrength", () => {
  // Minute 0 is the first pivot's bar and belongs to the move before.
  const bars = [
    bar(0, 10, 20, 0, 0, 9999),     // excluded: pivot A's own bar
    bar(1, 10, 20, 10, 20, 1000),   // green, closes on the high: 1000 buyers
    bar(2, 20, 20, 10, 15, 400),    // red, mid-range: 200 / 200
    bar(3, 15, 15, 5, 5, 600),      // red, closes on the low: 600 sellers
    bar(4, 5, 9, 5, 9, 1),          // after B: excluded
  ]

  it("splits each candle's volume by sir's formula and adds it up", () => {
    const s = swingStrength(bars, T(0), T(3))!
    expect(s.candles).toBe(3)
    expect(s.buyers.volume).toBe(1200)
    expect(s.sellers.volume).toBe(800)
    expect(s.buyers.pct).toBeCloseTo(60)
    expect(s.stronger).toBe("buyers")
  })

  it("counts green and red candles, and averages volume per candle", () => {
    const s = swingStrength(bars, T(0), T(3))!
    expect([s.green, s.red]).toEqual([1, 2])
    expect(s.buyers.avgPerCandle).toBeCloseTo(400)
    expect(s.sellers.avgPerCandle).toBeCloseTo(266.67, 1)
  })

  it("volume decides, not the number of candles", () => {
    // More red candles, but the green one carries more volume.
    expect(swingStrength(bars, T(0), T(3))!.stronger).toBe("buyers")
  })

  it("sellers win when they carry more volume", () => {
    expect(swingStrength(bars, T(1), T(3))!.stronger).toBe("sellers")
  })

  it("without volume, the candle count decides", () => {
    const noVol = bars.map((b) => ({ ...b, v: null }))
    expect(swingStrength(noVol, T(0), T(3))!.stronger).toBe("sellers")
  })

  it("an empty stretch has nothing to say", () => {
    expect(swingStrength(bars, T(3), T(3))).toBeNull()
  })
})

describe("strengthLines", () => {
  it("names the stronger side in its colour", () => {
    const lines = strengthLines("10 Leg Dev (A to B)", swingStrength(
      [bar(1, 1, 2, 1, 2, 100)], T(0), T(1)), "#fff")
    expect(lines[0].label).toBe("10 Leg Dev (A to B)")
    expect(lines.find((l) => l.label === "Stronger")?.value).toBe("BUYERS (green)")
    expect(lines.find((l) => l.label === "Buyers")?.value).toBe("100 (100%)")
  })

  it("says so when the stretch is empty", () => {
    expect(strengthLines("x", null, "#fff")[1].label).toBe("No bars in this stretch")
  })
})

describe("swingAt", () => {
  const span = (swing: number, a: number, b: number): SwingSpan => ({
    swing, color: "#fff", start: T(a), end: T(b), tenLeg: { from: T(a), to: T(b), label: "A to B" }, threeLeg: null,
  })
  const spans = [span(1, 0, 10), span(2, 10, 20)]

  it("finds the swing whose region holds the bar", () => {
    expect(swingAt(spans, T(5))?.swing).toBe(1)
    expect(swingAt(spans, T(10))?.swing).toBe(2)
    expect(swingAt(spans, T(20))?.swing).toBe(2)
  })

  it("nothing outside every swing", () => {
    expect(swingAt(spans, T(30))).toBeNull()
  })
})
