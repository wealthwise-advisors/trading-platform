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

export interface DateWindow {
  /** YYYY-MM-DD */
  start: string
  /** YYYY-MM-DD */
  end: string
}

export interface SymbolMeta {
  symbol: string
  name: string
  /** False means no contract economics are configured, so the engine falls
   *  back to the E-mini default and the resulting P&L is not meaningful. */
  has_spec: boolean
  /** Date windows this symbol actually has data for, oldest first. Present
   *  only for file-backed sources. Several windows rather than one span
   *  because coverage is often not continuous — the bundled ES sample is
   *  2008 plus 2022–2025, with nothing in between. */
  coverage?: DateWindow[]
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
  session_start: string | null
  session_end: string | null
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
  session_start: string | null
  session_end: string | null
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
  /** Session VWAP and its ±2σ bands. All-null when the dataset has no volume
   *  column — VWAP is undefined without volume, so the chart draws nothing
   *  rather than a fabricated line. Optional so an older cached response
   *  without these keys still type-checks. */
  vwap?: (number | null)[]
  vwap_upper?: (number | null)[]
  vwap_lower?: (number | null)[]
}

/** Volume traded at each price level, with the point of control and the
 *  value-area bounds. Empty / null throughout when the dataset has no volume —
 *  a profile without volume cannot be approximated, so nothing is drawn. */
export interface VolumeProfile {
  prices: number[]
  volumes: number[]
  /** Price level holding the most volume. */
  poc: number | null
  /** Value Area Low / High — bounds of the ~70% volume band around the POC. */
  val: number | null
  vah: number | null
  bin_size: number | null
}

export interface PriceDataResponse {
  bars: OHLCVRecord[]
  indicators: IndicatorSeries
  volume_profile?: VolumeProfile
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

// ── Elliott Wave ────────────────────────────────────────────────────────────
// Mirrors api/schemas/elliott_wave.py. Two absences are deliberate and must
// stay absent: there is no confidence/score/probability field (SRS FR-7.4 --
// the reference states no weighting function), and no valid/violated_rules
// field (a candidate failing an implementable gate is never created).

export interface EWPivot {
  index: number
  /** Bar at which the reversal confirmed this pivot; always > index.
   *  A consumer at bar t may only use pivots with confirm_index <= t. */
  confirm_index: number
  t: string
  price: number
  kind: "H" | "L"
  /** Ladder index, NOT an Elliott degree -- degree naming is OQ-17, open. */
  scale: number
}

/** gated = passed every implementable gate. undecidable = passed everything
 *  evaluable, but acceptance depends on a rule blocked by an open question. */
export type EWState = "enumerated" | "gated" | "measured" | "undecidable"

export type EWStructureType =
  | "impulse"
  | "leading_diagonal"
  | "ending_diagonal"
  | "zigzag"
  | "flat"
  | "flat_running"

export interface EWWave {
  id: string
  scale: number
  state: EWState
  label: string | null
  structure_type: EWStructureType | null
  direction: "up" | "down" | null
  start_t: string
  start_price: number
  end_t: string
  end_price: number
  parent_id: string | null
  child_ids: string[]
  /** Raw guideline ratios. Recorded, never "matched" -- OQ-05 is open. */
  measurements: Record<string, number | string | boolean | null>
  /** Rule / open-question ids that prevented a decision. */
  blocked_by: string[]
}

export interface EWBlockedRule {
  rules: string[]
  oq: string
  reason: string
}

export interface ElliottWaveResponse {
  engine_version: string
  config: Record<string, unknown>
  pivots: EWPivot[]
  waves: EWWave[]
  blocked_rules: EWBlockedRule[]
  notes: string[]
  counts: {
    pivots: number
    waves: number
    structures: number
    structures_by_type: Record<string, number>
    structures_by_state: Record<string, number>
    blocked_rule_ids: number
  }
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
  commission_per_contract?: number
  session_start?: string | null
  session_end?: string | null
  /** Multi-timeframe grid; omit for the legacy single-timeframe session. */
  timeframes?: string[]
  data_source?: string
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
  timeframes: string[]
  base_timeframe: string
  /** Set when an overnight session made the fetch reach back a day earlier than
   *  asked, so its first session is whole. Null when unchanged. */
  fetch_start_date?: string | null
  /** Resolution the bars were fetched at. Anything finer needs a new session. */
  data_timeframe?: string
  bar_counts: Record<string, number>
  data_source: string
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
  /** Session VWAP and its +/-2 sigma bands. Always shipped at 2 sigma so the
   *  client can recover sigma as (upper - vwap) / 2 and re-scale to whatever
   *  deviation the user selects without another round trip. */
  vwap: number | null
  vwap_upper: number | null
  vwap_lower: number | null
}

/** One clock tick: every pane that produced a new bar, sent together so the
 *  grid can never paint half-updated. Panes that did not advance are absent. */
export interface ReplayFramesMessage {
  type: "frames"
  market_time: string | null
  ticks_processed: number
  total_ticks: number
  frames: Record<string, ReplayFrameMessage>
}

/** History for a pane added part-way through a session.
 *
 *  `bars` are the pane's already-closed bars (capped server-side, hence
 *  `truncated`); `state` is the ONE frame that settles every scalar, because
 *  position / portfolio value / completed trades are all carried cumulatively
 *  in a frame rather than as deltas. `state` is null when the pane has not
 *  closed a bar yet -- e.g. a 1h pane added four minutes into the session. */
export interface ReplayBackfill {
  /** Each bar carries its own VWAP triple, so a timeframe added part-way
   *  through has real band values on its historical rows rather than blanks. */
  bars: (ReplayBar & {
    vwap?: number | null
    vwap_upper?: number | null
    vwap_lower?: number | null
  })[]
  bars_closed: number
  truncated: boolean
  state: ReplayFrameMessage | null
}

/** Reply to `add_timeframes`. `rejected` lists timeframes FINER than the
 *  resolution the session's data was loaded at -- they cannot be resampled out
 *  of what is in memory, so they need a fresh session rather than a pane. */
export interface ReplayTimeframesMessage {
  type: "timeframes"
  timeframes: string[]
  base_timeframe: string
  data_timeframe: string
  bar_counts: Record<string, number>
  added: string[]
  rejected: string[]
  backfill: Record<string, ReplayBackfill>
}

export type ReplayWsMessage =
  | ReplayFramesMessage
  | ReplayFrameMessage
  | ReplayTimeframesMessage
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
  session_start: string | null
  session_end: string | null
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


