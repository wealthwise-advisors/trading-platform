// null is a number as far as JavaScript's comparison operators are concerned,
// and that is the whole hazard here:
//
//     null >= 1.5  -> false   an unbounded factor is not "strong"
//     null <  1.0  -> TRUE    and it IS "below 1.0, lost money overall"
//
// The second one shipped: a run where every trade won — the best outcome
// possible — was told in the insights panel that it "lost money overall".
// strict is off in tsconfig.app.json, so the compiler catches none of this.

import { describe, it, expect } from "vitest"
import {
  profitFactorText, isStrongProfitFactor, isLosingProfitFactor,
} from "./profitFactor"
import { generateInsights } from "./insights"
import type { BacktestSummary } from "./types"

describe("profitFactorText", () => {
  it("prints a finite factor to two decimals", () => {
    expect(profitFactorText(2.5, 10)).toBe("2.50")
    expect(profitFactorText(0, 0)).toBe("0.00")
  })

  it("shows unbounded when the run had winners and no losers", () => {
    expect(profitFactorText(null, 4)).toBe("∞")
  })

  it("shows undefined when there was nothing to divide", () => {
    expect(profitFactorText(null, 0)).toBe("—")
  })

  it("never returns the string 'null' or 'NaN'", () => {
    for (const [pf, wins] of [[null, 0], [null, 3], [1.2, 5]] as const) {
      const out = profitFactorText(pf, wins)
      expect(out).not.toMatch(/null|NaN|undefined/i)
    }
  })
})

describe("the comparisons that null silently wins", () => {
  it("THE BUG: an unbounded factor is not a losing one", () => {
    // null < 1.0 is true. This is the assertion that fails without the guard.
    expect(isLosingProfitFactor(null)).toBe(false)
  })

  it("an unbounded factor counts as strong, but only with winners behind it", () => {
    expect(isStrongProfitFactor(null, 3)).toBe(true)
    expect(isStrongProfitFactor(null, 0)).toBe(false)
  })

  it("a genuinely losing factor is still reported as losing", () => {
    expect(isLosingProfitFactor(0.4)).toBe(true)
    expect(isStrongProfitFactor(0.4, 2)).toBe(false)
  })

  it("the 1.5 threshold still holds for finite values", () => {
    expect(isStrongProfitFactor(1.49, 9)).toBe(false)
    expect(isStrongProfitFactor(1.5, 9)).toBe(true)
  })
})

/** A summary with only the fields the insight rules read. */
function summary(over: Partial<BacktestSummary>): BacktestSummary {
  return {
    win_rate: 80, total_trades: 5, winning_trades: 5, losing_trades: 0,
    profit_factor: null, avg_win: 100, avg_loss: 0, max_drawdown_pct: 1,
    total_return_pct: 5, sharpe_ratio: 1, ...over,
  } as BacktestSummary
}

describe("generateInsights with an unbounded profit factor", () => {
  it("does not tell a flawless run that it lost money", () => {
    const text = generateInsights(summary({})).join(" ")
    expect(text).not.toMatch(/lost money overall/i)
    expect(text).not.toMatch(/below 1\.0/i)
  })

  it("says what actually happened instead", () => {
    const text = generateInsights(summary({})).join(" ")
    expect(text).toMatch(/unbounded|no losing trade/i)
  })

  it("still calls out a real loser", () => {
    const text = generateInsights(summary({
      profit_factor: 0.5, winning_trades: 2, losing_trades: 8, win_rate: 20,
    })).join(" ")
    expect(text).toMatch(/below 1\.0/i)
  })
})
