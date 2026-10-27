/**
 * The twelve specified numbers are the point of this module, so each is
 * asserted on its own line rather than looped over. A loop that reads the
 * table and checks itself against the table proves nothing; if a value is
 * edited by accident, these say which one.
 */
import { describe, expect, it } from "vitest"
import {
  QUICK_INTERVALS,
  ALL_CHART_TIMEFRAMES, INTRADAY_TIMEFRAMES, daysFor, daysForSet, isDailyOrLonger, isMaxHistory,
  isSpecified, maxRangeDaysFor, rangeLabel, TF_MINUTES, startDateForTimeframe, startDateForTimeframes, UNSPECIFIED,
} from "./chartSetup"
import { MAX_HISTORY_DAYS, MAX_RANGE_DAYS } from "./dayRange"

describe("the specified table", () => {
  it("loads 2 days for 1m", () => expect(daysFor("1m")).toBe(2))
  it("loads 2 days for 5m", () => expect(daysFor("5m")).toBe(2))
  it("loads 3 days for 10m", () => expect(daysFor("10m")).toBe(3))
  it("loads 4 days for 15m", () => expect(daysFor("15m")).toBe(4))
  it("loads 5 days for 20m", () => expect(daysFor("20m")).toBe(5))
  it("loads 15 days for 30m", () => expect(daysFor("30m")).toBe(15))
  it("loads 20 days for 45m", () => expect(daysFor("45m")).toBe(20))
  // 3m was given 2 days by inference on 2026-10-11 and that was overruled the
  // next day: it has no specified range. Guarded explicitly so the same
  // "1m and 5m are both 2" argument cannot quietly bring it back.
  it("gives 3m no range, even though 1m and 5m agree around it", () =>
    expect(daysFor("3m")).toBeNull())
  it("loads 25 days for 1h", () => expect(daysFor("1h")).toBe(25))
  it("loads 180 days for 2h", () => expect(daysFor("2h")).toBe(180))
  it("loads 180 days for 4h", () => expect(daysFor("4h")).toBe(180))
  it("loads the maximum history, twenty years, for 1d", () => expect(daysFor("1d")).toBe(MAX_HISTORY_DAYS))
  it("loads the maximum history, twenty years, for 1w", () => expect(daysFor("1w")).toBe(MAX_HISTORY_DAYS))

  it("twenty years is 7305 days", () => expect(MAX_HISTORY_DAYS).toBe(7305))

  it("marks exactly 1d and 1w as Max", () => {
    expect(ALL_CHART_TIMEFRAMES.filter(isMaxHistory)).toEqual(["1d", "1w"])
  })

  it("gives 1m and 5m the same value, which is intended and not a typo", () => {
    expect(daysFor("1m")).toBe(daysFor("5m"))
  })

  it("holds exactly twelve entries — nothing inferred has been added", () => {
    expect(ALL_CHART_TIMEFRAMES.filter(isSpecified)).toHaveLength(12)
  })
})

describe("timeframes the table does not cover", () => {
  // 2m was here until 2026-10-11, when it was specified as 2 and moved into
  // the table. 25m was asked about in the same message and not answered, so
  // it stays uncovered; 35m was not raised.
  it("no longer offers 2m at all", () => {
    // Replaced by 3m in the selector on 2026-10-11. The API still accepts it
    // -- see TF_MINUTES -- but the app does not offer it.
    expect(ALL_CHART_TIMEFRAMES).not.toContain("2m")
    expect(ALL_CHART_TIMEFRAMES).toContain("3m")
  })

  it("has no entry for 25m or 35m", () => {
    for (const tf of ["25m", "35m"]) {
      expect(isSpecified(tf)).toBe(false)
      expect(daysFor(tf)).toBeNull()
    }
  })

  it("keeps their proposed values out of the lookup entirely", () => {
    // UNSPECIFIED is a proposal awaiting a decision. If it ever leaks into
    // daysFor, a timeframe nobody specified starts moving real date ranges.
    for (const tf of Object.keys(UNSPECIFIED)) expect(daysFor(tf)).toBeNull()
  })

  it("proposes a value for each remaining one, for a human to accept or not", () => {
    expect(UNSPECIFIED).toEqual({ "25m": 5, "35m": 10 })
  })
})

describe("an unknown timeframe", () => {
  it("returns null rather than inventing a default", () => {
    expect(daysFor("3h")).toBeNull()
    expect(daysFor("1mo")).toBeNull()
    expect(daysFor("")).toBeNull()
  })
})

describe("a set of timeframes sharing one range", () => {
  it("takes the largest, so the coarsest pane still has history", () => {
    expect(daysForSet(["1m", "1h"])).toBe(25)
    expect(daysForSet(["5m", "15m"])).toBe(4)
    expect(daysForSet(["1m", "4h"])).toBe(180)
  })

  it("matches the single value when only one is selected", () => {
    expect(daysForSet(["30m"])).toBe(15)
  })

  it("skips uncovered timeframes rather than treating them as zero", () => {
    expect(daysForSet(["25m", "15m"])).toBe(4)
    expect(daysForSet(["25m", "1h"])).toBe(25)
  })

  it("returns null when it covers none of them, so the range is left alone", () => {
    expect(daysForSet(["25m", "35m"])).toBeNull()
    expect(daysForSet([])).toBeNull()
  })
})

describe("the timeframe list", () => {
  it("covers every interval Backtest and Export Data offer, in bar-interval order", () => {
    expect(ALL_CHART_TIMEFRAMES).toEqual([
      "1m", "3m", "5m", "10m", "15m", "20m", "25m", "30m", "35m", "45m", "1h", "2h", "4h", "1d", "1w",
    ])
  })

  it("gives Market Grid everything but daily and weekly, which it cannot replay", () => {
    expect(INTRADAY_TIMEFRAMES).toEqual([
      "1m", "3m", "5m", "10m", "15m", "20m", "25m", "30m", "35m", "45m", "1h", "2h", "4h",
    ])
  })

  it("knows which are daily or longer, and how far each can reach", () => {
    expect(ALL_CHART_TIMEFRAMES.filter(isDailyOrLonger)).toEqual(["1d", "1w"])
    expect(maxRangeDaysFor("1d")).toBe(MAX_HISTORY_DAYS)
    expect(maxRangeDaysFor("1w")).toBe(MAX_HISTORY_DAYS)
    expect(maxRangeDaysFor("4h")).toBe(MAX_RANGE_DAYS)
    expect(maxRangeDaysFor("3m")).toBe(MAX_RANGE_DAYS)
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
    expect(startDateForTimeframe(END, "30m")).toBe("2026-08-18")   // 15 days
    expect(startDateForTimeframe(END, "1h")).toBe("2026-08-08")    // 25 days
    expect(startDateForTimeframe(END, "2h")).toBe("2026-03-06")    // 180 days
    expect(startDateForTimeframe(END, "4h")).toBe("2026-03-06")    // 180 days
    expect(startDateForTimeframe(END, "1d")).toBe("2006-09-02")    // 7305 days, twenty years
    expect(startDateForTimeframe(END, "1w")).toBe("2006-09-02")
  })

  it("shortens a range too long for the new timeframe, as after Daily's twenty years", () => {
    // 25m has no day count, so its range normally stays -- but not at 20 years.
    expect(startDateForTimeframe(END, "25m", "2006-09-02")).toBe("2026-03-06")   // 180 days
    // A range it can serve is left exactly as it was.
    expect(startDateForTimeframe(END, "25m", "2026-08-20")).toBeNull()
  })

  it("gives 1m and 5m the same start, as the table intends", () => {
    expect(startDateForTimeframe(END, "1m")).toBe(startDateForTimeframe(END, "5m"))
  })

  it("moves nothing for a timeframe the table does not cover", () => {
    for (const tf of ["25m", "35m", "3h"]) {
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
    expect(startDateForTimeframes(END, ["25m", "15m"])).toBe(startDateForTimeframe(END, "15m"))
  })

  it("moves nothing when the selection is empty or wholly uncovered", () => {
    expect(startDateForTimeframes(END, [])).toBeNull()
    expect(startDateForTimeframes(END, ["25m", "35m"])).toBeNull()
  })
})

/**
 * rangeLabel moved here from lib/intervalPicker when the interval-picker
 * popup was removed. Its tests moved with it -- the Volume Profile dialog's
 * day-range column is the only caller now, and the numbers it prints are the
 * specified table verbatim.
 */
describe("rangeLabel reads the specified table and invents nothing", () => {
  it.each([
    ["1m", "2 D"], ["5m", "2 D"], ["10m", "3 D"], ["15m", "4 D"],
    ["20m", "5 D"], ["30m", "15 D"], ["45m", "20 D"], ["1h", "25 D"],
    ["2h", "180 D"], ["4h", "180 D"], ["1d", "Max"], ["1w", "Max"],
  ])("%s -> %s", (tf, label) => {
    expect(rangeLabel(tf)).toBe(label)
  })

  it.each(["3m", "25m", "35m"])("%s has no day count, so no label", (tf) => {
    expect(rangeLabel(tf)).toBeNull()
  })

  it("covers every offered interval except the three left blank", () => {
    const unlabelled = ALL_CHART_TIMEFRAMES.filter((tf) => rangeLabel(tf) == null)
    expect(unlabelled).toEqual(["3m", "25m", "35m"])
  })
})

/**
 * Every intraday timeframe the app offers must have a minutes entry.
 *
 * THE BUG THIS CATCHES. 3m replaced 2m in the list and the minutes table,
 * then in another file, was not updated. Market Grid divided by undefined,
 * marked 3m as needing a refetch it did not need, and mis-sorted it.
 */
describe("TF_MINUTES covers every offered intraday timeframe", () => {
  it.each([...INTRADAY_TIMEFRAMES])("%s has a minutes entry", (tf) => {
    expect(Number.isInteger(TF_MINUTES[tf]) && TF_MINUTES[tf] > 0).toBe(true)
  })

  it("can build 3m from 1-minute bars, so it needs no refetch", () => {
    expect(TF_MINUTES["3m"] % TF_MINUTES["1m"]).toBe(0)
  })

  it("orders the offered timeframes by length, as Market Grid sorts its rows", () => {
    const sorted = [...INTRADAY_TIMEFRAMES].sort((a, b) => TF_MINUTES[a] - TF_MINUTES[b])
    expect(sorted).toEqual([...INTRADAY_TIMEFRAMES])
  })
})

describe("QUICK_INTERVALS", () => {
  it("puts 3m and 10m on the Backtest and chart quick buttons, in bar-length order", () => {
    expect(QUICK_INTERVALS).toEqual(["1m", "3m", "5m", "10m", "15m", "30m", "1h", "4h", "1D", "1W", "1M"])
  })
})
