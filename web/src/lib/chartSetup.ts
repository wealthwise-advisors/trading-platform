/**
 * Chart setup: how many days of history each timeframe loads.
 *
 * THE TABLE BELOW IS THE ONLY SOURCE OF TRUTH. It was specified for this
 * project on 2026-09-01 and replaces whatever per-timeframe day count the
 * pages applied before.
 *
 *     1m → 2 days     20m → 5 days      2h → 180 days
 *     5m → 2 days     30m → 10 days     4h → 180 days
 *     10m → 3 days    45m → 15 days     1d → Max (20 years)
 *     15m → 4 days     1h → 25 days     1w → Max (20 years)
 *
 * 1m and 5m share 2 days deliberately. That is not a transcription slip, and
 * the surrounding numbers are not a curve with a gap in it: they are separate
 * judgements. Nothing here smooths, fits or extrapolates between them, and
 * nothing should.
 *
 * WHERE THE NUMBERS COME FROM
 * ---------------------------
 * The first eight were specified on 2026-09-01 and owe nothing to any
 * third-party charting platform; a screenshot of one was shown then as an
 * example of the idea, not as data.
 *
 * 2h and 4h were added on 2026-09-15 at 180 days each, and those two values
 * ARE the reference platform's own defaults, read from its interval list in a
 * screenshot shared that day. They were proposed with that source stated and
 * adopted by explicit approval. 180 days also sits inside what Schwab serves
 * for the 30-minute bars both are built from (see INTRADAY_LOOKBACK_DAYS in
 * src/data/schwab_provider.py).
 *
 * 1d and 1w were added on 2026-09-16 as "Max", the reference platform's own
 * entry for them, also by approval. Max is MAX_HISTORY_DAYS (twenty years): a
 * concrete range the date fields can show. Neither is offered by Market Grid,
 * which replays from 1-minute bars -- see INTRADAY_TIMEFRAMES.
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
 * The app offers fifteen; the table covers twelve. 2m, 25m and 35m have no
 * entry, and deliberately get none: `daysFor` returns null and the caller
 * leaves the range exactly as the user had it -- unless it is longer than that
 * timeframe can be served (see startDateForTimeframe). Proposed values for
 * those three are in UNSPECIFIED below, awaiting a decision -- they are NOT
 * applied.
 */
import { MAX_HISTORY_DAYS, MAX_RANGE_DAYS, daysInRange, startDateForDays } from "./dayRange"

/** Exactly as specified. Twelve entries; do not add a thirteenth by inference. */
const SPECIFIED: Record<string, number> = {
  "1m": 2,
  "5m": 2,
  "10m": 3,
  "15m": 4,
  "20m": 5,
  "30m": 10,
  "45m": 15,
  "1h": 25,
  "2h": 180,
  "4h": 180,
  "1d": MAX_HISTORY_DAYS,
  "1w": MAX_HISTORY_DAYS,
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

/** Every timeframe Backtest and Export Data offer, in bar-interval order. */
export const ALL_CHART_TIMEFRAMES = [
  "1m", "2m", "5m", "10m", "15m", "20m", "25m", "30m", "35m", "45m", "1h", "2h", "4h", "1d", "1w",
] as const

/** Daily and weekly bars -- whole trading days, not a bin within one. */
export function isDailyOrLonger(timeframe: string): boolean {
  return timeframe === "1d" || timeframe === "1w"
}

/**
 * The timeframes Market Grid offers: every one but daily and weekly. It builds
 * every pane from 1-minute bars, which cannot reach back the years a daily bar
 * is for (see _source_timeframe in api/routers/replay.py).
 */
export const INTRADAY_TIMEFRAMES: string[] = ALL_CHART_TIMEFRAMES.filter((tf) => !isDailyOrLonger(tf))

/** The longest date range a timeframe can be served over. */
export function maxRangeDaysFor(timeframe: string): number {
  return isDailyOrLonger(timeframe) ? MAX_HISTORY_DAYS : MAX_RANGE_DAYS
}

/** Does this timeframe have a specified day count? */
export function isSpecified(timeframe: string): boolean {
  return timeframe in SPECIFIED
}

/** Is its specified range "Max" -- all the history offered? */
export function isMaxHistory(timeframe: string): boolean {
  return daysFor(timeframe) === MAX_HISTORY_DAYS
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

/**
 * The start date that charts `timeframe` over its specified history, counting
 * back from `endISO`, or null when nothing should move.
 *
 * This is the whole behaviour the pages apply on a timeframe change, in one
 * place where it can be tested. It used to be four lines inlined into each of
 * two components -- so the rule that actually reaches the user (which end
 * moves, and when nothing moves at all) was only ever exercised by rendering
 * a form.
 *
 * Null covers both reasons to leave the range alone: a timeframe the table
 * does not cover, and an end date that is mid-edit and unparseable. The caller
 * writes nothing in either case, rather than writing a date derived from a
 * number nobody chose or from a string that is not yet a date.
 */
export function startDateForTimeframe(
  endISO: string, timeframe: string, currentStartISO?: string,
): string | null {
  const days = daysFor(timeframe)
  const max = maxRangeDaysFor(timeframe)
  if (days != null) return startDateForDays(endISO, days, max)
  // No day count: the range stays as it is -- unless it is longer than this
  // timeframe can be served, as after switching from Daily's twenty years to
  // 2m. Then it shortens to the longest this timeframe allows, rather than
  // asking for twenty years of 2-minute bars.
  if (currentStartISO) {
    const span = daysInRange(currentStartISO, endISO)
    if (span != null && span > max) return startDateForDays(endISO, max, max)
  }
  return null
}

/** The same for a SET of timeframes sharing one range -- see daysForSet. */
export function startDateForTimeframes(
  endISO: string, timeframes: readonly string[],
): string | null {
  const days = daysForSet(timeframes)
  return days == null ? null : startDateForDays(endISO, days)
}
