/**
 * Price display, in the same shape the reference platform prints.
 *
 * DISPLAY ONLY. Nothing here touches a stored or computed value -- strategy
 * signals, backtests and the API all keep full precision. This is the last
 * step before a number becomes text on screen.
 *
 * The convention, read off thirty VWAP/band values and the OHLC beside them on
 * thinkorswim tooltips: at most two decimals, with trailing zeros stripped.
 *
 *     7809.8986  ->  "7809.9"
 *     7810.0000  ->  "7810"
 *     7794.9000  ->  "7794.9"
 *     7816.2500  ->  "7816.25"
 *
 * Not rounding to whole numbers. That was considered and is wrong: 26 of the
 * 30 observed values carry two decimals, and printing 7809.89 as "7810" would
 * make the two screens LESS alike, not more. The three whole numbers seen
 * (7810, 7828, 7795) are genuinely .00 with the zeros trimmed.
 */

/** A price as the reference platform would print it. */
export function price(x: number | null | undefined, dash = "—"): string {
  if (x == null || Number.isNaN(x)) return dash
  // toFixed first so the rounding happens at 2dp, then Number() drops the
  // trailing zeros. Doing it the other way round would keep float noise.
  return String(Number(x.toFixed(2)))
}

/** Signed change, same trimming, explicit + so direction reads at a glance. */
export function delta(x: number | null | undefined, dash = "—"): string {
  if (x == null || Number.isNaN(x)) return dash
  const s = String(Number(x.toFixed(2)))
  return x >= 0 ? `+${s}` : s
}
