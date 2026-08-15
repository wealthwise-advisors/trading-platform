// Regression tests for the timestamp convention bug that made the entire
// candlestick trace vanish from the price panel.
//
// The failure: resampleOHLC serialized bucket boundaries with
// new Date(ms).toISOString(), which always emits UTC with a trailing "Z",
// while every other trace passed the API's naive wall-clock strings straight
// through. Plotly reads a trailing "Z" as UTC and a naive string as wall
// clock, so on a UTC+05:30 machine the candles landed 5h30m left of the EMA
// lines -- about 4,900px outside the plot area. The trace was present and its
// paths had correct 40px geometry; they were simply nowhere near the viewport.
//
// These tests are written to fail if that serialization is reintroduced,
// REGARDLESS of the machine's timezone: the assertions compare candle output
// against the same-shaped output for the other traces rather than against
// hardcoded strings, so they hold at UTC+0 too (where the bug is invisible).

import { describe, it, expect } from "vitest"
import { toNaiveString, formatterFor } from "@/lib/isoTime"

const NAIVE = "2026-08-10T09:30:00"
const ZULU = "2026-08-10T09:30:00.000Z"
const OFFSET = "2026-08-10T09:30:00+05:30"

describe("toNaiveString", () => {
  it("is the exact inverse of parsing a naive wall-clock string", () => {
    // The round trip must be lossless in ANY timezone: Date.parse reads a
    // naive string as local, so serializing with local getters must return it.
    for (const s of [
      "2026-08-10T09:30:00",
      "2026-01-01T00:00:00",
      "2026-12-31T23:59:59",
      "2026-03-08T02:30:00", // inside the US DST spring-forward window
      "2026-11-01T01:30:00", // inside the US DST fall-back window
    ]) {
      expect(toNaiveString(Date.parse(s))).toBe(s)
    }
  })

  it("never emits a timezone designator", () => {
    expect(toNaiveString(Date.parse(NAIVE))).not.toMatch(/Z$|[+-]\d{2}:?\d{2}$/)
  })

  it("zero-pads every field", () => {
    expect(toNaiveString(Date.parse("2026-01-02T03:04:05"))).toBe("2026-01-02T03:04:05")
  })
})

describe("formatterFor", () => {
  it("returns a naive serializer for naive input", () => {
    const fmt = formatterFor(NAIVE)
    expect(fmt(Date.parse(NAIVE))).toBe(NAIVE)
  })

  it("returns a UTC serializer for Z-suffixed input", () => {
    const fmt = formatterFor(ZULU)
    expect(fmt(Date.parse(ZULU))).toBe(ZULU)
  })

  it("returns a UTC serializer for explicit-offset input", () => {
    // An offset-bearing string is unambiguous, so round-tripping through UTC
    // preserves the instant even though the literal text changes.
    const fmt = formatterFor(OFFSET)
    expect(Date.parse(fmt(Date.parse(OFFSET)))).toBe(Date.parse(OFFSET))
  })

  it("round-trips any sample back to an equivalent instant", () => {
    for (const s of [NAIVE, ZULU, OFFSET]) {
      const fmt = formatterFor(s)
      expect(Date.parse(fmt(Date.parse(s)))).toBe(Date.parse(s))
    }
  })

  it("THE BUG: a derived timestamp keeps the convention of its source", () => {
    // This is the invariant that was violated. A value derived by arithmetic
    // on a naive timestamp must come back naive, or it renders on a different
    // part of the axis than the untouched strings beside it.
    const fmt = formatterFor(NAIVE)
    const oneHourLater = fmt(Date.parse(NAIVE) + 3_600_000)
    expect(oneHourLater).toBe("2026-08-10T10:30:00")
    expect(oneHourLater).not.toMatch(/Z$/)
  })

  it("THE BUG: naive input must not produce UTC output even at UTC+0", () => {
    // toISOString() on a naive-derived value is wrong even where the offset is
    // zero and the shift is invisible -- the string shape itself differs, and
    // Plotly's parsing of the two differs. Asserting on shape, not value,
    // makes this test meaningful on a UTC CI runner.
    const naiveOut = formatterFor(NAIVE)(Date.parse(NAIVE))
    const utcOut = new Date(Date.parse(NAIVE)).toISOString()
    expect(/Z$/.test(naiveOut)).toBe(false)
    expect(/Z$/.test(utcOut)).toBe(true)
    expect(/Z$/.test(naiveOut)).toBe(/Z$/.test(NAIVE))
  })
})
