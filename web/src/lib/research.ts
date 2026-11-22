/** Shapes of the strategy research endpoints (upgrade plan, Feature 6). */

export interface RunSummary {
  id: string
  created_at: string
  symbol: string
  strategy_name: string
  timeframe: string
  total_pnl: number
  total_return_pct: number
  sharpe_ratio: number | null
  max_drawdown_pct: number
  win_rate: number
  total_trades: number
}

type Pcts = Record<"p5" | "p25" | "p50" | "p75" | "p95", number>

export interface MonteCarloSide {
  final_pnl: Pcts
  max_drawdown: Pcts
  max_drawdown_pct: Pcts
  prob_loss: number
  prob_loss_over?: number
  equity_fan: { p5: number[]; p50: number[]; p95: number[] }
}

export interface MonteCarloResult {
  runs: number
  trades: number
  seed: number
  initial_capital: number
  actual: { final_pnl: number; max_drawdown: number; max_drawdown_pct: number }
  shuffle: MonteCarloSide
  bootstrap: MonteCarloSide
}

export interface WalkForwardFold {
  train_start: string; train_end: string; test_start: string; test_end: string
  params: Record<string, number>
  train_return_pct: number
  test_return_pct: number
  test_sharpe: number | null
  test_trades: number
  test_win_rate: number
  test_max_drawdown_pct: number
}

export interface WalkForwardResult {
  folds: WalkForwardFold[]
  notes: string[]
  cancelled: boolean
  equity: { t: string; equity: number }[]
  test_return_pct: number
  test_trades: number
  efficiency: number | null
}

export interface ResearchJob {
  id: string
  kind: string
  status: "running" | "done" | "failed" | "cancelled"
  progress: { done: number; total: number }
  result: WalkForwardResult | null
  error: string | null
  started_at: string
}

/** What a walk-forward efficiency means, in one line. */
export function efficiencyNote(e: number | null): string {
  if (e == null) return "Not measurable: the training windows made no money."
  if (e >= 0.5) return "The optimised edge mostly carried over to unseen data."
  if (e > 0) return "Only part of the optimised edge carried over: some of it was fitted to the past."
  return "The optimised edge did not carry over: it was fitted to the past."
}
