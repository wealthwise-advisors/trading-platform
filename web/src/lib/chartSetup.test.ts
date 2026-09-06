/**
 * The eight specified numbers are the point of this module, so each is
 * asserted on its own line rather than looped over. A loop that reads the
 * table and checks itself against the table proves nothing; if a value is
 * edited by accident, these say which one.
 */
import { describe, expect, it } from "vitest"
import {
  ALL_CHART_TIMEFRAMES, daysFor, daysForSet, isSpecified,
  startDateForTimeframe, startDateForTimeframes, UNSPECIFIED,
} from "./chartSetup"

describe("the specified table", () => {
  it("loads 2 days for 1m", () => expect(daysFor("1m")).toBe(2))
  it("loads 2 days for 5m", () => expect(daysFor("5m")).toBe(2))
  it("loads 3 days for 10m", () => expect(daysFor("10m")).toBe(3))
  it("loads 4 days for 15m", () => expect(daysFor("15m")).toBe(4))
  it("loads 5 days for 20m", () => expect(daysFor("20m")).toBe(5))
  it("loads 10 days for 30m", () => expect(daysFor("30m")).toBe(10))
  it("loads 15 days for 45m", () => expect(daysFor("45m")).toBe(15))
  it("loads 25 days for 1h", () => expect(daysFor("1h")).toBe(25))

  it("gives 1m and 5m the same value, which is intended and not a typo", () => {
    expect(daysFor("1m")).toBe(daysFor("5m"))
  })

  it("holds exactly eight entries — nothing inferred has been added", () => {
    expect(ALL_CHART_TIMEFRAMES.filter(isSpecified)).toHaveLength(8)
  })
})

describe("timeframes the table does not cover", () => {
  it("has no entry for 2m, 25m or 35m", () => {
    for (const tf of ["2m", "25m", "35m"]) {
      expect(isSpecified(tf)).toBe(false)
      expect(daysFor(tf)).toBeNull()
    }
  })

  it("keeps their proposed values out of the lookup entirely", () => {
    // UNSPECIFIED is a proposal awaiting a decision. If it ever leaks into
    // daysFor, a timeframe nobody specified starts moving real date ranges.
    for (const tf of Object.keys(UNSPECIFIED)) expect(daysFor(tf)).toBeNull()
  })

  it("proposes a value for each of the three, for a human to accept or not", () => {
    expect(UNSPECIFIED).toEqual({ "2m": 2, "25m": 5, "35m": 10 })
  })
})

describe("an unknown timeframe", () => {
  it("returns null rather than inventing a default", () => {
    expect(daysFor("2h")).toBeNull()
    expect(daysFor("4h")).toBeNull()
    expect(daysFor("1d")).toBeNull()
    expect(daysFor("1w")).toBeNull()
    expect(daysFor("")).toBeNull()
  })
})

describe("a set of timeframes sharing one range", () => {
  it("takes the largest, so the coarsest pane still has history", () => {
    expect(daysForSet(["1m", "1h"])).toBe(25)
    expect(daysForSet(["5m", "15m"])).toBe(4)
  })

  it("matches the single value when only one is selected", () => {
    expect(daysForSet(["30m"])).toBe(10)
  })

  it("skips uncovered timeframes rather than treating them as zero", () => {
    expect(daysForSet(["25m", "15m"])).toBe(4)
    expect(daysForSet(["2m", "1h"])).toBe(25)
  })

  it("returns null when it covers none of them, so the range is left alone", () => {
    expect(daysForSet(["2m", "25m", "35m"])).toBeNull()
    expect(daysForSet([])).toBeNull()
  })
})

describe("the timeframe list", () => {
  it("covers every interval both pages offer, in bar-interval order", () => {
    expect(ALL_CHART_TIMEFRAMES).toEqual([
      "1m", "2m", "5m", "10m", "15m", "20m", "25m", "30m", "35m", "45m", "1h",
    ])
  })
})

describe("the start date a timeframe change produces", () => {
  // The end is the fixed edge — normally the most recent session the source
  // can serve — so the START moves and the window becomes "the last N days".
  const END = "2026-09-01"

  it("counts back inclusively, so 2 days ends the day after it starts", () => {
    expect(startDateForTimeframe(END, "1m")).toBe("2026-08-31")
  })

  it("reaches back further the coarser the bar", () => {
    expect(startDateForTimeframe(END, "10m")).toBe("2026-08-30")   // 3 days
    expect(startDateForTimeframe(END, "30m")).toBe("2026-08-23")   // 10 days
    expect(startDateForTimeframe(END, "1h")).toBe("2026-08-08")    // 25 days
  })

  it("gives 1m and 5m the same start, as the table intends", () => {
    expect(startDateForTimeframe(END, "1m")).toBe(startDateForTimeframe(END, "5m"))
  })

  it("moves nothing for a timeframe the table does not cover", () => {
    for (const tf of ["2m", "25m", "35m", "4h", "1d"]) {
      expect(startDateForTimeframe(END, tf)).toBeNull()
    }
  })

  it("moves nothing when the end date is mid-edit and unparseable", () => {
    // The caller writes only on a non-null result, so a half-typed date can
    // never produce a start derived from garbage.
    expect(startDateForTimeframe("2026-09", "1h")).toBeNull()
    expect(startDateForTimeframe("", "1h")).toBeNull()
  })

  it("crosses a month boundary correctly", () => {
    expect(startDateForTimeframe("2026-03-02", "10m")).toBe("2026-02-28")
  })

  it("crosses a leap day correctly", () => {
    // 2024 is a leap year: 3 days back from 1 Mar is 28 Feb only if 29 Feb exists.
    expect(startDateForTimeframe("2024-03-01", "10m")).toBe("2024-02-28")
  })
})

describe("the start date a Market Grid selection produces", () => {
  const END = "2026-09-01"

  it("follows the coarsest pane, so none of them is left empty", () => {
    expect(startDateForTimeframes(END, ["1m", "1h"])).toBe("2026-08-08")  // 25, not 2
  })

  it("matches the single-timeframe result when only one is selected", () => {
    expect(startDateForTimeframes(END, ["30m"])).toBe(startDateForTimeframe(END, "30m"))
  })

  it("ignores uncovered timeframes in the selection", () => {
    expect(startDateForTimeframes(END, ["2m", "15m"])).toBe(startDateForTimeframe(END, "15m"))
  })

  it("moves nothing when the selection is empty or wholly uncovered", () => {
    expect(startDateForTimeframes(END, [])).toBeNull()
    expect(startDateForTimeframes(END, ["2m", "25m", "35m"])).toBeNull()
  })
})
