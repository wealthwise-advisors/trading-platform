/**
 * How much of the price chart is on screen before any zoom or pan.
 *
 * Two hours, for every bar size up to 1h -- the window the chart has always
 * opened on. A 2h or 4h bar is as wide as that whole window, so it would open on
 * one candle or less. From 2-hour bars up, the default is the last
 * DEFAULT_WINDOW_BARS bars instead, measured between the bars' own timestamps so
 * overnight gaps and weekends do not shrink it.
 *
 * The candle aggregation, the swing-header spacing, the price range and the
 * time range all read this one value, so they always agree about the window.
 */

export const DEFAULT_WINDOW_MS = 2 * 60 * 60 * 1000

/** Bars shown by default once each bar is as wide as the two-hour window. */
export const DEFAULT_WINDOW_BARS = 40

/** The bar size: the smallest gap between consecutive timestamps near the start. */
export function barStepMs(t: readonly string[]): number {
  let step = Infinity
  for (let i = 1; i < Math.min(t.length, 60); i++) {
    const gap = new Date(t[i]).getTime() - new Date(t[i - 1]).getTime()
    if (gap > 0 && gap < step) step = gap
  }
  return Number.isFinite(step) ? step : 0
}

export function defaultWindowMs(t: readonly string[]): number {
  if (t.length < 2 || barStepMs(t) < DEFAULT_WINDOW_MS) return DEFAULT_WINDOW_MS
  const last = new Date(t[t.length - 1]).getTime()
  const start = new Date(t[Math.max(0, t.length - DEFAULT_WINDOW_BARS)]).getTime()
  return Math.max(last - start, DEFAULT_WINDOW_MS)
}

/**
 * The span the candle aggregation should be told the default view covers.
 *
 * Not defaultWindowMs. That window is clock time and includes the overnight
 * gaps and weekends between bars, while the aggregation turns a span into a
 * bar count by dividing by the bar size. Across forty 2h bars that reads as
 * several times as many bars, and it merged them into 4h candles. For bars of
 * two hours and up the default view IS a bar count, so this hands over exactly
 * that; for every smaller bar it is the same two hours as before.
 */
export function defaultAggregationSpanMs(t: readonly string[]): number {
  const step = barStepMs(t)
  if (t.length < 2 || step < DEFAULT_WINDOW_MS) return DEFAULT_WINDOW_MS
  return Math.min(t.length, DEFAULT_WINDOW_BARS) * step
}
