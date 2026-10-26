import { describe, expect, it } from "vitest"
import { profileWindowStart as start } from "./profileWindow"

const profileWindowStart = (times: string[], upto: number, tf: string) =>
  start(times.map((t) => ({ t })), upto, tf)

/** Bars every `step` hours from 2026-10-01 00:00 for `days` days. */
function hourly(days: number, step = 1): string[] {
  const out: string[] = []
  for (let d = 0; d < days; d++) {
    for (let h = 0; h < 24; h += step) {
      const day = String(1 + d).padStart(2, "0")
      out.push(`2026-10-${day}T${String(h).padStart(2, "0")}:00:00`)
    }
  }
  return out
}

describe("profileWindowStart", () => {
  const bars = hourly(25)            // 2026-10-01 .. 2026-10-25, 24 bars a day

  it("limits a timeframe to its own specified calendar days", () => {
    // 5m is 2 D: the last two dates of the range, 10-24 and 10-25.
    const i = profileWindowStart(bars, bars.length, "5m")
    expect(bars[i]).toBe("2026-10-24T00:00:00")
    expect(bars.length - i).toBe(48)
    // 15m is 4 D, 30m 15 D.
    expect(bars[profileWindowStart(bars, bars.length, "15m")]).toBe("2026-10-22T00:00:00")
    expect(bars[profileWindowStart(bars, bars.length, "30m")]).toBe("2026-10-11T00:00:00")
  })

  it("keeps the whole range when the window covers it", () => {
    expect(profileWindowStart(bars, bars.length, "1h")).toBe(0)   // 25 D over 25 days
    expect(profileWindowStart(bars, bars.length, "4h")).toBe(0)   // 180 D
  })

  it("counts back from the bar being profiled, not the end of the range", () => {
    // Profile as it stood at the 10th day's last bar: 5m covers 10-09 and 10-10.
    const upto = 24 * 10
    const i = profileWindowStart(bars, upto, "5m")
    expect(bars[i]).toBe("2026-10-09T00:00:00")
    expect(upto - i).toBe(48)
  })

  it("leaves timeframes with no specified range on the whole loaded range", () => {
    for (const tf of ["3m", "25m", "35m"]) expect(profileWindowStart(bars, bars.length, tf)).toBe(0)
  })

  it("counts calendar days across a gap with no bars", () => {
    // 10-03 and 10-04 have no bars (a weekend): 2 D ending 10-05 is 10-04..10-05.
    const gappy = bars.filter((t) => t < "2026-10-03" || t >= "2026-10-05")
    const upto = gappy.findIndex((t) => t >= "2026-10-06")
    expect(gappy[profileWindowStart(gappy, upto, "5m")]).toBe("2026-10-05T00:00:00")
  })

  it("handles empty input", () => {
    expect(profileWindowStart([], 0, "5m")).toBe(0)
  })
})
