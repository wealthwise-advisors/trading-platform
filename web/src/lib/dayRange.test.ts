import { describe, it, expect } from "vitest"
import {
  daysInRange, endDateForDays, startDateForDays, clampDays, steppedEndDate,
  MIN_RANGE_DAYS, MAX_RANGE_DAYS,
} from "./dayRange"

describe("day count is inclusive of both dates", () => {
  it("same date on both sides is one day, not zero", () => {
    expect(daysInRange("2026-08-12", "2026-08-12")).toBe(1)
  })

  it("matches the spec example: 12 Aug + 4 days ends on the 15th", () => {
    expect(endDateForDays("2026-08-12", 4)).toBe("2026-08-15")
    expect(daysInRange("2026-08-12", "2026-08-15")).toBe(4)
  })

  for (const [days, end] of [
    [1, "2026-08-12"], [2, "2026-08-13"], [4, "2026-08-15"],
    [7, "2026-08-18"], [10, "2026-08-21"], [30, "2026-09-10"],
  ] as const) {
    it(`${days} day(s) from 2026-08-12 ends ${end}`, () => {
      expect(endDateForDays("2026-08-12", days)).toBe(end)
      expect(daysInRange("2026-08-12", end)).toBe(days)
    })
  }
})

describe("round trip", () => {
  it("endDateForDays and daysInRange invert each other", () => {
    for (let n = 1; n <= 60; n++) {
      const end = endDateForDays("2026-03-01", n)!
      expect(daysInRange("2026-03-01", end)).toBe(n)
    }
  })

  it("startDateForDays counts back from the end", () => {
    expect(startDateForDays("2026-08-15", 4)).toBe("2026-08-12")
    expect(startDateForDays("2026-08-12", 1)).toBe("2026-08-12")
  })
})

describe("calendar edges", () => {
  it("crosses a month boundary", () => {
    expect(endDateForDays("2026-01-30", 4)).toBe("2026-02-02")
  })

  it("crosses a year boundary", () => {
    expect(endDateForDays("2026-12-30", 4)).toBe("2027-01-02")
  })

  it("handles a leap day", () => {
    // 2028 is a leap year.
    expect(endDateForDays("2028-02-27", 4)).toBe("2028-03-01")
    expect(daysInRange("2028-02-27", "2028-03-01")).toBe(4)
  })

  it("is unaffected by local timezone — dates are parsed as UTC", () => {
    // A naive `new Date("2026-08-12")` in a negative-offset zone can land on
    // the 11th. Every case above would shift by one if that leaked in.
    expect(endDateForDays("2026-08-12", 1)).toBe("2026-08-12")
    expect(endDateForDays("2026-01-01", 1)).toBe("2026-01-01")
    expect(endDateForDays("2026-12-31", 1)).toBe("2026-12-31")
  })
})

describe("weekends are counted as calendar days, not skipped", () => {
  it("Fri + 3 days lands on Sunday, per the documented convention", () => {
    // 2026-08-14 is a Friday.
    expect(endDateForDays("2026-08-14", 3)).toBe("2026-08-16")
    // NOT 2026-08-18, which is what trading-day semantics would give.
  })

  it("a 7-day range spanning a weekend is still 7 days", () => {
    expect(daysInRange("2026-08-14", "2026-08-20")).toBe(7)
  })
})

describe("clamping", () => {
  it("never goes below 1", () => {
    expect(clampDays(0)).toBe(MIN_RANGE_DAYS)
    expect(clampDays(-5)).toBe(MIN_RANGE_DAYS)
  })

  it("never exceeds the provider's lookback", () => {
    expect(clampDays(MAX_RANGE_DAYS + 1)).toBe(MAX_RANGE_DAYS)
    expect(clampDays(100_000)).toBe(MAX_RANGE_DAYS)
  })

  it("the cap mirrors INTRADAY_LOOKBACK_DAYS", () => {
    expect(MAX_RANGE_DAYS).toBe(180)
  })

  it("rejects NaN and non-integers rather than passing them on", () => {
    expect(clampDays(3.7)).toBe(3)
  })

  it("treats any non-finite value as the MINIMUM, not the maximum", () => {
    // Deliberately conservative: a NaN or Infinity arriving from a broken
    // input should never turn into a request for six months of intraday
    // data. Falling back to one day is cheap and obviously wrong on screen;
    // falling back to 180 is expensive and looks plausible.
    expect(clampDays(NaN)).toBe(MIN_RANGE_DAYS)
    expect(clampDays(Infinity)).toBe(MIN_RANGE_DAYS)
    expect(clampDays(-Infinity)).toBe(MIN_RANGE_DAYS)
  })

  it("endDateForDays clamps too, so a bad count cannot produce a bad range", () => {
    expect(endDateForDays("2026-08-12", 0)).toBe("2026-08-12")
    expect(endDateForDays("2026-08-12", -9)).toBe("2026-08-12")
    expect(endDateForDays("2026-08-12", 9999)).toBe(endDateForDays("2026-08-12", MAX_RANGE_DAYS))
  })
})

describe("invalid dates leave the range alone", () => {
  for (const bad of ["", "   ", "not-a-date", "2026-8-12", "12-08-2026", "2026-13-45"]) {
    it(`daysInRange returns null for ${JSON.stringify(bad)}`, () => {
      expect(daysInRange(bad, "2026-08-12")).toBeNull()
      expect(daysInRange("2026-08-12", bad)).toBeNull()
    })
    it(`endDateForDays returns null for ${JSON.stringify(bad)}`, () => {
      expect(endDateForDays(bad, 4)).toBeNull()
    })
  }
})

describe("an end before the start", () => {
  it("reports the minimum rather than a negative count", () => {
    // Reachable while a date field is being edited by hand.
    expect(daysInRange("2026-08-15", "2026-08-12")).toBe(MIN_RANGE_DAYS)
  })
})

describe("stepping behaves like the +/- buttons", () => {
  // The stepper reads the count, applies +-1, clamps, and writes an end date.
  const step = (start: string, end: string, delta: number) => {
    const cur = daysInRange(start, end)
    if (cur == null) return end
    return endDateForDays(start, clampDays(cur + delta)) ?? end
  }

  it("default of 1 increments to 2", () => {
    expect(step("2026-08-12", "2026-08-12", +1)).toBe("2026-08-13")
  })

  it("2 decrements back to 1", () => {
    expect(step("2026-08-12", "2026-08-13", -1)).toBe("2026-08-12")
  })

  it("cannot go below 1", () => {
    expect(step("2026-08-12", "2026-08-12", -1)).toBe("2026-08-12")
  })

  it("survives rapid repeated clicks in both directions", () => {
    let end = "2026-08-12"
    for (let i = 0; i < 25; i++) end = step("2026-08-12", end, +1)
    expect(daysInRange("2026-08-12", end)).toBe(26)
    for (let i = 0; i < 100; i++) end = step("2026-08-12", end, -1)
    expect(daysInRange("2026-08-12", end)).toBe(MIN_RANGE_DAYS)
  })

  it("cannot be pushed past the maximum by holding +", () => {
    let end = "2026-08-12"
    for (let i = 0; i < MAX_RANGE_DAYS + 50; i++) end = step("2026-08-12", end, +1)
    expect(daysInRange("2026-08-12", end)).toBe(MAX_RANGE_DAYS)
  })

  it("changing the start date re-derives the count without touching the end", () => {
    // The count is derived, never stored — so editing Start changes the number
    // shown, which is the intended single-source-of-truth behaviour.
    expect(daysInRange("2026-08-12", "2026-08-15")).toBe(4)
    expect(daysInRange("2026-08-13", "2026-08-15")).toBe(3)
  })
})

// ---------------------------------------------------------------------------
// Burst clicks must COMPOSE.
//
// The first implementation computed an absolute end date from the day count it
// had rendered with. Three fast clicks all read the same count and produced the
// same date, so "+3" advanced one day. Browser-verified as such before the fix.
// steppedEndDate takes the CURRENT end, so each application builds on the last.
// ---------------------------------------------------------------------------
describe("stepping composes across rapid clicks", () => {
  it("three +1 steps advance three days, not one", () => {
    let end = "2026-08-12"
    for (let i = 0; i < 3; i++) end = steppedEndDate("2026-08-12", end, +1)
    expect(end).toBe("2026-08-15")
    expect(daysInRange("2026-08-12", end)).toBe(4)
  })

  it("six + then two - lands on five days", () => {
    let end = "2026-08-12"
    for (let i = 0; i < 6; i++) end = steppedEndDate("2026-08-12", end, +1)
    for (let i = 0; i < 2; i++) end = steppedEndDate("2026-08-12", end, -1)
    expect(daysInRange("2026-08-12", end)).toBe(5)
  })

  it("holding minus stops at 1 and stays there", () => {
    let end = "2026-08-20"
    for (let i = 0; i < 50; i++) end = steppedEndDate("2026-08-12", end, -1)
    expect(end).toBe("2026-08-12")
    expect(daysInRange("2026-08-12", end)).toBe(MIN_RANGE_DAYS)
  })

  it("holding plus stops at the maximum", () => {
    let end = "2026-08-12"
    for (let i = 0; i < MAX_RANGE_DAYS + 30; i++) end = steppedEndDate("2026-08-12", end, +1)
    expect(daysInRange("2026-08-12", end)).toBe(MAX_RANGE_DAYS)
  })

  it("an unparseable end is returned untouched", () => {
    expect(steppedEndDate("2026-08-12", "garbage", +1)).toBe("garbage")
  })

  it("never yields a range shorter than one day", () => {
    for (let d = -10; d <= 10; d++) {
      const end = steppedEndDate("2026-08-12", "2026-08-12", d)
      expect(daysInRange("2026-08-12", end)!).toBeGreaterThanOrEqual(MIN_RANGE_DAYS)
    }
  })
})
