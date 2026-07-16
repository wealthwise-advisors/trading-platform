// Mirrors api/schemas/backtest.py + api/strategy_registry.py

export interface StrategyParam {
  name: string
  label: string
  type: "int" | "float"
  min: number
  max: number
  step: number
  default: number
}

export interface StrategyMeta {
  id: string
  label: string
  params: StrategyParam[]
}

export interface DataSourceMeta {
  id: string
  label: string
  available: boolean
}

export interface BacktestRequest {
  data_source: string
  symbol: string
  timeframe: string
  strategy_id: string
  params: Record<string, number>
  initial_capital: number
  contracts_per_trade: number
  commission_per_contract: number
  start_date: string
  end_date: string
  session_start: string
  session_end: string
  zigzag_dev_3: number
  zigzag_dev_10: number
}

export interface BacktestSummary {
  backtest_id: string
  symbol: string
  strategy_name: string
  timeframe: string
  start_date: string
  end_date: string
  session_start: string
  session_end: string
  data_source: string
  initial_capital: number
  final_capital: number
  total_pnl: number
  total_return_pct: number
  sharpe_ratio: number
  sortino_ratio: number
  max_drawdown_pct: number
  win_rate: number
  profit_factor: number
  avg_win: number
  avg_loss: number
  total_trades: number
  winning_trades: number
  losing_trades: number
  avg_trade_duration_min: number
  data_points: number
}

export interface TradeRecord {
  entry_time: string
  exit_time: string | null
  symbol: string
  direction: "LONG" | "SHORT"
  qty: number
  entry_price: number
  exit_price: number | null
  pnl: number
  commission: number
  duration_min: number | null
  strategy: string
  quality_score: number | null
  quality_grade: string | null
}

export interface OHLCVRecord {
  t: string
  o: number
  h: number
  l: number
  c: number
  v: number | null
}

export interface IndicatorSeries {
  ema9: (number | null)[]
  ema21: (number | null)[]
  rsi2: (number | null)[]
  rsi13: (number | null)[]
  stoch_k: (number | null)[]
  stoch_d: (number | null)[]
}

export interface PriceDataResponse {
  bars: OHLCVRecord[]
  indicators: IndicatorSeries
}

export interface EquityPoint {
  t: string
  equity: number
  drawdown_pct: number
}

export interface ZigZagPoint {
  t: string
  price: number
  type: "H" | "L"
  swing: number
  sub: number
  label: string
}

export interface ZigZagResponse {
  zigzag_10: ZigZagPoint[]
  zigzag_3: ZigZagPoint[]
}

export interface WinLoss {
  wins: number
  losses: number
  win_rate: number
}

export interface CandlestickPatternRecord {
  timestamp: string
  pattern: string
  direction: string
  confidence: number
}

export interface ChartPatternRecord {
  pattern: string
  direction: string
  start: string
  end: string
  neckline: number
  metrics: Record<string, number>
}

export interface MonthlyReturns {
  years: string[]
  months: string[]
  values: (number | null)[][]
}

export interface ReplayCreateRequest {
  symbol: string
  timeframe: string
  strategy_id: string
  params: Record<string, number>
  initial_capital: number
  contracts_per_trade: number
  start_date: string
  end_date: string
}

export interface ReplayCreateResponse {
  replay_id: string
  total_bars: number
  symbol: string
  strategy_name: string
  initial_capital: number
}

export interface ReplayBar {
  t: string
  o: number
  h: number
  l: number
  c: number
  v: number | null
}

export interface ReplayTrade {
  direction: "LONG" | "SHORT"
  qty: number
  entry_time: string
  entry_price: number
  exit_time: string | null
  exit_price: number | null
  pnl: number
  commission: number
  duration_min: number | null
}

export interface ReplaySignal {
  type: "BUY" | "SELL" | "CLOSE"
  reason: string
}

export interface ReplayFrameMessage {
  type: "frame"
  bar: ReplayBar
  signal: ReplaySignal | null
  position: number
  portfolio_value: number
  equity_point: { t: string; equity: number } | null
  completed_trades: ReplayTrade[]
  open_trade: ReplayTrade | null
  bars_processed: number
  total_bars: number
}

export type ReplayWsMessage =
  | ReplayFrameMessage
  | { type: "reset" }
  | { type: "done" }
  | { type: "error"; message: string }

export interface SchwabStatus {
  available: boolean
  authenticated: boolean
  needs_reauth: boolean
  hours_remaining: number
  error: string | null
}

export interface OptimizeRequest {
  data_source: string
  symbol: string
  timeframe: string
  strategy_id: string
  initial_capital: number
  contracts_per_trade: number
  commission_per_contract: number
  start_date: string
  end_date: string
  session_start: string
  session_end: string
  metric: "sharpe_ratio" | "total_return_pct" | "profit_factor"
}

export interface OptimizeCombo {
  params: Record<string, number>
  total_return_pct: number
  sharpe_ratio: number
  win_rate: number
  total_trades: number
  profit_factor: number
  max_drawdown_pct: number
}

export interface OptimizeResponse {
  metric: string
  combos_tested: number
  results: OptimizeCombo[]
  best_backtest_id: string | null
}

export interface WaveSwing {
  t: string
  price: number
  kind: "high" | "low"
  label: string | null
}

export interface WaveImpulse {
  direction: "up" | "down"
  valid: boolean
  rules: Record<string, boolean>
  fib_score: number
  truncated_fifth: boolean
  pivots: WaveSwing[]
}

export interface WaveCorrection {
  type: string
  direction: string
  metrics: Record<string, number | null>
  pivots: WaveSwing[]
}

export interface WaveFibDetail {
  fib_fit: number | null
  detail: Record<string, { achieved: number; nearest_ideal: number; dist: number }>
}

export interface WaveTargetZone {
  center: number
  low: number
  high: number
  strength: number
  members: { price: number; source: string }[]
}

export interface WaveLabel {
  t: string
  price: number
  kind: "high" | "low"
  wave: string          // "1".."11" or "a"/"b"/"c"
  sub: 1 | 2 | null      // confidence tier: 1 = fib+pattern both met, 2 = pattern only
  direction: "up" | "down"
}

export interface WaveAnalysis {
  degree: string
  trend: string
  n_swings: number
  swings: WaveSwing[]
  impulse: WaveImpulse | null
  impulse_fib: WaveFibDetail | null
  correction: WaveCorrection | null
  correction_fib: WaveFibDetail | null
  cycle_position: string
  bias: string
  invalidation: number | null
  target_zones: WaveTargetZone[]
  alternates: string[]
  notes: string[]
  wave_sequence: WaveLabel[]
}

export type ElliottWaveResponse = Record<string, WaveAnalysis>

