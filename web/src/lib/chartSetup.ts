/**
 * Chart setup: how many days of history each timeframe is charted over.
 *
 * The numbers are not ours. They were specified for this project on
 * 2026-09-01, and they encode a working trader's judgement about how much
 * history a given bar interval is worth reading:
 *
 *     1m → 2 days     20m → 5 days
 *     5m → 2 days     30m → 10 days
 *     10m → 3 days    45m → 15 days
 *     15m → 4 days     1h → 25 days
 *
 * The shape is deliberate. A finer bar is for reading the last session or two
 * in detail; a coarser one is for reading structure, and structure needs weeks.
 * Charting 1m over 25 days is not "more information", it is the same screen
 * with the detail compressed out of it.
 *
 * WHY THIS IS A PRESET AND NOT A RULE
 * -----------------------------------
 * Selecting a timeframe MOVES the date range to its preset, and then the range
 * is the user's again -- the day stepper and both date fields keep working, and
 * nothing snaps back. The preset is a starting point that is right most of the
 * time, not a constraint. `daysFor` is the only place the numbers live, so the
 * two pages cannot drift apart.
 *
 * THREE INTERVALS WERE NOT SPECIFIED
 * ----------------------------------
 * The app offers eleven timeframes and the specification covers eight. 2m, 25m
 * and 35m have no given value, so they are interpolated from their neighbours
 * on either side rather than guessed at -- see INTERPOLATED. They are marked in
 * the UI, because a number someone chose and a number we derived should not
 * look alike to whoever reads the screen next.
 */

/** Minutes per bar, for interpolating and for ordering. */
const TF_MINUTES: Record<string, number> = {
  "1m": 1, "2m": 2, "5m": 5, "10m": 10, "15m": 15, "20m": 20,
  "25m": 25, "30m": 30, "35m": 35, "45m": 45, "1h": 60,
}

/** Exactly as specified. Do not adjust these without asking. */
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
 * Derived, not given. Linear between the specified neighbours on either side,
 * rounded up so a coarser bar never gets LESS history than a finer one:
 *
 *   2m  sits between 1m (2) and 5m (2)   → 2
 *   25m sits between 20m (5) and 30m (10) → 8
 *   35m sits between 30m (10) and 45m (15) → 12
 */
const INTERPOLATED: Record<string, number> = {
  "2m": 2,
  "25m": 8,
  "35m": 12,
}

export const CHART_SETUP: Record<string, number> = { ...SPECIFIED, ...INTERPOLATED }

/** Timeframes in bar-interval order, for rendering the setup table. */
export const CHART_SETUP_ORDER = Object.keys(CHART_SETUP)
  .sort((a, b) => TF_MINUTES[a] - TF_MINUTES[b])

/** Was this timeframe's day count given to us, or did we derive it? */
export function isSpecified(timeframe: string): boolean {
  return timeframe in SPECIFIED
}

/**
 * Days of history to chart `timeframe` over, or null if we have no preset.
 *
 * Null rather than a fallback number: a caller that gets null should leave the
 * user's range alone, which is honest. Inventing a default here would silently
 * move someone's dates on the strength of a number nobody chose.
 */
export function daysFor(timeframe: string): number | null {
  return CHART_SETUP[timeframe] ?? null
}

/**
 * Days to chart a SET of timeframes over -- the Market Grid case, where every
 * pane shares one date range.
 *
 * The largest preset among them wins. The coarsest pane is the one that needs
 * the most history to show anything at all, and a range that satisfies it also
 * contains every finer pane's. Taking the smallest instead would leave a 1h
 * pane with two days of bars, which is a pane with nothing in it.
 */
export function daysForSet(timeframes: readonly string[]): number | null {
  const known = timeframes.map(daysFor).filter((d): d is number => d != null)
  return known.length ? Math.max(...known) : null
}
