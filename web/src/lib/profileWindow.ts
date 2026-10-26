/**
 * Which bars a timeframe's Volume Profile is built from on Market Grid.
 *
 * Every Market Grid pane shares ONE date range -- the largest day count among
 * the selected timeframes (see daysForSet). Until 2026-10-26 each pane's POC
 * was profiled over all of that range, so selecting 1h (25 D) beside 5m (2 D)
 * gave 5m a 25-day POC. Measured on /ES ending 2026-10-23: 5m read 7770.41
 * where its own 2 days give 7688.20, and POC vs Avg was off by the same.
 *
 * Now each timeframe's profile covers its OWN specified days -- the bars its
 * chart setup would load if it were selected alone -- counted back from the
 * bar being profiled. So at the session's last bar, 5m's POC is exactly the
 * POC of a 5m-only session over the same end date, and during replay it is
 * the last N days as they stood at that moment.
 *
 * Days are CALENDAR days, inclusive, the convention the loader and the day
 * stepper use (see ./dayRange). A timeframe with no specified range (3m, 25m,
 * 35m) keeps the whole loaded range, as before.
 */
import { daysFor } from "./chartSetup"
import { MAX_HISTORY_DAYS, startDateForDays } from "./dayRange"

/**
 * Index of the first bar in `timeframe`'s profile window ending at bar
 * `upto - 1`. `bars` are the pane's bars, ascending, whose `t` is the open
 * time as a naive Eastern ISO string ("2026-10-23T09:30:00"), so a date
 * prefix compares as a string. 0 when the timeframe has no day count or the window covers it all.
 */
export function profileWindowStart(
  bars: readonly { t: string }[], upto: number, timeframe: string,
): number {
  const days = daysFor(timeframe)
  if (days == null || upto <= 0) return 0
  const lastDate = bars[Math.min(upto, bars.length) - 1]?.t.slice(0, 10)
  const from = lastDate ? startDateForDays(lastDate, days, MAX_HISTORY_DAYS) : null
  if (!from) return 0
  // First bar dated on or after `from`; dates ascend, so binary search.
  let lo = 0, hi = Math.min(upto, bars.length)
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (bars[mid].t.slice(0, 10) < from) lo = mid + 1
    else hi = mid
  }
  return lo
}
