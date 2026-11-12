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

/** Same for the same run however many bars have since been added to it. */
export function chartRunKey(bars: ReadonlyArray<{ t: string }>, interval?: string): string {
  return `${interval ?? ""}|${bars[0]?.t ?? ""}`
}

/**
 * The x window to draw, in ms: the user's view (or the default window ending
 * at the last bar), plus `rightSpaceBars` of empty space -- but ONLY when the
 * view reaches the last bar. That space is room after the latest candle.
 *
 * It used to be added to the end of every view. Panned into the middle, the
 * view then ran ~35 minutes past where the drag left it, and the price scale,
 * fitted to the dragged window, did not cover the candles in that extra
 * stretch: real /ES 5m 2026-11-12, lows at 7593.25 under a scale starting at
 * 7601. The step is the bars' own interval (barStepMs), not the average gap,
 * which overnight breaks inflated.
 */
export function xWindowMs(
  t: readonly string[],
  view: { start: number; end: number } | null,
  defaultWindow: number,
  rightSpaceBars: number,
): [number, number] | undefined {
  if (t.length < 2) return undefined
  const first = new Date(t[0]).getTime()
  const last = new Date(t[t.length - 1]).getTime()
  const step = barStepMs(t) || 60_000
  // Dragged past either end, the view stops at the data and keeps its width:
  // clamping each end on its own let a view dragged before the first bar end
  // BEFORE it starts -- an empty, inverted chart.
  const width = view ? Math.max(view.end - view.start, step) : defaultWindow
  const start = Math.max(first, Math.min(view ? view.start : last - defaultWindow, last - step))
  const end = Math.min(last, Math.max(view ? view.end : last, start + Math.min(width, last - start)))
  const pad = end >= last ? step * rightSpaceBars : 0
  return [start, end + pad]
}
