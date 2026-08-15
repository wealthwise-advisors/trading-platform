// Regression tests for resampleOHLC, which has shipped two separate bugs:
//
//   1. Non-uniform gaps. Bucketing 5-minute bars into 9-minute windows and
//      emitting the first bar's own timestamp produced 09:30, 09:35, 09:45,
//      09:55 ... a mix of 5- and 10-minute spacing. Plotly sizes a candle from
//      the SMALLEST gap between x values, so every body was drawn at the
//      5-minute width while most sat 10 minutes apart -- bodies filled about a
//      quarter of their slot and the series read as thin, sparse sticks.
//
//   2. UTC serialization. Emitting the grid position via toISOString() shifted
//      every candle by the browser's UTC offset, putting the whole trace off
//      the visible axis. See isoTime.test.ts.

import { describe, it, expect } from "vitest"
import { resampleOHLC, displayBucketMinutes } from "@/lib/resample"
import type { OHLCVRecord } from "@/lib/types"
import { toNaiveString } from "@/lib/isoTime"

/** Build `count` bars spaced `stepMinutes` apart, starting at a naive time. */
function makeBars(
  count: number,
  stepMinutes: number,
  start = "2026-08-10T09:30:00",
  zoned = false,
): OHLCVRecord[] {
  const t0 = Date.parse(start)
  return Array.from({ length: count }, (_, i) => {
    const ms = t0 + i * stepMinutes * 60_000
    return {
      t: zoned ? new Date(ms).toISOString() : toNaiveString(ms),
      o: 4500 + i, h: 4505 + i, l: 4495 + i, c: 4502 + i, v: 100 + i,
    }
  })
}

/** Distinct gaps (in minutes) between consecutive output timestamps. */
function gapMinutes(bars: OHLCVRecord[]): number[] {
  const gaps = new Set<number>()
  for (let i = 1; i < bars.length; i++) {
    gaps.add((Date.parse(bars[i].t) - Date.parse(bars[i - 1].t)) / 60_000)
  }
  return [...gaps].sort((a, b) => a - b)
}

describe("resampleOHLC — uniform spacing", () => {
  // 9 is the target the chart actually passes, and the value that exposed the
  // bug: it divides 1m evenly but not 5m or 15m.
  it.each([
    { interval: 1, target: 9, expectedGap: 9 },
    { interval: 5, target: 9, expectedGap: 10 },
    { interval: 15, target: 9, expectedGap: 15 },
    { interval: 5, target: 30, expectedGap: 30 },
    { interval: 15, target: 60, expectedGap: 60 },
  ])(
    "$interval m source, target $target m -> a single gap of $expectedGap m",
    ({ interval, target, expectedGap }) => {
      const out = resampleOHLC(makeBars(60, interval), target)
      const gaps = gapMinutes(out)
      // Exactly one distinct gap. The old code produced [5, 10] here, which is
      // what made Plotly draw quarter-width candles.
      expect(gaps).toHaveLength(1)
      expect(gaps[0]).toBe(expectedGap)
    },
  )

  it("bucket width is always a whole multiple of the source interval", () => {
    for (const interval of [1, 2, 5, 15, 30]) {
      const out = resampleOHLC(makeBars(80, interval), 9)
      if (out.length < 2) continue
      const gap = (Date.parse(out[1].t) - Date.parse(out[0].t)) / 60_000
      expect(gap % interval).toBe(0)
    }
  })

  it("every emitted timestamp sits on the bucket grid", () => {
    const out = resampleOHLC(makeBars(60, 5), 9)
    const step = Date.parse(out[1].t) - Date.parse(out[0].t)
    for (const b of out) {
      expect(Date.parse(b.t) % step).toBe(Date.parse(out[0].t) % step)
    }
  })

  it("returns the input untouched when the bucket would not widen it", () => {
    const bars = makeBars(10, 15)
    expect(resampleOHLC(bars, 9)).toBe(bars)   // 9m target < 15m native
    expect(resampleOHLC(bars, 1)).toBe(bars)   // no aggregation requested
    const single = bars.slice(0, 1)
    expect(resampleOHLC(single, 9)).toBe(single)  // too few bars to bucket
  })
})

describe("resampleOHLC — timestamp convention", () => {
  it("THE BUG: naive input produces naive output", () => {
    const bars = makeBars(60, 5)
    const out = resampleOHLC(bars, 9)
    expect(out.length).toBeGreaterThan(1)
    for (const b of out) {
      expect(b.t).not.toMatch(/Z$/)
      expect(b.t).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/)
    }
  })

  it("THE BUG: candle timestamps match the convention other traces receive", () => {
    // EMA9 and friends get bars[i].t verbatim. If the candle trace's own
    // strings differ in convention, Plotly places them on a different part of
    // the same axis -- the exact failure the user saw.
    const bars = makeBars(60, 5)
    const out = resampleOHLC(bars, 9)
    const emaConvention = /Z$/.test(bars[0].t)
    for (const b of out) {
      expect(/Z$/.test(b.t)).toBe(emaConvention)
    }
  })

  it("Z-suffixed input produces Z-suffixed output", () => {
    const bars = makeBars(60, 5, "2026-08-10T09:30:00", true)
    const out = resampleOHLC(bars, 9)
    for (const b of out) expect(b.t).toMatch(/Z$/)
  })

  it("THE BUG: output stays inside the input's own time span", () => {
    // A UTC-serialized grid position lands hours outside the range the other
    // traces occupy. This catches that even where the string shape looks fine.
    const bars = makeBars(60, 5)
    const lo = Date.parse(bars[0].t)
    const hi = Date.parse(bars[bars.length - 1].t)
    for (const b of resampleOHLC(bars, 9)) {
      expect(Date.parse(b.t)).toBeGreaterThanOrEqual(lo - 9 * 60_000)
      expect(Date.parse(b.t)).toBeLessThanOrEqual(hi)
    }
  })
})

describe("resampleOHLC — OHLCV aggregation", () => {
  it("open is the first bar's, close the last, high/low the extremes", () => {
    const bars = makeBars(12, 5)
    const out = resampleOHLC(bars, 10)
    expect(out.length).toBeGreaterThan(1)
    expect(out[0].o).toBe(bars[0].o)
    const firstBucket = bars.filter(
      (b) => Date.parse(b.t) < Date.parse(out[1].t),
    )
    expect(out[0].h).toBe(Math.max(...firstBucket.map((b) => b.h)))
    expect(out[0].l).toBe(Math.min(...firstBucket.map((b) => b.l)))
    expect(out[0].c).toBe(firstBucket[firstBucket.length - 1].c)
  })

  it("volume is conserved across the whole series", () => {
    const bars = makeBars(60, 5)
    const total = bars.reduce((s, b) => s + (b.v ?? 0), 0)
    const out = resampleOHLC(bars, 9)
    expect(out.reduce((s, b) => s + (b.v ?? 0), 0)).toBe(total)
  })
})


describe("displayBucketMinutes — candle legibility at any zoom", () => {
  // Plotly draws a candle body at roughly half its slot, measured on the real
  // chart. A ~1100px panel therefore needs the on-screen candle count held
  // near 90 for a ~6px body. These tests assert that invariant directly
  // rather than a particular bucket size, so retuning MAX_VISIBLE_CANDLES
  // does not make them vacuous.
  const PANEL_PX = 1103
  const MIN_BODY_PX = 4

  /** Candles that fall inside `windowMs`, given the chosen bucket. */
  function visibleCount(bars: OHLCVRecord[], windowMs: number): number {
    const out = resampleOHLC(bars, displayBucketMinutes(bars, windowMs))
    const last = Date.parse(out[out.length - 1].t)
    return out.filter((b) => Date.parse(b.t) >= last - windowMs).length
  }

  function bodyPx(bars: OHLCVRecord[], windowMs: number): number {
    return (PANEL_PX / Math.max(1, visibleCount(bars, windowMs))) * 0.49
  }

  it.each([
    { label: "2h window, 5m bars", bars: makeBars(430, 5), windowMs: 2 * 3600e3 },
    { label: "37h Globex range, 5m bars", bars: makeBars(430, 5), windowMs: 37 * 3600e3 },
    { label: "1 RTH day, 5m bars", bars: makeBars(78, 5), windowMs: 6.5 * 3600e3 },
    { label: "1 week, 5m bars", bars: makeBars(2000, 5), windowMs: 7 * 24 * 3600e3 },
    { label: "1 month, 15m bars", bars: makeBars(2000, 15), windowMs: 30 * 24 * 3600e3 },
    { label: "intraday zoom, 1m bars", bars: makeBars(1000, 1), windowMs: 30 * 60e3 },
  ])("$label -> candle body stays legible", ({ bars, windowMs }) => {
    const px = bodyPx(bars, windowMs)
    expect(px).toBeGreaterThanOrEqual(MIN_BODY_PX)
  })

  it("THE BUG: the old fixed 9-minute bucket fails the wide-zoom case", () => {
    // Documents what regressed, so the assertions above cannot quietly stop
    // testing anything. 430 5m bars over 37h at a fixed 9m target produced
    // 217 candles -> ~5px slot -> ~2.5px body.
    const bars = makeBars(430, 5)
    const fixed = resampleOHLC(bars, 9)
    const fixedBody = (PANEL_PX / fixed.length) * 0.49
    expect(fixedBody).toBeLessThan(MIN_BODY_PX)

    const adaptive = resampleOHLC(bars, displayBucketMinutes(bars, 37 * 3600e3))
    expect((PANEL_PX / adaptive.length) * 0.49).toBeGreaterThanOrEqual(MIN_BODY_PX)
  })

  it("never aggregates below the data's own interval", () => {
    for (const interval of [1, 5, 15]) {
      const bars = makeBars(200, interval)
      // A window so small it holds fewer than MAX_VISIBLE_CANDLES bars.
      expect(displayBucketMinutes(bars, 10 * 60e3)).toBeGreaterThanOrEqual(interval)
      expect(displayBucketMinutes(bars, 10 * 60e3) % interval).toBe(0)
    }
  })

  it("zooming in never produces coarser candles than zooming out", () => {
    const bars = makeBars(2000, 5)
    const windows = [30 * 60e3, 2 * 3600e3, 12 * 3600e3, 24 * 3600e3, 7 * 24 * 3600e3]
    const buckets = windows.map((w) => displayBucketMinutes(bars, w))
    expect(buckets).toEqual([...buckets].sort((a, b) => a - b))
  })

  it("output stays uniformly spaced at every zoom level", () => {
    const bars = makeBars(430, 5)
    for (const w of [2 * 3600e3, 12 * 3600e3, 37 * 3600e3]) {
      const out = resampleOHLC(bars, displayBucketMinutes(bars, w))
      expect(gapMinutes(out)).toHaveLength(1)
    }
  })

  it("output keeps the input's timestamp convention at every zoom level", () => {
    const bars = makeBars(430, 5)
    for (const w of [2 * 3600e3, 37 * 3600e3]) {
      for (const b of resampleOHLC(bars, displayBucketMinutes(bars, w))) {
        expect(b.t).not.toMatch(/Z$/)
      }
    }
  })
})
