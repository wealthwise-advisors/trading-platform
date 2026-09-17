/**
 * Profit factor, in one place, because null is a number in JavaScript's eyes.
 *
 * The API sends `null` when there is no finite ratio: winners and no losers is
 * unbounded, nothing won and nothing lost is undefined. TypeScript does not
 * protect the call sites -- `strict` is off in tsconfig.app.json, so
 * `pf.toFixed(2)` on a null compiles and then throws at runtime -- and the
 * comparisons are worse than the crash:
 *
 *     null >= 1.5   // false  -- an unbounded factor is not "good"
 *     null <  1.0   // TRUE   -- and it IS "below 1.0, lost money overall"
 *
 * That second line is why this module exists. Coerced to 0, an infinite profit
 * factor -- the best result a run can have -- produced the sentence "this run
 * lost money overall" in the insights panel. Guard the null explicitly; never
 * let it fall into an arithmetic comparison.
 */

/** Display text. `winningTrades` decides unbounded vs undefined. */
export function profitFactorText(pf: number | null, winningTrades: number): string {
  if (pf == null) return winningTrades > 0 ? "∞" : "—"
  return pf.toFixed(2)
}

/** True only for a genuinely strong factor — an unbounded one included. */
export function isStrongProfitFactor(pf: number | null, winningTrades: number): boolean {
  if (pf == null) return winningTrades > 0
  return pf >= 1.5
}

/** True only when the run really did lose money. Never for null. */
export function isLosingProfitFactor(pf: number | null): boolean {
  return pf != null && pf < 1.0
}
