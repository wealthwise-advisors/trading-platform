// Display-only aggregation of bars into wider buckets, purely so each candle
// gets more horizontal pixels (candle width is driven by how many bars are
// packed into the visible range -- no Plotly line-width setting can widen the
// body itself). Only the candlestick trace's own OHLC arrays use this;
// EMA/RSI/Stoch lines, zigzag swing markers, and trade entry/exit markers all
// keep the original per-bar timestamps, since they're plotted on the same
// continuous date axis and never needed to align with candle boundaries.
//
// Lives in lib/ rather than inside the chart component so the bucketing and
// timestamp rules can be tested directly -- both have shipped bugs before.

import type { OHLCVRecord } from "@/lib/types"
import { formatterFor } from "@/lib/isoTime"

/**
 * Most candles that stay legible across a ~1100px price panel.
 *
 * Measured on the rendered SVG: Plotly draws a candle body at roughly half its
 * slot, so 217 candles in 1103px gave a 5.08px slot and a 2.48px body -- a
 * hairline, swamped by the 12px entry/exit markers drawn over it. 90 candles
 * gives a ~12px slot and a ~6px body, which reads as a candle.
 */
const MAX_VISIBLE_CANDLES = 90

/** Median positive gap between consecutive bars, in ms. */
function nativeStepMs(bars: OHLCVRecord[]): number {
  const deltas: number[] = []
  for (let i = 1; i < bars.length; i++) {
    deltas.push(Date.parse(bars[i].t) - Date.parse(bars[i - 1].t))
  }
  const positive = deltas.filter((d) => d > 0).sort((a, b) => a - b)
  return positive.length ? positive[Math.floor(positive.length / 2)] : 60_000
}

/**
 * Display bucket width, in minutes, for a given visible window.
 *
 * Candle width in Plotly comes from the spacing of the x values, so it scales
 * with how much time is on screen. A single fixed bucket cannot serve both
 * ends: the old hardcoded 9-minute target gave a comfortable 40px body in the
 * default 2-hour window, but the same data zoomed out to a 37-hour Globex
 * range packed 217 candles into the panel at 2.48px each. Sizing the bucket
 * from the window keeps the on-screen candle count -- and so the candle
 * width -- roughly constant at every zoom level.
 *
 * Returns a whole multiple of the data's own interval; resampleOHLC snaps to
 * that grid anyway, and returning the native interval means "do not aggregate".
 */
export function displayBucketMinutes(bars: OHLCVRecord[], windowMs: number): number {
  if (bars.length < 2) return 1
  const stepMs = nativeStepMs(bars)
  const span = Math.max(windowMs, stepMs)
  const barsInWindow = span / stepMs
  const multiple = Math.max(1, Math.ceil(barsInWindow / MAX_VISIBLE_CANDLES))
  return (stepMs * multiple) / 60_000
}

export function resampleOHLC(bars: OHLCVRecord[], targetMinutes: number): OHLCVRecord[] {
  if (bars.length < 2 || targetMinutes <= 1) return bars

  // Bucket width must be a whole multiple of the data's own bar interval, and
  // every emitted timestamp must sit on that grid.
  //
  // Both matter for how WIDE Plotly draws each candle: it takes the smallest
  // gap between consecutive x values as the slot width. Bucketing 5-minute
  // bars into 9-minute windows and emitting the first bar's own timestamp
  // produced 09:30, 09:35, 09:45, 09:55, 10:00, ... -- a mix of 5- and
  // 10-minute gaps (measured: 5min x10, 10min x34). Plotly then sized every
  // candle to the 5-minute minimum while most sat 10 minutes apart, so each
  // body filled about a quarter of its slot and the series read as thin,
  // sparse sticks. Snapping to a multiple of the native interval keeps the
  // spacing uniform, so the bodies fill the slot they are given.
  const stepMs = (() => {
    const deltas: number[] = []
    for (let i = 1; i < bars.length; i++) {
      deltas.push(Date.parse(bars[i].t) - Date.parse(bars[i - 1].t))
    }
    const positive = deltas.filter((d) => d > 0).sort((a, b) => a - b)
    return positive.length ? positive[Math.floor(positive.length / 2)] : 60_000
  })()

  const target = targetMinutes * 60_000
  const bucketMs = Math.max(1, Math.round(target / stepMs)) * stepMs
  if (bucketMs <= stepMs) return bars

  const order: number[] = []
  const buckets = new Map<number, OHLCVRecord[]>()
  for (const b of bars) {
    const key = Math.floor(Date.parse(b.t) / bucketMs) * bucketMs
    if (!buckets.has(key)) { buckets.set(key, []); order.push(key) }
    buckets.get(key)!.push(b)
  }

  // Every millisecond figure derived here has to be turned back into a string
  // in the SAME convention the incoming bars use, or the candles land on a
  // different part of the axis than every other trace. See lib/isoTime.ts.
  const fmt = formatterFor(bars[0].t)

  return order.map((key) => {
    const grp = buckets.get(key)!
    return {
      // The bucket's grid position, not grp[0].t -- this is what keeps the
      // spacing uniform.
      t: fmt(key),
      o: grp[0].o,
      h: Math.max(...grp.map((g) => g.h)),
      l: Math.min(...grp.map((g) => g.l)),
      c: grp[grp.length - 1].c,
      v: grp.reduce((sum, g) => sum + (g.v ?? 0), 0),
    }
  })
}
