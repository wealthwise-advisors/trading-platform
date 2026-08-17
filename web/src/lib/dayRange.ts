/**
 * "Number of days" over the existing inclusive start/end date range.
 *
 * DELIBERATELY NOT NEW STATE. The dates remain the single source of truth: the
 * day count is DERIVED from them, and the stepper writes back an end date.
 * Storing the count separately would let it disagree with the dates the request
 * actually carries — which is the sort of drift that produces a screen showing
 * "4 days" over a 9-day range.
 *
 * CONVENTION, matching what the loaders already do
 * ------------------------------------------------
 * Both ends are INCLUSIVE. external_csv_provider filters with
 * `(index >= start) & (index <= end)` and csv_provider uses `df.loc[start:end]`,
 * so a range where start equals end is one day, not zero.
 *
 * The unit is CALENDAR days, not trading days. Asking for 7 days spanning a
 * weekend yields 7 calendar days containing roughly 5 days of bars — the
 * existing session and fetch logic already drops dates with no data, and
 * inventing a holiday calendar here was explicitly out of scope.
 */

/**
 * Largest span offered, mirroring INTRADAY_LOOKBACK_DAYS in
 * src/data/schwab_provider.py.
 *
 * That value was measured rather than documented — single-day probes bisected
 * the boundary at roughly 204 days for /ES 5m — and 180 was chosen to sit
 * comfortably inside it. Offering more here would advertise ranges the provider
 * cannot serve, so the cap is deliberately the same number. Kept as a named
 * constant so the two move together if that measurement is ever revisited.
 */
export const MAX_RANGE_DAYS = 180

/** Smallest span: start and end on the same day. */
export const MIN_RANGE_DAYS = 1

const MS_PER_DAY = 86_400_000

/** An ISO date (YYYY-MM-DD) parsed as UTC midnight, so no timezone drift. */
function parseISODate(iso: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null
  const d = new Date(`${iso}T00:00:00Z`)
  return Number.isNaN(d.getTime()) ? null : d
}

function toISODate(d: Date): string {
  return d.toISOString().slice(0, 10)
}

export function clampDays(days: number): number {
  if (!Number.isFinite(days)) return MIN_RANGE_DAYS
  return Math.min(MAX_RANGE_DAYS, Math.max(MIN_RANGE_DAYS, Math.trunc(days)))
}

/**
 * Inclusive day count of a range. Same date on both sides is 1.
 *
 * Returns null when either date is unparseable, so a caller can leave the
 * stepper alone rather than guess — a half-typed date field should not silently
 * rewrite the other one.
 */
export function daysInRange(startISO: string, endISO: string): number | null {
  const s = parseISODate(startISO)
  const e = parseISODate(endISO)
  if (!s || !e) return null
  const span = Math.round((e.getTime() - s.getTime()) / MS_PER_DAY) + 1
  return span < MIN_RANGE_DAYS ? MIN_RANGE_DAYS : span
}

/**
 * The end date that makes the range exactly `days` long, counting from start.
 *
 * days = 1 returns start itself; days = 4 returns start + 3, which is four
 * calendar days inclusive.
 */
export function endDateForDays(startISO: string, days: number): string | null {
  const s = parseISODate(startISO)
  if (!s) return null
  const d = new Date(s.getTime() + (clampDays(days) - 1) * MS_PER_DAY)
  return toISODate(d)
}

/**
 * The start date that makes the range exactly `days` long, counting back from
 * end. Used where the end is the fixed edge (the most recent data available).
 */
export function startDateForDays(endISO: string, days: number): string | null {
  const e = parseISODate(endISO)
  if (!e) return null
  const d = new Date(e.getTime() - (clampDays(days) - 1) * MS_PER_DAY)
  return toISODate(d)
}

/**
 * The end date one step away from the CURRENT range.
 *
 * Takes the existing end rather than a day count, so successive calls compose.
 * The stepper originally computed an absolute date from the count it had
 * rendered with; three quick clicks then all read the same count and produced
 * the same date, so a burst of clicks advanced one day instead of three.
 * Passing the live end date through makes each step relative to the last.
 */
export function steppedEndDate(
  startISO: string,
  currentEndISO: string,
  delta: number,
): string {
  const days = daysInRange(startISO, currentEndISO)
  if (days == null) return currentEndISO
  return endDateForDays(startISO, clampDays(days + delta)) ?? currentEndISO
}
