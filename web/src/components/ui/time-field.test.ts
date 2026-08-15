import { describe, it, expect } from "vitest"
import { parse, display, stepHour, stepMinute, togglePeriod } from "@/lib/clock"

/**
 * The whole reason this component exists is that a 24-hour reading has to be
 * converted in the head, and the conversion is easy to get wrong at exactly two
 * points: midnight and noon. Both map to 12, and both are off-by-twelve in the
 * naive `h % 12` version. These pin every boundary.
 */
describe("TimeField 24h <-> 12h display", () => {
  const show = (v: string) => {
    const { h, m } = parse(v)
    const d = display(h, m)
    return `${String(d.h12).padStart(2, "0")}:${d.mm} ${d.period}`
  }

  it("renders midnight as 12 AM, not 00 AM", () => {
    expect(show("00:00")).toBe("12:00 AM")
    expect(show("00:30")).toBe("12:30 AM")
  })

  it("renders noon as 12 PM, not 00 PM", () => {
    expect(show("12:00")).toBe("12:00 PM")
    expect(show("12:45")).toBe("12:45 PM")
  })

  it("renders the session defaults the way a trader says them", () => {
    expect(show("09:30")).toBe("09:30 AM")   // RTH open
    expect(show("16:00")).toBe("04:00 PM")   // RTH close
    expect(show("18:00")).toBe("06:00 PM")   // overnight open
    expect(show("17:00")).toBe("05:00 PM")   // overnight close
  })

  it("keeps AM below noon and PM at or above it, across the whole day", () => {
    for (let h = 0; h < 24; h++) {
      const { period, h12 } = display(h, 0)
      expect(period).toBe(h < 12 ? "AM" : "PM")
      expect(h12).toBeGreaterThanOrEqual(1)
      expect(h12).toBeLessThanOrEqual(12)
    }
  })

  it("round-trips every minute of the day back to the same 24h value", () => {
    for (let h = 0; h < 24; h++) {
      for (const m of [0, 1, 29, 30, 59]) {
        const v = `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`
        const p = parse(v)
        expect(p.h).toBe(h)
        expect(p.m).toBe(m)
        // 12-hour reading must be reversible
        const d = display(p.h, p.m)
        const back = d.period === "AM"
          ? (d.h12 === 12 ? 0 : d.h12)
          : (d.h12 === 12 ? 12 : d.h12 + 12)
        expect(back).toBe(h)
      }
    }
  })

  it("clamps nonsense rather than rendering NaN", () => {
    expect(show("")).toBe("12:00 AM")
    expect(show("99:99")).toBe("11:59 PM")
  })
})

/**
 * Stepper behaviour. The minute arrow originally moved 5 minutes per click,
 * which made 6:21 unreachable -- a single-arrow stepper has to mean one unit.
 */
describe("TimeField steppers", () => {
  it("moves the minute by exactly one per click", () => {
    let v = "06:20"
    const seen: string[] = []
    for (let i = 0; i < 5; i++) { v = stepMinute(v, 1); seen.push(v) }
    expect(seen).toEqual(["06:21", "06:22", "06:23", "06:24", "06:25"])
  })

  it("moves the minute down by exactly one per click", () => {
    let v = "06:20"
    const seen: string[] = []
    for (let i = 0; i < 3; i++) { v = stepMinute(v, -1); seen.push(v) }
    expect(seen).toEqual(["06:19", "06:18", "06:17"])
  })

  it("carries the hour when minutes roll past the boundary", () => {
    expect(stepMinute("06:59", 1)).toBe("07:00")
    expect(stepMinute("07:00", -1)).toBe("06:59")
    expect(stepMinute("23:59", 1)).toBe("00:00")   // wraps the day
    expect(stepMinute("00:00", -1)).toBe("23:59")
  })

  it("returns to where it started after up-then-down", () => {
    for (const start of ["00:00", "06:20", "09:30", "12:00", "16:00", "23:59"]) {
      expect(stepMinute(stepMinute(start, 1), -1)).toBe(start)
      expect(stepHour(stepHour(start, 1), -1)).toBe(start)
    }
  })

  it("keeps the hour arrows inside the current half of the day", () => {
    // 11 AM up must give 12 AM, not 12 PM -- only the AM/PM button crosses over
    expect(stepHour("11:30", 1)).toBe("00:30")
    expect(stepHour("00:30", -1)).toBe("11:30")
    expect(stepHour("23:30", 1)).toBe("12:30")
    expect(stepHour("12:30", -1)).toBe("23:30")
  })

  it("leaves minutes untouched when stepping hours", () => {
    expect(stepHour("09:37", 1)).toBe("10:37")
    expect(stepHour("09:37", -1)).toBe("08:37")
  })

  it("toggles AM/PM without changing the clock reading", () => {
    expect(togglePeriod("09:30")).toBe("21:30")
    expect(togglePeriod("21:30")).toBe("09:30")
    expect(togglePeriod("00:15")).toBe("12:15")
    expect(togglePeriod("12:15")).toBe("00:15")
  })
})
