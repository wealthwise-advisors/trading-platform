// computeRangebreaks had the same latent timestamp-convention defect as the
// candlestick trace: it parsed naive wall-clock strings with Date.parse (which
// reads them as local) and re-serialized the gap bounds with toISOString()
// (which forces UTC). Plotly would then cut the axis at spans shifted by the
// browser's UTC offset -- removing time that still had bars in it and keeping
// the empty overnight stretch.
//
// It never surfaced because a single-day chart has no gaps for it to emit.

import { describe, it, expect } from "vitest"
import { computeRangebreaks } from "@/lib/rangebreaks"
import { toNaiveString } from "@/lib/isoTime"

/** Two 09:30-16:00 sessions of 5m bars, with the overnight gap between them. */
function twoSessions(): string[] {
  const out: string[] = []
  for (const day of ["2026-08-10", "2026-08-11"]) {
    const t0 = Date.parse(`${day}T09:30:00`)
    for (let i = 0; i * 5 <= 390; i++) out.push(toNaiveString(t0 + i * 5 * 60_000))
  }
  return out
}

describe("computeRangebreaks", () => {
  it("returns nothing when the series is continuous", () => {
    const t0 = Date.parse("2026-08-10T09:30:00")
    const times = Array.from({ length: 60 }, (_, i) => toNaiveString(t0 + i * 5 * 60_000))
    expect(computeRangebreaks(times)).toEqual([])
  })

  it("returns nothing for a degenerate series", () => {
    expect(computeRangebreaks([])).toEqual([])
    expect(computeRangebreaks(["2026-08-10T09:30:00"])).toEqual([])
  })

  it("emits one break for the overnight gap between two sessions", () => {
    const breaks = computeRangebreaks(twoSessions())
    expect(breaks).toHaveLength(1)
  })

  it("THE BUG: bounds are naive, matching the timestamps they came from", () => {
    for (const b of computeRangebreaks(twoSessions())) {
      for (const bound of b.bounds) {
        expect(bound).not.toMatch(/Z$/)
        expect(bound).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/)
      }
    }
  })

  it("THE BUG: the break covers the actual gap, not a UTC-shifted one", () => {
    // This is the assertion that fails if toISOString() comes back: the bounds
    // must sit between the last bar of session 1 and the first of session 2.
    const times = twoSessions()
    const breaks = computeRangebreaks(times)
    expect(breaks).toHaveLength(1)
    const [lo, hi] = breaks[0].bounds.map((b) => Date.parse(b.replace(" ", "T")))

    const lastOfDay1 = Date.parse("2026-08-10T16:00:00")
    const firstOfDay2 = Date.parse("2026-08-11T09:30:00")
    expect(lo).toBeGreaterThan(lastOfDay1)
    expect(hi).toBeLessThanOrEqual(firstOfDay2)

    // And no real bar may fall inside the removed span -- a shifted break
    // would swallow live bars from the start of the next session.
    for (const t of times) {
      const ms = Date.parse(t)
      expect(ms >= lo && ms < hi).toBe(false)
    }
  })

  it("starts one step after the last bar so it keeps its full width", () => {
    const breaks = computeRangebreaks(twoSessions())
    const lo = Date.parse(breaks[0].bounds[0].replace(" ", "T"))
    expect(lo).toBe(Date.parse("2026-08-10T16:05:00"))
  })

  it("handles Z-suffixed input by keeping that convention", () => {
    const zoned = twoSessions().map((t) => new Date(Date.parse(t)).toISOString())
    const breaks = computeRangebreaks(zoned)
    expect(breaks).toHaveLength(1)
    // Round-tripped through UTC, the bounds must still bracket the real gap.
    const [lo, hi] = breaks[0].bounds.map((b) => Date.parse(b.replace(" ", "T") + "Z"))
    for (const t of zoned) {
      const ms = Date.parse(t)
      expect(ms >= lo && ms < hi).toBe(false)
    }
  })
})
