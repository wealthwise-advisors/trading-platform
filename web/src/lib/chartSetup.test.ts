/**
 * The specified numbers are the point of this module, so they are asserted
 * one by one rather than looped over. A loop that reads the table and checks
 * itself against the table proves nothing; if someone edits a value by
 * accident, these are the tests that say which one.
 */
import { describe, expect, it } from "vitest"
import {
  CHART_SETUP, CHART_SETUP_ORDER, daysFor, daysForSet, isSpecified,
} from "./chartSetup"

describe("the specified chart setup", () => {
  it("charts 1m over 2 days", () => expect(daysFor("1m")).toBe(2))
  it("charts 5m over 2 days", () => expect(daysFor("5m")).toBe(2))
  it("charts 10m over 3 days", () => expect(daysFor("10m")).toBe(3))
  it("charts 15m over 4 days", () => expect(daysFor("15m")).toBe(4))
  it("charts 20m over 5 days", () => expect(daysFor("20m")).toBe(5))
  it("charts 30m over 10 days", () => expect(daysFor("30m")).toBe(10))
  it("charts 45m over 15 days", () => expect(daysFor("45m")).toBe(15))
  it("charts 1h over 25 days", () => expect(daysFor("1h")).toBe(25))

  it("marks every specified interval as specified", () => {
    for (const tf of ["1m", "5m", "10m", "15m", "20m", "30m", "45m", "1h"]) {
      expect(isSpecified(tf)).toBe(true)
    }
  })
})

describe("the three intervals nobody specified", () => {
  it("does not claim 2m, 25m or 35m were specified", () => {
    for (const tf of ["2m", "25m", "35m"]) expect(isSpecified(tf)).toBe(false)
  })

  it("still offers each one a value, so no timeframe is left without a setup", () => {
    expect(daysFor("2m")).toBe(2)
    expect(daysFor("25m")).toBe(8)
    expect(daysFor("35m")).toBe(12)
  })
})

describe("the shape of the table", () => {
  it("never gives a coarser bar less history than a finer one", () => {
    const days = CHART_SETUP_ORDER.map((tf) => CHART_SETUP[tf])
    for (let i = 1; i < days.length; i++) expect(days[i]).toBeGreaterThanOrEqual(days[i - 1])
  })

  it("covers every timeframe both pages offer", () => {
    const offered = ["1m", "2m", "5m", "10m", "15m", "20m", "25m", "30m", "35m", "45m", "1h"]
    for (const tf of offered) expect(daysFor(tf)).not.toBeNull()
    expect(CHART_SETUP_ORDER).toHaveLength(offered.length)
  })

  it("orders by bar interval, not alphabetically", () => {
    expect(CHART_SETUP_ORDER[0]).toBe("1m")
    expect(CHART_SETUP_ORDER.at(-1)).toBe("1h")
    // "10m" sorts before "2m" as a string; it must not here.
    expect(CHART_SETUP_ORDER.indexOf("2m")).toBeLessThan(CHART_SETUP_ORDER.indexOf("10m"))
  })
})

describe("an unknown timeframe", () => {
  it("returns null rather than inventing a default", () => {
    expect(daysFor("3h")).toBeNull()
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

  it("ignores timeframes it has no preset for instead of failing", () => {
    expect(daysForSet(["3h", "15m"])).toBe(4)
  })

  it("returns null when it knows none of them, so the range is left alone", () => {
    expect(daysForSet(["3h", "1w"])).toBeNull()
    expect(daysForSet([])).toBeNull()
  })
})
