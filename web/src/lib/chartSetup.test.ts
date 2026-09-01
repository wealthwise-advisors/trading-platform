/**
 * The eight specified numbers are the point of this module, so each is
 * asserted on its own line rather than looped over. A loop that reads the
 * table and checks itself against the table proves nothing; if a value is
 * edited by accident, these say which one.
 */
import { describe, expect, it } from "vitest"
import {
  ALL_CHART_TIMEFRAMES, daysFor, daysForSet, isSpecified, UNSPECIFIED,
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
