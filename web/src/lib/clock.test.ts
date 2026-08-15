import { describe, it, expect } from "vitest"
import { addMinutesNaive, barCloseLabel, barOpenLabel } from "./clock"

/**
 * Bars are stored on their OPEN time, so the final bar of a 17:00 session is
 * labelled 16:59 and reads as though the session ended early. These pin the
 * close-labelling that fixes that, and the timezone-independence that keeps the
 * label the same for every viewer.
 */
describe("bar close labels", () => {
  it("labels the final bar with the configured session end", () => {
    expect(barCloseLabel("2026-08-12T16:59:00", 1)).toBe("2026-08-12 17:00")
    expect(barCloseLabel("2026-08-12T16:55:00", 5)).toBe("2026-08-12 17:00")
    expect(barCloseLabel("2026-08-12T16:45:00", 15)).toBe("2026-08-12 17:00")
    expect(barCloseLabel("2026-08-12T16:30:00", 30)).toBe("2026-08-12 17:00")
    expect(barCloseLabel("2026-08-12T16:00:00", 60)).toBe("2026-08-12 17:00")
  })

  it("works for the odd intervals too", () => {
    expect(barCloseLabel("2026-08-12T16:35:00", 25)).toBe("2026-08-12 17:00")
    expect(barCloseLabel("2026-08-12T16:25:00", 35)).toBe("2026-08-12 17:00")
    expect(barCloseLabel("2026-08-12T16:15:00", 45)).toBe("2026-08-12 17:00")
  })

  it("rolls over the hour, the day, the month and the year", () => {
    expect(addMinutesNaive("2026-08-12T09:59:00", 1)).toBe("2026-08-12 10:00")
    expect(addMinutesNaive("2026-08-12T23:59:00", 1)).toBe("2026-08-13 00:00")
    expect(addMinutesNaive("2026-08-31T23:59:00", 1)).toBe("2026-09-01 00:00")
    expect(addMinutesNaive("2026-12-31T23:59:00", 1)).toBe("2027-01-01 00:00")
    expect(addMinutesNaive("2028-02-28T23:59:00", 1)).toBe("2028-02-29 00:00")  // leap year
  })

  it("is independent of the viewer's timezone", () => {
    // A naive market timestamp must produce the same label everywhere. Parsing
    // via the local Date constructor would shift this by the viewer's offset.
    const label = barCloseLabel("2026-08-12T12:20:00", 1)
    expect(label).toBe("2026-08-12 12:21")
    // no hour component of the input may leak through unchanged-but-shifted
    expect(label.slice(11, 13)).toBe("12")
  })

  it("accepts a space separator as well as T", () => {
    expect(barCloseLabel("2026-08-12 16:59:00", 1)).toBe("2026-08-12 17:00")
  })

  it("returns the input unchanged when it is not a timestamp", () => {
    expect(barCloseLabel("", 1)).toBe("")
    expect(barCloseLabel("not-a-date", 5)).toBe("not-a-date")
  })
})

describe("barOpenLabel — the shape Jump compares against", () => {
  it("renders a bar's open in the same shape as a typed time", () => {
    // Jump builds the typed side with addMinutesNaive, so both sides must be
    // space-separated and second-less or the string comparison is meaningless.
    expect(barOpenLabel("2026-08-13T14:20:00")).toBe("2026-08-13 14:20")
    expect(barOpenLabel("2026-08-13 14:20")).toBe("2026-08-13 14:20")
  })

  it("sorts correctly against a typed time on the SAME date", () => {
    // The regression: comparing the raw ISO string put every bar on the target's
    // own date AFTER the target, because "T" sorts after " ". Jump then fell back
    // to the previous day -- it showed a bar opening 2026-08-12 23:40 for a
    // request of 2026-08-13 14:20.
    const target = addMinutesNaive("2026-08-13 14:20", 0)
    const raw = "2026-08-13T09:00:00"
    expect(raw <= target).toBe(false)              // the broken comparison
    expect(barOpenLabel(raw) <= target).toBe(true) // the fixed one
  })

  it("still puts a genuinely later bar after the target", () => {
    const target = addMinutesNaive("2026-08-13 14:20", 0)
    expect(barOpenLabel("2026-08-13T14:40:00") <= target).toBe(false)
    expect(barOpenLabel("2026-08-13T14:20:00") <= target).toBe(true)
    expect(barOpenLabel("2026-08-12T23:40:00") <= target).toBe(true)
  })
})
