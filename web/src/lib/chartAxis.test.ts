// Integration-level guard for the failure mode the unit tests above can miss:
// a trace that is present, correctly shaped, and still nowhere near the
// viewport.
//
// The real bug looked healthy at every level except position. The candlestick
// trace existed, had 40 points with valid OHLC values, and its rendered SVG
// paths measured a correct 40.04px via getBBox(). It was simply drawn ~4,900px
// to the left of the plot area, because its x strings used a different
// timestamp convention than every other trace. getBBox() reports geometry in
// local SVG coordinates and ignores clipping, so a geometry check could not
// have caught it.
//
// Rather than drive a real browser, this reproduces the arithmetic Plotly does
// to turn an x value into a pixel: project each timestamp onto the axis range,
// then assert the result lands inside the plot rectangle. That is exactly the
// quantity that went wrong, and it runs in a millisecond with no DOM.
//
// A true pixel-level test would need Playwright plus a running dev server; see
// the note in the commit message for why that is not wired up yet.

import { describe, it, expect } from "vitest"
import { resampleOHLC } from "@/lib/resample"
import { computeRangebreaks } from "@/lib/rangebreaks"
import type { OHLCVRecord } from "@/lib/types"
import { toNaiveString } from "@/lib/isoTime"

const PLOT_LEFT = 50
const PLOT_WIDTH = 1103   // measured from the real chart at 1683px wide

/** One 09:30-16:00 session of 5-minute bars, as the API delivers them. */
function session(day = "2026-08-10"): OHLCVRecord[] {
  const t0 = Date.parse(`${day}T09:30:00`)
  const n = 390 / 5 + 1
  return Array.from({ length: n }, (_, i) => {
    const ms = t0 + i * 5 * 60_000
    return { t: toNaiveString(ms), o: 4500, h: 4510, l: 4490, c: 4505, v: 100 }
  })
}

/**
 * Parse the way PLOTLY does, which is the whole point of this file.
 *
 * JS Date.parse() cannot expose this bug: it reads a naive string as local and
 * a Z string as UTC, so "09:30" and its toISOString() form resolve to the same
 * instant and appear identical. Plotly does not do that -- it reads a naive
 * string's wall-clock fields as-is and a Z string as UTC, so the two land
 * 5h30m apart on a UTC+05:30 machine. That divergence is the defect.
 */
function plotlyParse(t: string): number {
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:?\d{2})?$/.exec(t)
  if (!m) return NaN
  const [, y, mo, d, h, mi, s, frac, tz] = m
  const base = Date.UTC(+y, +mo - 1, +d, +h, +mi, +s,
    frac ? Number(frac.padEnd(3, "0").slice(0, 3)) : 0)
  if (!tz || tz === "Z") return base
  const sign = tz[0] === "-" ? -1 : 1
  const digits = tz.slice(1).replace(":", "")
  return base - sign * (Number(digits.slice(0, 2)) * 60 + Number(digits.slice(2))) * 60_000
}

/** Plotly's projection: timestamp -> pixel, given an axis range and plot rect. */
function toPixel(t: string, range: [string, string]): number {
  const lo = plotlyParse(range[0])
  const hi = plotlyParse(range[1])
  return PLOT_LEFT + ((plotlyParse(t) - lo) / (hi - lo)) * PLOT_WIDTH
}

describe("candlestick trace lands inside the plot area", () => {
  const bars = session()
  // Every other trace (EMA9, VWAP, markers) receives bars[i].t verbatim.
  const otherTraceX = bars.map((b) => b.t)
  const candleX = resampleOHLC(bars, 9).map((b) => b.t)
  // The axis is autoranged over the traces that render, i.e. the untouched ones.
  const axis: [string, string] = [otherTraceX[0], otherTraceX[otherTraceX.length - 1]]

  it("candle x values share the axis domain with the other traces", () => {
    const lo = plotlyParse(axis[0])
    const hi = plotlyParse(axis[1])
    for (const t of candleX) {
      expect(plotlyParse(t)).toBeGreaterThanOrEqual(lo)
      expect(plotlyParse(t)).toBeLessThanOrEqual(hi)
    }
  })

  it("THE BUG: every candle projects to a pixel inside the plot rectangle", () => {
    // With the bug, the first candle projected to roughly -4872px against a
    // plot area starting at +50px.
    for (const t of candleX) {
      const px = toPixel(t, axis)
      expect(px).toBeGreaterThanOrEqual(PLOT_LEFT - 1)
      expect(px).toBeLessThanOrEqual(PLOT_LEFT + PLOT_WIDTH + 1)
    }
  })

  it("candles span essentially the same pixel extent as the other traces", () => {
    const candlePx = candleX.map((t) => toPixel(t, axis))
    const otherPx = otherTraceX.map((t) => toPixel(t, axis))
    // Within one bucket's width at either end.
    const bucketPx = (9 / 390) * PLOT_WIDTH * 2
    expect(Math.min(...candlePx)).toBeCloseTo(Math.min(...otherPx), -1)
    expect(Math.abs(Math.max(...candlePx) - Math.max(...otherPx))).toBeLessThan(bucketPx)
  })

  it("demonstrates the regression: UTC-serialized x values leave the plot", () => {
    // Reproduce the old behaviour explicitly so the test file documents what
    // failure looks like, and prove the assertion above would reject it.
    // Skipped where the runner sits at UTC+0, since there the shift is zero
    // and no pixel displacement occurs -- the shape-level tests cover that case.
    const offsetMin = new Date(Date.parse(otherTraceX[0])).getTimezoneOffset()
    if (offsetMin === 0) return

    const buggyX = resampleOHLC(bars, 9).map((b) => new Date(Date.parse(b.t)).toISOString())
    const outside = buggyX.filter((t) => {
      const px = toPixel(t, axis)
      return px < PLOT_LEFT - 1 || px > PLOT_LEFT + PLOT_WIDTH + 1
    })

    // The displacement is exactly the machine's UTC offset, projected onto the
    // axis. Asserting the magnitude rather than "all of them left the plot" is
    // what makes this precise: a 5h30m shift across a 6h30m session still
    // leaves an hour of overlap, so some candles remain on screen while the
    // series as a whole is visibly wrong.
    const axisSpanMs = plotlyParse(axis[1]) - plotlyParse(axis[0])
    const expectedShiftPx = ((-offsetMin * 60_000) / axisSpanMs) * PLOT_WIDTH
    const actualShiftPx = toPixel(candleX[0], axis) - toPixel(buggyX[0], axis)
    expect(actualShiftPx).toBeCloseTo(expectedShiftPx, 6)

    // And the guard above rejects it.
    expect(outside.length).toBeGreaterThan(0)
  })
})

describe("rangebreaks do not remove bars that exist", () => {
  it("no real timestamp falls inside a computed break", () => {
    const times = [...session("2026-08-10"), ...session("2026-08-11")].map((b) => b.t)
    for (const brk of computeRangebreaks(times)) {
      const lo = Date.parse(brk.bounds[0].replace(" ", "T"))
      const hi = Date.parse(brk.bounds[1].replace(" ", "T"))
      for (const t of times) {
        const ms = Date.parse(t)
        expect(ms >= lo && ms < hi).toBe(false)
      }
    }
  })
})
