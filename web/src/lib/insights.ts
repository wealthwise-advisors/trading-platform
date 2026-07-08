// TS port of ui/components/insights.py's generate_insights()/generate_ai_insight().
// Plain threshold checks on a BacktestSummary -- no LLM, no external call.
// Kept in sync manually with the Python version; if you change one, change both.

import type { BacktestSummary } from "./types"

export function generateInsights(s: BacktestSummary): string[] {
  const insights: string[] = []
  if (s.total_trades === 0) return ["No trades were taken in this period — nothing to evaluate yet."]

  if (s.win_rate >= 70) {
    insights.push(`Strategy shows a high win rate (${s.win_rate.toFixed(0)}%).`)
  } else if (s.win_rate < 40) {
    insights.push(`Win rate is low (${s.win_rate.toFixed(0)}%) — review entry conditions.`)
  }

  if (s.max_drawdown_pct <= 5) {
    insights.push(`Max drawdown is under control (${s.max_drawdown_pct.toFixed(1)}%).`)
  } else {
    insights.push(`Max drawdown is significant (${s.max_drawdown_pct.toFixed(1)}%) — consider tighter risk limits.`)
  }

  if (s.profit_factor >= 1.5) {
    insights.push(`Profit factor (${s.profit_factor.toFixed(2)}) suggests a solid edge.`)
  } else if (s.profit_factor < 1.0) {
    insights.push(`Profit factor is below 1.0 (${s.profit_factor.toFixed(2)}) — this run lost money overall.`)
  }

  if (s.total_trades < 10) {
    insights.push(`Only ${s.total_trades} trades — treat these results as preliminary.`)
  }

  return insights.slice(0, 4)
}

export function generateAiInsight(s: BacktestSummary): string {
  if (s.total_trades === 0) {
    return "No trades to analyze — try a longer date range or looser entry parameters."
  }
  if (s.avg_loss && Math.abs(s.avg_loss) > s.avg_win * 1.5 && s.avg_win > 0) {
    return "Average loss is notably larger than average win — consider tightening stop-loss distance."
  }
  if (s.win_rate > 65 && s.profit_factor < 1.2) {
    return "High win rate but thin profit factor — winners may be cut short relative to losers; consider letting profits run longer."
  }
  if (s.max_drawdown_pct > 15) {
    return "Drawdown is deep relative to returns — consider reducing position size or adding a volatility filter."
  }
  return "No strong red flags in this run — test across a longer date range to confirm robustness."
}
