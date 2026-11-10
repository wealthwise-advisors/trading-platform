import { describe, expect, it } from "vitest"
import { dominance, dominanceTag, strengthLines, swingAt, swingStrength, type SwingSpan } from "./swingStrength"
import type { OHLCVRecord } from "./types"

const T = (m: number) => `2026-11-09T10:${String(m).padStart(2, "0")}:00`
const bar = (m: number, o: number, h: number, l: number, c: number, v: number | null): OHLCVRecord =>
  ({ t: T(m), o, h, l, c, v })

describe("swingStrength -- sir's running total", () => {
  // Minute 0 is the first pivot's bar and belongs to the move before.
  const bars = [
    bar(0, 10, 20, 0, 0, 9999),                       // excluded: pivot A's own bar
    bar(1, 10, 20, 10, 20, 1000),                     // buyers 1,000 / sellers 0     -> +1,000
    bar(2, 7568.25, 7568.75, 7567, 7567.25, 1959),    // buyers 280 / sellers 1,679   -> -1,679
    bar(3, 7572, 7575.75, 7572, 7575.5, 2606),        // buyers 2,432 / sellers 174   -> +2,432
    bar(4, 5, 9, 5, 9, 1),                            // after B: excluded
  ]

  it("adds the higher side when green, subtracts it when red, and keeps the total", () => {
    const s = swingStrength(bars, T(0), T(3))!
    expect(s.added).toBe(3432)
    expect(s.subtracted).toBe(1679)
    expect(s.net).toBe(1753)
    expect(s.stronger).toBe("green")
    expect([s.greenLed, s.redLed, s.candles]).toEqual([2, 1, 3])
  })

  it("a negative total is red", () => {
    const s = swingStrength(bars, T(1), T(2))!
    expect(s.net).toBe(-1679)
    expect(s.stronger).toBe("red")
  })

  it("an even candle adds nothing", () => {
    const s = swingStrength([bar(1, 5, 10, 0, 5, 100)], T(0), T(1))!
    expect([s.net, s.greenLed, s.redLed, s.stronger]).toEqual([0, 0, 0, "even"])
  })

  it("nothing is averaged: the total grows with the candles", () => {
    const one = swingStrength([bar(1, 1, 2, 1, 2, 100)], T(0), T(1))!
    const two = swingStrength([bar(1, 1, 2, 1, 2, 100), bar(2, 1, 2, 1, 2, 100)], T(0), T(2))!
    expect([one.net, two.net]).toEqual([100, 200])
  })

  it("no volume is said plainly, not called even", () => {
    const s = swingStrength(bars.map((b) => ({ ...b, v: null })), T(0), T(3))!
    expect(s.hasVolume).toBe(false)
    expect(strengthLines("x", s)[1].label).toBe("No volume data")
  })

  it("an empty stretch has nothing to say", () => {
    expect(swingStrength(bars, T(3), T(3))).toBeNull()
  })
})

describe("strengthLines", () => {
  const lines = strengthLines("10 Leg Dev (A to B)", swingStrength(
    [bar(1, 10, 20, 10, 20, 1000), bar(2, 7568.25, 7568.75, 7567, 7567.25, 1959)], T(0), T(2)),
    { from: 7500, to: 7476.5 })
  const line = (label: string) => lines.find((l) => l.label === label)

  it("five bullets under a heading: buyers, sellers, net, dominant, price change", () => {
    expect(lines[0]).toMatchObject({ label: "10 Leg Dev (A to B)", kind: "heading" })
    expect(lines.slice(1).map((l) => l.label)).toEqual(["Buyers", "Sellers", "Net", "Dominant", "Price change"])
    expect(lines.slice(1).every((l) => l.bullet)).toBe(true)
    expect(line("Buyers")?.value).toBe("+1,000 (37%)")
    expect(line("Sellers")?.value).toBe("-1,679 (63%)")
    expect(line("Net")?.value).toBe("-679")
    expect(line("Dominant")?.value).toBe("SELLERS · Moderate")
    expect(line("Price change")?.value).toBe("▼ -23.50 pts")
  })

  it("only the numbers and the verdict carry colour", () => {
    expect(lines.every((l) => l.color === undefined)).toBe(true)
    expect(line("Buyers")?.valueColor).toBe("#00c853")
    expect(line("Dominant")?.valueColor).toBe("#ff6b6b")
  })

  it("no price change line without the pivots' prices", () => {
    const s = swingStrength([bar(1, 1, 2, 1, 2, 100)], T(0), T(1))
    expect(strengthLines("x", s).map((l) => l.label)).not.toContain("Price change")
    expect(strengthLines("x", s, { from: 1, to: 3.25 }).at(-1)?.value).toBe("▲ +2.25 pts")
  })

  it("says so when the stretch is empty", () => {
    expect(strengthLines("x", null)[1].label).toBe("No bars in this stretch")
  })
})

describe("dominance", () => {
  const of = (added: number, subtracted: number) => dominance({
    candles: 1, greenLed: 1, redLed: 1, added, subtracted, net: added - subtracted, hasVolume: true,
    stronger: added > subtracted ? "green" : added < subtracted ? "red" : "even",
  })

  it.each([[90, 10, "buyers", "Strong"], [65, 35, "buyers", "Strong"], [60, 40, "buyers", "Moderate"],
           [52, 48, "buyers", "Slight"], [30, 70, "sellers", "Strong"]] as const)(
    "%s / %s -> %s, %s", (a, b, side, strength) => {
      expect(of(a, b)).toMatchObject({ side, strength })
    },
  )

  it("an even split has no strength", () => expect(of(50, 50)).toMatchObject({ side: "even", strength: null }))
})

describe("dominanceTag", () => {
  it("an arrow and the winning side, STRONG when it is", () => {
    const strong = swingStrength([bar(1, 10, 20, 10, 20, 1000)], T(0), T(1))
    expect(dominanceTag(strong)).toEqual({ text: "▲ BUYERS · STRONG", color: "#00c853" })
    // +60 (buyers 60 / 40) then -55 (sellers 55 / 45): buyers win with 52%.
    const slight = swingStrength([bar(1, 10, 20, 10, 16, 100), bar(2, 10, 20, 10, 14.5, 100)], T(0), T(2))
    expect(dominanceTag(slight)?.text).toBe("▲ BUYERS")
  })

  it("nothing to tag without volume", () => {
    expect(dominanceTag(swingStrength([bar(1, 1, 2, 1, 2, null)], T(0), T(1)))).toBeNull()
  })
})

describe("swingAt", () => {
  const span = (swing: number, a: number, b: number): SwingSpan => ({
    swing, color: "#fff", start: T(a), end: T(b),
    tenLeg: { from: T(a), to: T(b), label: "A to B", fromPrice: 0, toPrice: 0 }, threeLeg: null,
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
