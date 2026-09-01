/**
 * Chart setup: how many days of history each timeframe loads.
 *
 * THE TABLE BELOW IS THE ONLY SOURCE OF TRUTH. It was specified for this
 * project on 2026-09-01 and replaces whatever per-timeframe day count the
 * pages applied before.
 *
 *     1m → 2 days     20m → 5 days
 *     5m → 2 days     30m → 10 days
 *     10m → 3 days    45m → 15 days
 *     15m → 4 days     1h → 25 days
 *
 * 1m and 5m share 2 days deliberately. That is not a transcription slip, and
 * the surrounding numbers are not a curve with a gap in it: they are eight
 * separate judgements. Nothing here smooths, fits or extrapolates between
 * them, and nothing should.
 *
 * No value in this file comes from a third-party charting platform. A
 * screenshot of one was shown as a conceptual example of the idea, not as data,
 * and none of its numbers were read into this table.
 *
 * WHAT IT DOES
 * ------------
 * Selecting a timeframe loads that many days -- automatically, every time, not
 * as a setting applied once. The start date moves and the end date stays, so
 * the window is the last N days rather than N days ending wherever it happened
 * to end. Afterwards the dates and the day stepper still work: this sets the
 * range, it does not lock it.
 *
 * TIMEFRAMES THIS TABLE DOES NOT COVER
 * ------------------------------------
 * The app offers eleven; the specification covers eight. 2m, 25m and 35m have
 * no entry, and deliberately get none: `daysFor` returns null and the caller
 * leaves the range exactly as the user had it. Proposed values for those three
 * are in UNSPECIFIED below, awaiting a decision -- they are NOT applied.
 *
 * The app has no 2h, 4h, Daily or Weekly timeframe, so there is nothing to
 * decide for those. If any is ever added it lands here with no entry, changes
 * no range, and shows as unset until someone gives it a number.
 */

/** Exactly as specified. Eight entries; do not add a ninth by inference. */
const SPECIFIED: Record<string, number> = {
  "1m": 2,
  "5m": 2,
  "10m": 3,
  "15m": 4,
  "20m": 5,
  "30m": 10,
  "45m": 15,
  "1h": 25,
}

/**
 * PROPOSALS, NOT SETTINGS. Nothing reads these to load data.
 *
 * The three intervals the app offers that the table does not cover. Each value
 * is the specified entry for the nearest interval BELOW it -- not an average
 * across the gap -- so that adopting one would never hand a coarser bar less
 * history than the finer bar beneath it:
 *
 *   2m  → 2, the same as 1m and 5m, which agree either side of it
 *   25m → 5, as specified for 20m
 *   35m → 10, as specified for 30m
 *
 * Move an entry into SPECIFIED to adopt it. Until then the UI shows these
 * timeframes as unset and selecting one leaves the date range alone.
 */
export const UNSPECIFIED: Record<string, number> = {
  "2m": 2,
  "25m": 5,
  "35m": 10,
}

/** Every timeframe both pages offer, in bar-interval order. */
export const ALL_CHART_TIMEFRAMES = [
  "1m", "2m", "5m", "10m", "15m", "20m", "25m", "30m", "35m", "45m", "1h",
] as const

/** Does this timeframe have a specified day count? */
export function isSpecified(timeframe: string): boolean {
  return timeframe in SPECIFIED
}

/**
 * Days of history to load for `timeframe`, or null when the table has no
 * entry for it.
 *
 * Null, never a fallback. A number nobody chose would move someone's dates on
 * our authority rather than theirs, and it would look identical on screen to
 * the eight that were actually specified.
 */
export function daysFor(timeframe: string): number | null {
  return SPECIFIED[timeframe] ?? null
}

/**
 * Days for a SET of timeframes -- the Market Grid case, where every pane
 * shares one date range.
 *
 * The largest specified entry among them wins. The coarsest pane needs the
 * most history to show anything, and a range that satisfies it contains every
 * finer pane's. Timeframes with no entry are skipped rather than treated as
 * zero, and a selection containing none of the eight returns null so the range
 * is left alone.
 */
export function daysForSet(timeframes: readonly string[]): number | null {
  const known = timeframes.map(daysFor).filter((d): d is number => d != null)
  return known.length ? Math.max(...known) : null
}
