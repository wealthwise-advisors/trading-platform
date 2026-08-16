// Multi-Timeframe Live View: configure a strategy, pick one or more
// timeframes, then watch them all trade forward together over a WebSocket.
//
// The server runs one ReplayEngine per timeframe off a single market clock
// (src/backtesting/multi_replay.py) and sends ONE message per tick carrying
// every pane that produced a bar. Coarse panes appear in far fewer messages
// than fine ones -- a 1h pane updates on 1 tick in 60 against a 1m base --
// which is what keeps the grid showing one shared moment in the market.
//
// Selecting a single timeframe yields a grid of one, so the original
// single-pane behaviour is the degenerate case rather than a separate path.

import { useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { SchwabAuthWidget } from "@/components/SchwabAuthWidget"
import { bandAgreement, agreeingLabels } from "@/lib/bandAgreement"
import type { ReplayBar, ReplayTrade, ReplaySignal, ReplayWsMessage, ReplayFrameMessage, ReplayBackfill } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Slider } from "@/components/ui/slider"
import { Card } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { GOOD, CRITICAL, NEUTRAL } from "@/components/cards/StatCard"
// Reuses the exact profile implementation the Backtest chart uses, so the
// numbers in this table and on that chart come from one algorithm.
import { computeVolumeProfile } from "@/lib/volumeProfile"
import { Loader, LoadingBlock } from "@/components/ui/loader"
import { TickProgress } from "@/components/ui/tick-progress"
import { TimeField } from "@/components/ui/time-field"
import { addMinutesNaive, barCloseLabel, barOpenLabel } from "@/lib/clock"
import { delta as signed, price } from "@/lib/priceFormat"

type Status = "idle" | "loading" | "ready" | "playing" | "paused" | "done"

/** Levels offered. 1 and 2 are what broker platforms default to. */
const ALL_DEV_LEVELS = [0.5, 1, 1.5, 2, 2.5, 3] as const

/**
 * Session windows worth having to hand, in ET.
 *
 * Globex first: it is the one that matches a broker platform's DAY VWAP for
 * futures, and it is the one nobody types from memory.
 */
const SESSION_PRESETS = [
  {
    label: "Globex 6:00 PM – 5:00 PM",
    from: "18:00", to: "17:00",
    why: "The futures session, 18:00–17:00 ET (17:00–16:00 CT). This is what a broker platform's DAY VWAP anchors to, so use it when comparing VWAP or bands against one.",
  },
  {
    label: "RTH 9:30 AM – 4:00 PM",
    from: "09:30", to: "16:00",
    why: "Regular cash hours, 09:30–16:00 ET. VWAP starts at the cash open and ignores overnight flow.",
  },
] as const

/** Display clocks. The data itself is always Eastern; these only relabel it. */
const TZ_CHOICES = [
  { short: "ET", label: "Eastern (data)", offset: 0 },
  { short: "CT", label: "Central", offset: -60 },
  { short: "MT", label: "Mountain", offset: -120 },
  { short: "PT", label: "Pacific", offset: -180 },
] as const

const ALL_TIMEFRAMES = [
  "1m", "5m", "10m", "15m", "20m", "25m", "30m", "35m", "40m", "45m", "1h",
] as const
const TF_MINUTES: Record<string, number> = {
  "1m": 1, "5m": 5, "10m": 10, "15m": 15, "20m": 20, "25m": 25,
  "30m": 30, "35m": 35, "40m": 40, "45m": 45, "1h": 60,
}

/** Can `tf` be resampled out of a frame held at `source`?
 *
 *  Only whole multiples. Not just "coarser": 25m out of a 15m frame is coarser
 *  and still wrong, because each 25m bin would swallow one or two whole 15m
 *  bars and so span 15 or 30 minutes of market time instead of 25. */
function isBuildableFrom(tf: string, source: string): boolean {
  if (!source) return true
  return TF_MINUTES[tf] % TF_MINUTES[source] === 0
}

/** Everything one pane accumulates. Each timeframe runs its own strategy and
 *  broker server-side, so none of this can be shared between panes. */
interface PaneState {
  bars: ReplayBar[]
  completedTrades: ReplayTrade[]
  openTrade: ReplayTrade | null
  equityPoints: { t: string; equity: number }[]
  position: number
  portfolioValue: number
  lastSignal: ReplaySignal | null
  barsProcessed: number
  totalBars: number
  /** As shipped: 2-sigma bands. Re-scaled at render time by the dev settings. */
  vwap: number | null
  vwapUpper: number | null
  vwapLower: number | null
}

function emptyPane(initialCapital: number): PaneState {
  return {
    bars: [], completedTrades: [], openTrade: null, equityPoints: [],
    position: 0, portfolioValue: initialCapital, lastSignal: null,
    barsProcessed: 0, totalBars: 0,
    vwap: null, vwapUpper: null, vwapLower: null,
  }
}

/** Build a pane from backfilled history, as if it had streamed all along.
 *
 *  Only `bars` has to be replayed. Every scalar comes off the single frame the
 *  server sends, because a frame carries position, portfolio value and the
 *  whole completed-trade list cumulatively -- which is also why applyFrame()
 *  below *replaces* completedTrades rather than appending to it. */
function seedPane(bf: ReplayBackfill, capital: number): PaneState {
  const s = bf.state
  return {
    bars: bf.bars,
    completedTrades: s?.completed_trades ?? [],
    openTrade: s?.open_trade ?? null,
    equityPoints: s?.equity_point ? [s.equity_point] : [],
    position: s?.position ?? 0,
    portfolioValue: s?.portfolio_value ?? capital,
    lastSignal: s?.signal ?? null,
    barsProcessed: s?.bars_processed ?? 0,
    totalBars: s?.total_bars ?? bf.bars_closed,
    vwap: s?.vwap ?? null,
    vwapUpper: s?.vwap_upper ?? null,
    vwapLower: s?.vwap_lower ?? null,
  }
}

function applyFrame(pane: PaneState, msg: ReplayFrameMessage): PaneState {
  return {
    bars: [...pane.bars, msg.bar],
    completedTrades: msg.completed_trades,
    openTrade: msg.open_trade,
    position: msg.position,
    portfolioValue: msg.portfolio_value,
    lastSignal: msg.signal ?? pane.lastSignal,
    barsProcessed: msg.bars_processed,
    totalBars: msg.total_bars,
    equityPoints: msg.equity_point ? [...pane.equityPoints, msg.equity_point] : pane.equityPoints,
    vwap: msg.vwap,
    vwapUpper: msg.vwap_upper,
    vwapLower: msg.vwap_lower,
  }
}

/** One emitted bar, from any timeframe, for the consolidated tape.
 *
 *  Fields are limited to what the backend already sends per frame (see
 *  ReplayFrameMessage): OHLCV, the strategy signal, position and portfolio
 *  value. There is deliberately no RSI/indicator column -- the replay frame
 *  does not carry indicator series, and inventing one here would mean either
 *  recomputing it in the browser off partial data or changing the backend,
 *  which this change explicitly leaves alone. */
interface TapeRow {
  seq: number
  tf: string
  t: string
  o: number; h: number; l: number; c: number; v: number | null
  position: number
  signalType: string | null
  signalReason: string | null
  pnl: number
  vwap: number | null
  /** Sigma at this bar, recovered from the frame's 2-sigma payload. Storing
   *  sigma rather than the bands themselves is what lets the deviation setting
   *  re-scale historical rows live, exactly as it does for Live state. */
  sigma: number | null
  /** How many bars this pane had processed at this row, so the volume profile
   *  as of THIS bar can be derived rather than showing the latest one. */
  barIndex: number
  /** True for a row spliced in when its timeframe was added mid-session. Those
   *  bars were replayed before the pane existed on this client, so there is no
   *  per-bar position, P&L or signal for them -- only price and indicators. */
  backfilled?: boolean
}

/**
 * How much history the tape KEEPS. This is a memory guard, not a display limit.
 *
 * It used to be 400, which was also what got rendered -- and that made reaching
 * an earlier bar a matter of pausing playback on exactly the right tick, which
 * is not something a person can do at 0.1s per tick. An overnight multi-day
 * session is several thousand bars per pane, so 400 discarded almost all of it.
 *
 * Rows are now kept in full and only a WINDOW of them is rendered (see
 * TAPE_WINDOW), so raising this costs memory rather than frame time: ~20k rows
 * of a dozen small fields is a few MB, while rendering 20k rows x 16 columns
 * would not survive a single tick.
 */
const TAPE_LIMIT = 20000

/** Rows rendered at once. The tape scrolls within this and pages beyond it. */
const TAPE_WINDOW = 150

function defaultDateRange() {
  const today = new Date()
  const end = new Date(today)
  end.setDate(end.getDate() - 1)
  const start = new Date(end)
  start.setDate(start.getDate() - 4)
  return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) }
}

const SPEED_OPTIONS = [
  { label: "0.05s", value: 0.05 }, { label: "0.1s", value: 0.1 }, { label: "0.2s", value: 0.2 },
  { label: "0.5s", value: 0.5 }, { label: "1s", value: 1.0 },
]

function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-[#0e1424] border border-white/6 rounded-lg px-3 py-2">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="text-lg font-bold" style={{ color: color ?? NEUTRAL }}>{value}</div>
    </div>
  )
}

export function ReplayPage() {
  const { data: strategies } = useQuery({ queryKey: ["strategies"], queryFn: api.strategies })
  const { data: dataSources } = useQuery({ queryKey: ["data-sources"], queryFn: api.dataSources })

  const dr = defaultDateRange()
  const [symbol, setSymbol] = useState("ES")
  const [dataSource, setDataSource] = useState("synthetic")
  const [timeframes, setTimeframes] = useState<string[]>(["5m"])
  const [strategyId, setStrategyId] = useState("rsi_divergence")
  const [params, setParams] = useState<Record<string, number>>({ rsi_overbought: 94, rsi_oversold: 2, swing_lookback: 5 })
  const [initialCapital, setInitialCapital] = useState(100_000)
  const [contractsPerTrade, setContractsPerTrade] = useState(1)
  const [commission, setCommission] = useState(2.5)
  // Session window, same as the Backtest form. session_start also anchors each
  // pane's VWAP daily reset, so an overnight window must not reset at midnight.
  const [session24h, setSession24h] = useState(false)
  const [sessionStart, setSessionStart] = useState("09:30")
  const [sessionEnd, setSessionEnd] = useState("16:00")
  const [startDate, setStartDate] = useState(dr.start)
  const [endDate, setEndDate] = useState(dr.end)
  const [speed, setSpeed] = useState(0.1)

  // The universe the backend can actually serve for THIS source, rather than a
  // hardcoded four. /api/symbols already answers this per source -- 12 symbols
  // for external_csv (whatever is in data/sample), 16 for Schwab, 5 for
  // synthetic (the generator only models a starting price for those) -- and the
  // Backtest form has been using it all along. Live Replay was the page that
  // never got wired up, so gold, bitcoin and nine equities were unreachable
  // here while working fine one tab over.
  const { data: symbols } = useQuery({
    queryKey: ["symbols", dataSource],
    queryFn: () => api.symbols(dataSource),
  })

  const [status, setStatus] = useState<Status>("idle")
  const [error, setError] = useState<string | null>(null)
  const [strategyName, setStrategyName] = useState("")
  const [ticksProcessed, setTicksProcessed] = useState(0)
  const [totalTicks, setTotalTicks] = useState(0)
  // One accumulator per timeframe, keyed by label. Replaces the old flat
  // single-pane state; a one-timeframe session simply has one key.
  const [panes, setPanes] = useState<Record<string, PaneState>>({})
  const [activeTimeframes, setActiveTimeframes] = useState<string[]>([])
  const [baseTimeframe, setBaseTimeframe] = useState("")
  /** Resolution the session's bars were fetched at. Timeframes finer than this
   *  cannot be added to the running session -- resampling down would invent
   *  bars -- so selecting one has to refetch. */
  const [dataTimeframe, setDataTimeframe] = useState("")
  /** Set when an overnight session pulled the previous day in. */
  const [fetchedFrom, setFetchedFrom] = useState<string | null>(null)
  /** Transient note explaining why a toggle did something non-obvious. */
  const [tfNotice, setTfNotice] = useState<string | null>(null)
  /** Raised when the user clicks a field that is locked for this session. */
  const [lockPrompt, setLockPrompt] = useState(false)
  /**
   * Index of the row shown at the top of the tape, or null to follow the newest.
   * Following is the default so the tape behaves as a live feed until the user
   * deliberately goes looking for a moment in the past.
   */
  /**
   * The single row a jump landed on, or null for the normal live tape.
   *
   * The ROW is held rather than its index: the tape is newest-first, so every
   * arriving bar shifts every index down by one and a stored index would drift
   * onto a different bar while playback continues.
   */
  /**
   * The rows a jump landed on -- one per selected timeframe -- or null for the
   * normal live tape.
   *
   * A moment in time falls inside a different bar on every timeframe, so one
   * jump has to resolve against each timeframe's own boundaries: 09:47 sits in
   * a 5m bar closing 09:50 and a 1h bar closing 10:00. Returning a row each
   * gives a synchronised snapshot of that moment without deselecting down to
   * one timeframe and jumping repeatedly.
   *
   * The ROWS are held rather than their indices: the tape is newest-first, so
   * every arriving bar shifts each index and a stored index would drift onto a
   * different bar while playback continues.
   */
  const [jumpedRows, setJumpedRows] = useState<TapeRow[] | null>(null)
  /**
   * Which clock the time columns are shown in.
   *
   * The data is Eastern. A reference platform set to Central labels the same
   * bar an hour earlier, so matching a label like "12:45" across the two
   * screens compares bars sixty minutes apart -- which reads as an OHLC bug
   * because the numbers genuinely differ. Offsets are minutes to ADD to the
   * Eastern timestamp for display.
   */
  const [tzOffset, setTzOffset] = useState(0)

  const [jumpDate, setJumpDate] = useState("")
  const [jumpTime, setJumpTime] = useState("12:20")
  const [jumpNote, setJumpNote] = useState<string | null>(null)
  const [focus, setFocus] = useState("")        // which pane the stats panel follows
  const [marketTime, setMarketTime] = useState<string | null>(null)
  // Consolidated, newest-first log of every bar every pane has emitted.
  const [tape, setTape] = useState<TapeRow[]>([])

  // ---- indicator settings (mirror the Backtest page's gear panels) --------
  // VWAP bands arrive at 2 sigma; sigma is recovered as (upper - vwap) / 2 and
  // re-scaled here, so these two react instantly with no refetch.
  const [showVwap, setShowVwap] = useState(true)
  /**
   * Deviation levels to show bands for, as positive multiples of sigma.
   *
   * Replaces the single num-dev-up / num-dev-dn pair. Comparing this app's +/-2
   * bands against a platform showing +/-1 is what made a band look like a
   * mismatch, so several levels can now be on at once and read side by side.
   * Each level N renders an "Upper +Ns" and a "Lower -Ns" column: sigma is a
   * distance and the bands are symmetric about the VWAP, so a separate up and
   * down multiplier only ever described the same distance twice.
   */
  const [devLevels, setDevLevels] = useState<number[]>([2])
  // Volume Profile is computed in the browser from each pane's accumulated
  // bars, exactly as the Backtest chart does, so bins / value-area also apply
  // instantly.
  const [showVp, setShowVp] = useState(true)

  /**
   * Highlight band values that several timeframes agree on, to the whole
   * number. Comparing columns by eye across three timeframes is exactly the
   * kind of thing a screen should do for you, and the whole number is the
   * unit that matters when checking against the reference platform.
   */
  const [markAgreement, setMarkAgreement] = useState(true)
  const [vpBins, setVpBins] = useState(48)
  const [vpValueArea, setVpValueArea] = useState(70)
  const [settingsOpen, setSettingsOpen] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => () => wsRef.current?.close(), [])

  const currentStrategy = strategies?.find((s) => s.id === strategyId)

  function resetAccumulators(tfs: string[] = activeTimeframes) {
    setPanes(Object.fromEntries(tfs.map((tf) => [tf, emptyPane(initialCapital)])))
    setTicksProcessed(0)
    setMarketTime(null)
    setTape([])
  }

  async function handleLoad(override?: string[]) {
    // `override` exists because a timeframe toggle may have to reload with a
    // selection React has not committed to state yet.
    const wanted = override ?? timeframes
    setStatus("loading"); setError(null)
    wsRef.current?.close()
    try {
      const resp = await api.createReplay({
        symbol,
        timeframe: wanted[0],               // legacy field, kept in step with the list
        timeframes: wanted,
        data_source: dataSource,
        strategy_id: strategyId, params,
        initial_capital: initialCapital, contracts_per_trade: contractsPerTrade,
        commission_per_contract: commission,
        start_date: startDate, end_date: endDate,
        session_start: session24h ? null : sessionStart,
        session_end: session24h ? null : sessionEnd,
      })
      setStrategyName(resp.strategy_name)
      setTotalTicks(resp.total_bars)
      // The server orders panes fine -> coarse and names the clock's base.
      setActiveTimeframes(resp.timeframes)
      setBaseTimeframe(resp.base_timeframe)
      setDataTimeframe(resp.data_timeframe ?? resp.base_timeframe)
      setFetchedFrom(resp.fetch_start_date ?? null)
      setFocus(resp.base_timeframe)
      resetAccumulators(resp.timeframes)

      const ws = new WebSocket(api.replayWsUrl(resp.replay_id))
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data) as ReplayWsMessage
        if (msg.type === "frames") {
          // Apply every pane from this tick in ONE state update, so the grid
          // never renders with some panes advanced and others not.
          setPanes((prev) => {
            const next = { ...prev }
            for (const [tf, frame] of Object.entries(msg.frames)) {
              next[tf] = applyFrame(next[tf] ?? emptyPane(initialCapital), frame)
            }
            return next
          })
          // Same tick, same state update: every bar from this tick enters the
          // tape together, so the table can never show one pane ahead of
          // another any more than the chart grid could.
          setTape((prev) => {
            const rows: TapeRow[] = Object.entries(msg.frames).map(([tf, f], i) => ({
              seq: msg.ticks_processed * 10 + i,
              tf,
              t: f.bar.t,
              o: f.bar.o, h: f.bar.h, l: f.bar.l, c: f.bar.c, v: f.bar.v,
              position: f.position,
              signalType: f.signal?.type ?? null,
              signalReason: f.signal?.reason ?? null,
              pnl: f.portfolio_value - initialCapital,
              vwap: f.vwap,
              // The frame ships bands at 2 sigma, so this recovers sigma itself.
              sigma: (f.vwap != null && f.vwap_upper != null)
                ? (f.vwap_upper - f.vwap) / 2
                : null,
              barIndex: f.bars_processed,
            }))
            // The backend iterates panes fine -> coarse, so `rows` is already
            // [1m, 5m, 15m]. Prepending it unreversed puts the finest pane on
            // top, which is the row carrying the newest timestamp -- reversing
            // here put a 20:15 5m bar above a 20:19 1m bar and made a
            // newest-first tape read as though time ran backwards.
            return [...rows, ...prev].slice(0, TAPE_LIMIT)
          })
          setTicksProcessed(msg.ticks_processed)
          setTotalTicks(msg.total_ticks)
          setMarketTime(msg.market_time)
        } else if (msg.type === "timeframes") {
          setActiveTimeframes(msg.timeframes)
          setBaseTimeframe(msg.base_timeframe)
          setDataTimeframe(msg.data_timeframe)
          // Seed each new pane with the history the server replayed for it, so
          // it arrives showing the same moment as every other pane instead of
          // an empty row that fills in over the following minutes.
          setPanes((prev) => {
            const next = { ...prev }
            for (const [tf, bf] of Object.entries(msg.backfill)) {
              next[tf] = seedPane(bf, initialCapital)
            }
            return next
          })
          // ...and into the TAPE, so the new timeframe can be jumped to at once.
          // Without this a timeframe added part-way through only appeared in the
          // tape from its next live bar, so asking for it at an earlier moment
          // answered "no bar yet" -- which is exactly what someone adding it in
          // order to look at an earlier moment is trying to do.
          setTape((prev) => {
            const extra: TapeRow[] = []
            for (const [tf, bf] of Object.entries(msg.backfill)) {
              bf.bars.forEach((b, i) => {
                const vwap = b.vwap ?? null
                extra.push({
                  seq: 0, tf, t: b.t,
                  o: b.o, h: b.h, l: b.l, c: b.c, v: b.v,
                  position: 0, signalType: null, signalReason: null, pnl: 0,
                  vwap,
                  sigma: (vwap != null && b.vwap_upper != null)
                    ? (b.vwap_upper - vwap) / 2 : null,
                  barIndex: i + 1,
                  backfilled: true,
                })
              })
            }
            if (extra.length === 0) return prev
            // Newest-first by the bar's CLOSE, which is the column the table
            // shows and the order the live tape is already in.
            const closeOf = (r: TapeRow) => barCloseLabel(r.t, TF_MINUTES[r.tf])
            return [...extra, ...prev]
              .sort((a, b) => (closeOf(a) < closeOf(b) ? 1 : closeOf(a) > closeOf(b) ? -1 : 0))
              .slice(0, TAPE_LIMIT)
          })
          if (msg.rejected.length > 0) {
            // Belt and braces: the button already reloads for finer timeframes,
            // so reaching here means the client's view of the data resolution
            // was stale. Say so rather than silently dropping the request.
            setTfNotice(
              `${msg.rejected.join(", ")} is finer than the loaded ${msg.data_timeframe} data — ` +
              "click it again to refetch at that resolution.",
            )
          } else if (msg.added.length > 0) {
            const bars = msg.added.map((tf) => msg.backfill[tf]?.bars_closed ?? 0)
            setTfNotice(
              `Added ${msg.added.join(", ")} — caught up to the current bar ` +
              `(${bars.join(", ")} bars of history).`,
            )
          }
        } else if (msg.type === "reset") {
          resetAccumulators(); setStatus("ready")
        } else if (msg.type === "done") {
          setStatus("done")
        } else if (msg.type === "error") {
          setError(msg.message); setStatus("idle")
        }
      }
      ws.onerror = () => setError("WebSocket connection failed.")
      wsRef.current = ws
      setStatus("ready")
    } catch (e) {
      setError((e as Error).message)
      setStatus("idle")
    }
  }

  function send(action: string, extra?: Record<string, unknown>) {
    wsRef.current?.send(JSON.stringify({ action, ...extra }))
  }

  const play = () => { send("play"); setStatus("playing") }
  const pause = () => { send("pause"); setStatus("paused") }
  const reset = () => { send("reset") }

  /**
   * Release the session and hand the form back.
   *
   * Reset REWINDS -- it replays the same session from tick 0, and the server
   * keeps its panes, so status stays "ready" and every setup field stays
   * locked. That left no way at all to change symbol, strategy or dates after
   * the first Load Data: the fields were disabled, and the only control that
   * looked like it should free them did not. Short of reloading the browser the
   * form was a dead end. This is the missing door out.
   */
  function changeSetup() {
    wsRef.current?.close()
    wsRef.current = null
    setStatus("idle")
    setActiveTimeframes([])
    setBaseTimeframe("")
    setDataTimeframe("")
    setFocus("")
    setPanes({})
    setTape([])
    setTicksProcessed(0)
    setTotalTicks(0)
    setMarketTime(null)
    setTfNotice(null)
    setError(null)
    setLockPrompt(false)
  }
  const changeSpeed = (v: number) => { setSpeed(v); send("set_speed", { speed: v }) }

  /** Re-scale a shipped 2-sigma band to the user's deviation setting.
   *  sigma = (upper - vwap) / 2, so value = vwap + mult * sigma. A negative mult
   *  negative, matching the reference dialog's "num dev dn = -2.0". */
  /** One tape row's band at `mult` sigma -- the row-level twin of atDev. */
  const rowBand = (row: TapeRow, mult: number): number | null =>
    (row.vwap == null || row.sigma == null) ? null : row.vwap + mult * row.sigma

  /** Shared formatter for the tape's numeric cells. */
  const tapeNum = price


  const atDev = (pane: PaneState, mult: number): number | null => {
    if (pane.vwap == null || pane.vwapUpper == null) return null
    return pane.vwap + mult * ((pane.vwapUpper - pane.vwap) / 2)
  }

  /**
   * Volume profile for a tape row: the profile as it stood at THAT bar, not the
   * latest one.
   *
   * Memoised because it is genuinely expensive -- a profile is a pass over every
   * bar up to that point, and the tape holds up to 400 rows. Keyed on the
   * settings as well as the row, so changing bins or the value-area percentage
   * invalidates every entry and the column re-derives live; steady-state
   * playback only ever computes the one new row per tick.
   */
  const profileCache = useRef(new Map<string, ReturnType<typeof computeVolumeProfile> | null>())

  const profileAtRow = (row: TapeRow) => {
    if (!showVp) return null
    const pane = panes[row.tf]
    if (!pane || pane.bars.length < 2) return null
    const key = `${row.tf}|${row.barIndex}|${vpBins}|${vpValueArea}`
    const hit = profileCache.current.get(key)
    if (hit !== undefined) return hit

    // The row's own history. pane.bars starts at the session's first bar except
    // when a mid-session addition truncated its backfill, so clamp rather than
    // slicing past the end.
    const upto = Math.min(row.barIndex, pane.bars.length)
    const slice = pane.bars.slice(0, upto)
    const out = slice.length < 2
      ? null
      : computeVolumeProfile(
          slice.map((b) => ({ h: b.h, l: b.l, v: b.v })),
          vpBins, vpValueArea / 100,
        )
    // Bounded: 400 rows x a few settings changes, not a leak.
    if (profileCache.current.size > 4000) profileCache.current.clear()
    profileCache.current.set(key, out)
    return out
  }

  /** POC / value-area for one pane, from the bars it has received so far. */
  const profileFor = (pane: PaneState) => {
    if (!showVp || pane.bars.length < 2) return null
    return computeVolumeProfile(
      pane.bars.map((b) => ({ h: b.h, l: b.l, v: b.v })),
      vpBins, vpValueArea / 100,
    )
  }

  const ready = status !== "idle" && status !== "loading"

  /** A raw Eastern timestamp, rendered in the chosen clock. */
  const inTz = (iso: string) => addMinutesNaive(iso, tzOffset)
  /** A bar's CLOSE label, in the chosen clock. */
  const closeInTz = (iso: string, tfMinutes: number) =>
    addMinutesNaive(iso, tfMinutes + tzOffset)
  /** A time the user typed in the chosen clock, back to Eastern for matching. */
  const fromTz = (iso: string) => addMinutesNaive(iso, -tzOffset)
  const TZ_LABEL = TZ_CHOICES.find((z) => z.offset === tzOffset)?.short ?? "ET"

  // Switching source changes the universe, so a symbol that was valid before
  // may not exist now (NQ has no CSV). Fall back to the first one the source
  // does serve instead of leaving a selection that cannot load. Never while a
  // session is live -- the symbol is locked then, and silently changing it
  // under a running replay would be worse than leaving it stale.
  useEffect(() => {
    if (ready || !symbols || symbols.length === 0) return
    if (!symbols.some((s) => s.symbol === symbol)) setSymbol(symbols[0].symbol)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbols, symbol, ready])

  /** Windows this symbol actually has data for. Empty = any date is fine. */
  const coverage = symbols?.find((s) => s.symbol === symbol)?.coverage ?? []
  const inCoverage = (from: string, to: string) =>
    coverage.length === 0 || coverage.some((w) => from <= w.end && to >= w.start)

  // Nudge the dates into a window that exists, but ONLY when the current range
  // misses entirely -- a range the user picked that does hold data is never
  // overwritten. Without this, selecting NVDA (data: 2025-01-02..2025-01-10)
  // with the default "last five days" produced an empty load and a message
  // about no bars, for a symbol that has plenty.
  useEffect(() => {
    if (ready || coverage.length === 0) return
    if (inCoverage(startDate, endDate)) return
    const latest = coverage[coverage.length - 1]
    setStartDate(latest.start)
    setEndDate(latest.end)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, dataSource, symbols, ready])

  /**
   * Why a field is fixed once a session is loaded.
   *
   * Timeframes were unlocked because a pane can be rebuilt from the frame
   * already in memory and caught up to the clock exactly (see
   * handleTimeframeToggle). Nothing else on this form has that property, so the
   * rest stay locked -- but they used to be locked SILENTLY: a greyed-out
   * control with no reason given, which is indistinguishable from a bug. Each
   * one now states what it would invalidate and how to change it.
   */
  const LOCK_REASON = {
    data:
      "it decides which bars the session is built from, and those are fetched once, at Load Data",
    symbol:
      "it changes both the bars and the contract spec (tick size and value) that every fill already booked was priced with",
    strategy:
      "each timeframe runs its own stateful strategy instance, so swapping it live would leave the new one with no history while positions opened by the old one are still on the book",
    money:
      "it feeds every fill already booked, so changing it mid-session would leave the portfolio value inconsistent with the trades that produced it",
  } as const

  const lockTitle = (kind: keyof typeof LOCK_REASON) =>
    ready
      ? `Fixed while a session is loaded — ${LOCK_REASON[kind]}. Press ✎ Change Setup to edit it.`
      : undefined

  /** Timeframes actually rendered: the user's selection, intersected with the
   *  panes the session has, ordered fine -> coarse.
   *
   *  Unticking a timeframe drops it from here and nothing else -- its pane goes
   *  on being stepped and streamed server-side. That is what makes re-ticking
   *  it instant and exactly in sync, and it means a UI toggle can never create
   *  or destroy backend state mid-tick. */
  const shownTimeframes = activeTimeframes
    .filter((tf) => timeframes.includes(tf))
    .sort((a, b) => TF_MINUTES[a] - TF_MINUTES[b])

  // Band values per shown timeframe, in the same column order the tape
  // renders them: [+d0, -d0, +d1, -d1, ...]. Computed once for the whole
  // table because agreement is a property of a COLUMN, which no single row
  // can see on its own.
  const tapeBandRows = shownTimeframes.map((tf) => {
    const pane = panes[tf] ?? emptyPane(initialCapital)
    return devLevels.flatMap((d) => [atDev(pane, d), atDev(pane, -d)])
  })
  const tapeAgreement = bandAgreement(tapeBandRows, shownTimeframes)

  // The summary has to follow a pane that is actually on screen. Derived rather
  // than synced through an effect: hiding the focused timeframe would otherwise
  // paint one frame of a pane that is no longer in the table before the effect
  // corrected it. Falls back to the clock base, else the finest row still shown.
  const focusedTimeframe =
    shownTimeframes.includes(focus) ? focus
      : shownTimeframes.includes(baseTimeframe) ? baseTimeframe
        : shownTimeframes[0] ?? ""

  /** A timeframe was clicked. Allowed at any moment -- before Load, mid-
   *  playback, or paused -- and what it costs depends entirely on direction:
   *
   *    off      -> hide the row. No backend call, nothing lost.
   *    on again -> unhide. No backend call; the pane never stopped updating.
   *    new, >= data resolution -> ask the server for a pane and backfill it.
   *    new, <  data resolution -> the bars do not exist at that resolution, so
   *                               this refetches. The only case that restarts. */
  function handleTimeframeToggle(tf: string) {
    const on = timeframes.includes(tf)
    if (on && timeframes.length === 1) return       // never leave zero rows

    const next = on
      ? timeframes.filter((x) => x !== tf)
      : [...timeframes, tf].sort((a, b) => TF_MINUTES[a] - TF_MINUTES[b])
    setTimeframes(next)
    setTfNotice(null)

    if (!ready) return                              // no session yet: just a form
    if (on) {
      setTfNotice(`${tf} hidden. Its pane keeps running, so re-adding it is instant.`)
    } else if (activeTimeframes.includes(tf)) {
      setTfNotice(`${tf} shown again — it never stopped updating, so it is already current.`)
    } else if (dataTimeframe && !isBuildableFrom(tf, dataTimeframe)) {
      // Either finer than the source, or coarser but not a whole multiple of
      // it -- both would need bars the loaded frame cannot produce honestly.
      setTfNotice(`${tf} cannot be built from the loaded ${dataTimeframe} bars — refetching from the start.`)
      void handleLoad(next)
    } else {
      send("add_timeframes", { timeframes: [tf] })
    }
  }
  const done = status === "done"
  //: Only a live date can go stale -- a historical day is complete the moment
  //  it is fetched, so warning about it would be noise.
  const isToday = endDate === new Date().toISOString().slice(0, 10)

  // The stats panel, equity chart and trade table follow ONE pane at a time --
  // each timeframe has its own broker and equity curve, so summing them would
  // be meaningless. Defaults to the clock's base; click a pane header to switch.
  const shown: PaneState = panes[focusedTimeframe] ?? emptyPane(initialCapital)

  /**
   * Jump the tape to the first row at or before a wall-clock moment.
   *
   * The tape is newest-first, so "at or before" means the first row scanning
   * downward whose bar close is <= the target -- that is the bar that was
   * current at that moment. Only bars that have actually been replayed exist,
   * so asking for a time playback has not reached yet says so rather than
   * silently landing somewhere near it.
   */
  function jumpToTime() {
    setJumpNote(null)
    const day = jumpDate || (shownTape.length ? shownTape[0].t.slice(0, 10) : "")
    if (!day) { setJumpNote("Nothing loaded yet."); return }
    // Checked before anything else: an impossible day otherwise reaches the
    // comparison and comes back as "playback has not got there yet", which
    // sounds like a data problem rather than a typo in the year.
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) {
      setJumpNote(`"${day}" is not a date. Expected YYYY-MM-DD.`)
      return
    }
    if (shownTape.length) {
      const [first, last] = [shownTape[shownTape.length - 1].t.slice(0, 10),
                             shownTape[0].t.slice(0, 10)]
      if (day < first || day > last) {
        setJumpNote(
          `${day} is outside the loaded data, which runs ${first} to ${last}. ` +
          `Check the year, or reload with a range that covers it.`,
        )
        return
      }
    }
    // The user types in whatever clock the table is showing, so convert back
    // to Eastern before matching against the bars.
    const target = fromTz(`${day} ${jumpTime}`)

    // MATCHED ON THE BAR'S OPEN, not its close.
    //
    // A broker platform's tooltip gives the open -- "8/13/26 1:20 PM" is the bar
    // running 1:20 to 1:40 on 20m. Matching on the close meant reading that
    // tooltip and mentally adding the bar length before typing, a different sum
    // for every timeframe, and getting it wrong lands on the ADJACENT bar, whose
    // OHLC is plausible and completely different. That cost four rounds of "the
    // values do not match" that were not value bugs at all.
    //
    // The Opened column is the one people compare against, so it is the one the
    // Jump field now speaks.
    const label = (r: TapeRow) => barOpenLabel(r.t)

    if (shownTape.length === 0) { setJumpNote("No bars yet — press Play first."); return }

    const newest = label(shownTape[0])
    const oldest = label(shownTape[shownTape.length - 1])
    // Same values in the clock the table is showing, for the messages below.
    // Matching stays in Eastern; only the wording changes.
    const newestShown = inTz(shownTape[0].t)
    const oldestShown = inTz(shownTape[shownTape.length - 1].t)
    const typedShown = `${day} ${jumpTime}`

    // The tape holds only bars that have actually been REPLAYED, which is not the
    // same as the bars the session loaded. Asking for a later time used to land on
    // the newest row and call it "the closest bar", which read as though the data
    // were missing -- the loaded day was complete, playback had simply not reached
    // that point. Distinguish the two cases explicitly.
    if (target > newest) {
      setJumpNote(
        `Playback has only reached ${newestShown} ${TZ_LABEL}. Press ▶ Play to ` +
        `carry the tape forward past ${typedShown}, then jump again.`,
      )
      return
    }
    if (target < oldest) {
      setJumpNote(
        `The tape starts at ${oldestShown} ${TZ_LABEL}, which is later than ${typedShown}.`,
      )
      return
    }

    // One row per selected timeframe. Newest-first, so the first row of a given
    // timeframe at or before the target is the bar that was current on that
    // timeframe at that moment.
    //
    // "Current" means the last bar to have CLOSED by then. A coarse timeframe's
    // bar containing the target may still have been forming -- at 09:47 the
    // hourly bar covering 09:00-10:00 has not closed, so its match is the one
    // closing 09:00. The Opened and Bar close columns show that span, so which
    // bar was matched is visible rather than assumed.
    const hits: TapeRow[] = []
    const missing: string[] = []
    for (const tf of shownTimeframes) {
      const hit = shownTape.find((r) => r.tf === tf && label(r) <= target)
      if (hit) hits.push(hit)
      else missing.push(tf)
    }
    if (hits.length === 0) {
      setJumpNote(
        `No bar at or before ${typedShown} ${TZ_LABEL} on any selected timeframe.`,
      )
      return
    }

    setJumpedRows(hits)

    // MATCHING is done in Eastern, because that is what the bars carry. SAYING
    // must use the clock the table is showing, or the note contradicts the
    // column beside it: with CT selected the Opened column read 05:15 while this
    // sentence said 06:15, which reads as the jump having landed somewhere else.
    const shown = (r: TapeRow) => inTz(r.t)
    const typed = `${day} ${jumpTime}`

    const exact = hits.filter((h) => label(h) === target).length
    const head = hits.length === 1
      ? (exact ? `Showing the bar that opened ${shown(hits[0])} ${TZ_LABEL}.`
               : `Showing the bar that opened ${shown(hits[0])} ${TZ_LABEL} — the last one to open at or before ${typed}.`)
      : `Showing ${hits.length} timeframes, by bar OPEN, at ${typed} ${TZ_LABEL} — ` +
        hits.map((h) => `${h.tf} opened ${shown(h)}`).join(", ") + "."
    setJumpNote(
      missing.length
        ? `${head} No bar yet on ${missing.join(", ")}.`
        : head,
    )
  }

  // Hidden timeframes keep streaming, so their rows keep arriving; filter at
  // render rather than on receipt, so re-showing a timeframe brings its history
  // back instead of leaving a hole for the bars it was hidden for.
  const shownTape = tape.filter((r) => timeframes.includes(r.tf))

  // A jump shows exactly the matched bar; otherwise the newest window of the
  // live tape. Only a window is ever rendered -- 20,000 rows x 16 columns would
  // not survive a single tick.
  //: First and last day present on the tape, for bounding the jump date.
  //  Newest-first, so the last row is the oldest.
  const tapeDayRange: [string, string] | null = shownTape.length
    ? [shownTape[shownTape.length - 1].t.slice(0, 10), shownTape[0].t.slice(0, 10)]
    : null

  const tapeWindow = jumpedRows ?? shownTape.slice(0, TAPE_WINDOW)
  const { completedTrades, position, portfolioValue, lastSignal } = shown

  const pnls = completedTrades.map((t) => t.pnl)
  const wins = pnls.filter((p) => p > 0)
  const losses = pnls.filter((p) => p <= 0)
  const totalPnl = pnls.reduce((a, b) => a + b, 0)
  const winRate = completedTrades.length ? (wins.length / completedTrades.length) * 100 : 0
  const avgWin = wins.length ? wins.reduce((a, b) => a + b, 0) / wins.length : 0
  const avgLoss = losses.length ? losses.reduce((a, b) => a + b, 0) / losses.length : 0

  return (
    <div className="space-y-4 p-4 w-full max-w-none">
      {/* Clicking a locked field used to do NOTHING -- a disabled control
          swallows the click, so the field simply refused to open with no
          feedback at all. That is what "completely locked with no way out"
          actually looked like: the tooltip explaining it needs a deliberate
          hover, which nobody does to a control they think is broken.

          Locked controls now have pointer-events:none (see .setup-locked in
          index.css), so the click lands on their wrapper and reaches this
          handler, which answers the question the click was asking. */}
      <Card
        className={`p-4 border border-white/6 w-full ${ready ? "setup-locked" : ""}`}
        onClickCapture={(e) => {
          if (!ready) return
          const el = e.target as HTMLElement
          if (el.querySelector?.("[disabled], [data-disabled]")) setLockPrompt(true)
        }}
      >
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 items-end">
          <div className="space-y-1" title={lockTitle("symbol")}>
            <Label className="text-xs">Symbol</Label>
            <Select value={symbol} onValueChange={setSymbol} disabled={ready}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                {(symbols ?? [{ symbol: "ES", name: "E-mini S&P 500", has_spec: true }]).map((s) => (
                  <SelectItem key={s.symbol} value={s.symbol}>
                    {s.symbol}
                    {s.name && s.name !== s.symbol && (
                      <span className="text-muted-foreground"> — {s.name}</span>
                    )}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1" title={lockTitle("data")}>
            <Label className="text-xs">Data Source</Label>
            <Select value={dataSource} onValueChange={setDataSource} disabled={ready}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                {(dataSources ?? [{ id: "synthetic", label: "Synthetic Data", available: true }]).map((d) => (
                  <SelectItem key={d.id} value={d.id} disabled={!d.available}>
                    {d.label}{d.available ? "" : " (unavailable)"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {/* Authorising with Schwab used to live only on the Backtest page, so
              selecting Schwab here offered no way to connect -- the option was
              enabled but unusable from replay, which is the page in daily use. */}
          {dataSource === "schwab" && (
            <div className="col-span-2">
              <SchwabAuthWidget />
            </div>
          )}
          <div className="space-y-1 col-span-2" title={lockTitle("strategy")}>
            <Label className="text-xs">Strategy</Label>
            <Select
              value={strategyId} disabled={ready}
              onValueChange={(v) => {
                setStrategyId(v)
                const s = strategies?.find((x) => x.id === v)
                if (s) setParams(Object.fromEntries(s.params.map((p) => [p.name, p.default])))
              }}
            >
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>{(strategies ?? []).map((s) => <SelectItem key={s.id} value={s.id}>{s.label}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Start</Label>
            <Input type="date" value={startDate} title={lockTitle("data")} disabled={ready} onChange={(e) => setStartDate(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">End</Label>
            <Input type="date" value={endDate} title={lockTitle("data")} disabled={ready} onChange={(e) => setEndDate(e.target.value)} />
          </div>
        </div>

        {/* Coverage, stated before Load rather than after a failed one. The
            equity samples run 2025-01-02..2025-01-10 and gold 2025-06-22..26,
            none of which overlap the default "last five days" -- so without
            this the honest answer "that symbol has no data in your range" only
            arrived as an error after clicking. */}
        {ready && fetchedFrom && (
          /* An overnight session begins the previous calendar day, so the fetch
             reaches back one day to make its first session whole. Without this
             note the extra evening of bars at the front of the replay looks
             like the wrong date range was loaded. */
          <p className="text-xs text-muted-foreground mt-2">
            Session starts at <span className="font-mono">{sessionStart}</span>, which is the
            previous evening — loaded from <span className="text-foreground/70">{fetchedFrom}</span> so
            the first session is complete and its VWAP anchors at the session open.
          </p>
        )}

        {!ready && coverage.length > 0 && (
          <p className="text-xs text-muted-foreground mt-2">
            <span className="text-foreground/70">{symbol}</span> data available:{" "}
            {coverage.map((w) => `${w.start} → ${w.end}`).join("  ·  ")}
            {!inCoverage(startDate, endDate) && (
              <span className="text-destructive"> — the selected range has no data</span>
            )}
          </p>
        )}

        <div className="mt-3 space-y-1">
          <Label className="text-xs">
            Timeframes — {timeframes.length} selected
            {timeframes.length > 1 && (
              <span className="text-muted-foreground">
                {" "}· base {[...timeframes].sort((a, b) => TF_MINUTES[a] - TF_MINUTES[b])[0]} drives the shared clock
              </span>
            )}
          </Label>
          <div className="flex flex-wrap gap-2">
            {ALL_TIMEFRAMES.map((tf) => {
              const on = timeframes.includes(tf)
              // Selectable at any point in the session; only the reason differs.
              const live = ready && activeTimeframes.includes(tf)
              const needsRefetch = ready && !!dataTimeframe && !isBuildableFrom(tf, dataTimeframe)
              return (
                <Button
                  key={tf} type="button" size="sm"
                  variant={on ? "default" : "secondary"}
                  aria-pressed={on}
                  title={
                    !ready ? undefined
                      : needsRefetch ? `${tf} cannot be built from the loaded ${dataTimeframe} bars — selecting it refetches from the start`
                      : on ? `Hide ${tf}. Its pane keeps running, so re-adding is instant.`
                      : live ? `Show ${tf} again — already up to date`
                      : `Add ${tf} — backfilled to the current bar`
                  }
                  onClick={() => handleTimeframeToggle(tf)}
                >
                  {on ? "✓ " : ""}{tf}
                  {needsRefetch && <span className="ml-1 opacity-60">↻</span>}
                </Button>
              )
            })}
          </div>
          {ready && (
            <p className="text-xs text-muted-foreground">
              Change these any time — during playback or paused.
              {dataTimeframe && (
                <> Data is loaded at <span className="font-mono">{dataTimeframe}</span>, so any whole
                multiple of it is added instantly and backfilled; anything else (↻) has to refetch.</>
              )}
            </p>
          )}
          {tfNotice && (
            <p className="text-xs text-primary" role="status">{tfNotice}</p>
          )}
        </div>

        <div className="mt-3 space-y-2">
          <Label className="text-xs">
            Session Hours (ET)
            <span className="ml-2 text-muted-foreground">
              · also anchors each pane&apos;s VWAP reset
            </span>
          </Label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={session24h} title={lockTitle("data")} disabled={ready} aria-label="24 hours"
                   onChange={(e) => setSession24h(e.target.checked)} />
            <span>24 hours <span className="text-muted-foreground">(keep every bar)</span></span>
          </label>

          {/* PRESETS.
              These two fields decide where VWAP starts accumulating, so an
              arbitrary value here puts every VWAP and band off against any other
              platform -- and it reads as a calculation bug, because the numbers
              really are different. A 04:00 start cost a week of hunting: it was
              reproducing 7812.33 exactly and correctly for the session it had
              been given, while the reference platform anchored at the Globex
              open and showed 7809.89.

              Typing the right pair from memory is the step that failed, so the
              two that matter are one click, and the one that matches a broker
              platform's DAY says so. */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-muted-foreground mr-1">presets</span>
            {SESSION_PRESETS.map((p) => {
              const on = !session24h && sessionStart === p.from && sessionEnd === p.to
              return (
                <Button
                  key={p.label} type="button" size="sm"
                  variant={on ? "default" : "secondary"}
                  aria-pressed={on}
                  aria-label={`session preset ${p.label}`}
                  title={p.why}
                  disabled={ready}
                  onClick={() => { setSession24h(false); setSessionStart(p.from); setSessionEnd(p.to) }}
                >
                  {on ? "✓ " : ""}{p.label}
                </Button>
              )
            })}
          </div>
          {!session24h && (() => {
            const hit = SESSION_PRESETS.find((p) => sessionStart === p.from && sessionEnd === p.to)
            return (
              <p className="text-xs text-muted-foreground">
                {hit
                  ? hit.why
                  : <>A custom window. VWAP will accumulate from{" "}
                      <span className="font-mono text-foreground/70">{sessionStart}</span> ET, so it
                      will not agree with a platform anchored anywhere else — pick
                      <span className="text-foreground/70"> Globex</span> to match a broker&apos;s DAY VWAP.</>}
              </p>
            )
          })()}
          <div className={`grid grid-cols-2 gap-3 max-w-md ${session24h ? "opacity-40" : ""}`}>
            <div className="space-y-1">
              <Label className="text-xs">From</Label>
              <TimeField value={sessionStart} onChange={setSessionStart}
                         label="Session start"
                         title={lockTitle("data") ?? (session24h ? "Not used while 24 hours is selected — every bar is kept." : undefined)}
                         disabled={ready || session24h} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">To</Label>
              <TimeField value={sessionEnd} onChange={setSessionEnd}
                         label="Session end"
                         title={lockTitle("data") ?? (session24h ? "Not used while 24 hours is selected — every bar is kept." : undefined)}
                         disabled={ready || session24h} />
            </div>
          </div>
        </div>

        {currentStrategy && currentStrategy.params.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-3">
            {currentStrategy.params.map((p) => (
              <div key={p.name} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span>{p.label}</span>
                  <span className="font-mono text-muted-foreground">{params[p.name] ?? p.default}</span>
                </div>
                <Slider min={p.min} max={p.max} step={p.step} title={lockTitle("strategy")} disabled={ready}
                        value={[params[p.name] ?? p.default]}
                        onValueChange={([v]) => setParams((prev) => ({ ...prev, [p.name]: v }))} />
              </div>
            ))}
          </div>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
          <div className="space-y-1">
            <Label className="text-xs">Initial Capital ($)</Label>
            <Input type="number" step={10000} value={initialCapital} title={lockTitle("money")} disabled={ready}
                   onChange={(e) => setInitialCapital(Number(e.target.value))} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Contracts / Trade</Label>
            <Input type="number" min={1} max={10} value={contractsPerTrade} title={lockTitle("money")} disabled={ready}
                   onChange={(e) => setContractsPerTrade(Number(e.target.value))} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Commission / Contract ($)</Label>
            <Input type="number" step={0.5} value={commission} title={lockTitle("money")} disabled={ready}
                   onChange={(e) => setCommission(Number(e.target.value))} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Speed</Label>
            <Select value={String(speed)} onValueChange={(v) => changeSpeed(Number(v))}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>{SPEED_OPTIONS.map((o) => <SelectItem key={o.value} value={String(o.value)}>{o.label}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        </div>

        <Separator className="my-3" />
        <div className="flex flex-wrap gap-2 items-center">
          <Button onClick={() => handleLoad()} disabled={status === "loading"} variant={ready ? "secondary" : "default"}>
            {status === "loading"
              ? <span className="flex items-center gap-2"><Loader size={16} tone="current" label="Loading data" />Loading…</span>
              : "⬇ Load Data"}
          </Button>
          <Button onClick={play} disabled={!ready || status === "playing" || done}>▶ Play</Button>
          <Button onClick={pause} disabled={!ready || status !== "playing"} variant="secondary">⏸ Pause</Button>
          <Button onClick={reset} disabled={!ready} variant="secondary"
                  title="Replay this same session from the first tick. Setup stays as loaded.">
            ↺ Reset
          </Button>
          {ready && (
            /* Styled apart from Pause/Reset on purpose. It sat fifth in this row
               with the identical secondary background, so it read as one more
               transport control rather than the way out of a locked form. */
            <Button
              onClick={changeSetup}
              variant="secondary"
              className={`border border-primary/50 text-primary hover:bg-primary/10 ${lockPrompt ? "ring-2 ring-primary animate-pulse" : ""}`}
              title="Release the session and unlock the setup fields so symbol, strategy, dates and capital can be changed."
            >
              ✎ Change Setup
            </Button>
          )}
          {ready && (
            /* The tick count and the timestamp moved into TickProgress below;
               they were being stated twice, once here and once by the bar. What
               is left is what the bar cannot say: which strategy is running,
               and its transport state. */
            <span className="text-sm text-muted-foreground ml-2 flex items-center gap-2">
              <span className="text-foreground/80">{strategyName}</span>
              <span className="text-xs px-2 py-0.5 rounded-full border border-white/10 bg-white/[0.03]">
                {done ? "✓ Complete"
                  : status === "playing" ? "▶ Playing"
                    : status === "paused" ? "⏸ Paused" : "Ready"}
              </span>
            </span>
          )}
        </div>
        {ready && totalTicks > 0 && (
          <div className="mt-3">
            <TickProgress
              processed={ticksProcessed}
              total={totalTicks}
              playing={status === "playing"}
              detail={marketTime ? barCloseLabel(marketTime, TF_MINUTES[baseTimeframe] ?? 1) : undefined}
            />
          </div>
        )}
        {ready && (
          /* Stated once, in the open. The per-field tooltips explain each
             control, but nobody hovers a field that looks broken -- so the split
             between what is live and what needs a reload is spelled out where it
             cannot be missed. */
          <p className="text-xs text-muted-foreground mt-3 leading-relaxed">
            <span className="text-foreground/75 font-medium">Live while loaded:</span>{" "}
            timeframes, speed, summary focus, VWAP &amp; Volume Profile settings.
            {" · "}
            <span className="text-foreground/75 font-medium">Needs a new session:</span>{" "}
            symbol, data source, dates, session hours, strategy &amp; parameters, capital,
            contracts, commission — each of those changes the bars or the fills this session
            was built from. Press <span className="text-foreground/75">✎ Change Setup</span> to
            edit them; ↺ Reset only rewinds this session. Hover a greyed field for its reason.
          </p>
        )}
        {lockPrompt && ready && (
          /* Answers the click where the click happened, instead of leaving the
             user to discover a button. */
          <div className="mt-3 flex flex-wrap items-center gap-3 rounded-lg border border-primary/45 bg-primary/[0.07] px-3 py-2.5">
            <span className="text-sm flex-1 min-w-[18rem]">
              <span className="font-medium">That field is fixed for this session.</span>{" "}
              <span className="text-muted-foreground">
                Symbol, data source, dates, session hours, strategy and the capital settings decide
                which bars are loaded and how every fill is priced, so they cannot change underneath
                a session that is already running.
              </span>
            </span>
            <Button size="sm" onClick={changeSetup}>✎ Change Setup now</Button>
            <Button size="sm" variant="secondary" onClick={() => setLockPrompt(false)}>Keep playing</Button>
          </div>
        )}
        {error && <p className="text-xs text-destructive mt-2">{error}</p>}
      </Card>

      {/* Nothing to show yet, and fetching a wide date range at a fine
          resolution is not instant -- so the ring holds the space the tables
          are about to occupy rather than leaving the page apparently empty. */}
      {status === "loading" && (
        <Card className="border border-white/6">
          <LoadingBlock
            label="Loading market data…"
            hint={`${symbol} · ${timeframes.join(" · ")} · ${startDate} to ${endDate}`}
          />
        </Card>
      )}

      {ready && (
        <>
          {/* Which pane the summary cards and trade table follow. Each timeframe
              runs its own strategy and broker server-side, so these figures are
              per-pane and cannot meaningfully be summed. The chart panes used to
              double as this selector; with the tables there was no way to change
              focus, so it is an explicit control. Purely a view switch -- it
              re-reads state already in the browser, so playback is untouched. */}
          <div className="flex items-center gap-2">
            <Label className="text-xs text-muted-foreground">Summary for</Label>
            <Select value={focusedTimeframe} onValueChange={setFocus}>
              <SelectTrigger className="w-40" aria-label="Summary timeframe">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {shownTimeframes.map((tf) => (
                  <SelectItem key={tf} value={tf}>
                    {tf}{tf === baseTimeframe ? " · clock base" : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span className="text-xs text-muted-foreground">
              each timeframe keeps its own broker and P&amp;L
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            <Metric label="Portfolio" value={`$${portfolioValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                    color={portfolioValue >= initialCapital ? GOOD : CRITICAL} />
            <Metric label="Total P&L" value={`${totalPnl >= 0 ? "+" : ""}$${totalPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                    color={totalPnl >= 0 ? GOOD : CRITICAL} />
            <Metric label="Trades" value={String(completedTrades.length)} />
            <Metric label="Win Rate" value={`${winRate.toFixed(0)}%`} />
            <Metric label="Avg Win" value={`$${avgWin.toLocaleString(undefined, { maximumFractionDigits: 0 })}`} color={GOOD} />
            <Metric label="Avg Loss" value={`$${avgLoss.toLocaleString(undefined, { maximumFractionDigits: 0 })}`} color={CRITICAL} />
            <Metric label="Position" value={position === 0 ? "FLAT" : position > 0 ? `LONG +${position}` : `SHORT ${position}`}
                    color={position === 0 ? NEUTRAL : position > 0 ? GOOD : CRITICAL} />
          </div>

          {lastSignal && (
            <div className="rounded-md px-3 py-2 border-l-4"
                 style={{
                   borderColor: lastSignal.type === "SELL" ? CRITICAL : lastSignal.type === "BUY" ? GOOD : "#e3b341",
                   background: `color-mix(in srgb, ${lastSignal.type === "SELL" ? CRITICAL : lastSignal.type === "BUY" ? GOOD : "#e3b341"} 12%, transparent)`,
                 }}>
              <b>{lastSignal.type}</b> <span className="text-muted-foreground">{lastSignal.reason}</span>
            </div>
          )}

          {/* Indicator settings. The same knobs as the Backtest page's gear
              dialogs, minus colour/width -- a table has no line to style, so
              offering those would be dead controls. Every value here re-derives
              the columns client-side, so changes apply to the already-streamed
              bars with no reload. */}
          <Card className="p-3 border border-white/6">
            <div className="flex items-center justify-between">
              <div className="flex flex-wrap items-center gap-4 text-sm">
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={showVwap} aria-label="Show VWAP"
                         onChange={(e) => setShowVwap(e.target.checked)} />
                  <span>VWAP</span>
                </label>
                <span className="text-xs text-muted-foreground font-mono">
                  {devLevels.length === 0
                    ? "bands off"
                    : devLevels.map((d) => `±${d.toFixed(1)}σ`).join("  ")}
                </span>
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={showVp} aria-label="Show Volume Profile"
                         onChange={(e) => setShowVp(e.target.checked)} />
                  <span>Volume Profile</span>
                </label>
                <label className="flex items-center gap-2"
                       title="Tint band values that two or more shown timeframes agree on, comparing only the digits before the decimal.">
                  <input type="checkbox" checked={markAgreement}
                         aria-label="Highlight matching band levels"
                         onChange={(e) => setMarkAgreement(e.target.checked)} />
                  <span>Match across timeframes</span>
                </label>
                <span className="text-xs text-muted-foreground font-mono">
                  whole numbers only
                </span>
                <span className="text-xs text-muted-foreground font-mono">
                  {vpBins} rows · VA {vpValueArea}%
                </span>
              </div>
              {/* Named for its contents. The Backtest chart puts a gear beside
                  each indicator; this page has one panel holding both, so a
                  button labelled just "Settings" gave someone hunting for a
                  Volume Profile gear nothing to recognise. */}
              <Button type="button" size="sm" variant="secondary"
                      aria-label="Volume Profile settings"
                      title="Deviation bands for VWAP, and rows / value area for Volume Profile"
                      onClick={() => setSettingsOpen((v) => !v)}>
                ⚙ VWAP &amp; Volume Profile settings
              </Button>
            </div>

            {settingsOpen && (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mt-3 pt-3 border-t border-white/6">
                {/* Multi-select, the same pattern as the timeframe buttons.
                    Every checked level gets its own pair of band columns in both
                    tables, so +/-1 and +/-2 can be read side by side instead of
                    by switching a single number back and forth -- which is how a
                    2-sigma band came to be compared against someone else's
                    1-sigma band. */}
                <div className="space-y-1 col-span-2">
                  <span className="text-xs text-muted-foreground">
                    deviations (&plusmn;&sigma;) &mdash; {devLevels.length} selected
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {ALL_DEV_LEVELS.map((d) => {
                      const on = devLevels.includes(d)
                      return (
                        <Button
                          key={d} type="button" size="sm"
                          variant={on ? "default" : "secondary"}
                          aria-pressed={on}
                          aria-label={`deviation ${d}`}
                          onClick={() => setDevLevels((prev) =>
                            prev.includes(d)
                              ? prev.filter((x) => x !== d)
                              : [...prev, d].sort((a, b) => a - b))}
                        >
                          {on ? "✓ " : ""}&plusmn;{d.toFixed(1)}
                        </Button>
                      )
                    })}
                  </div>
                </div>
                <label className="space-y-1">
                  <span className="text-xs text-muted-foreground">rows (bins)</span>
                  <Input type="number" min={4} max={200} value={vpBins} aria-label="rows (bins)"
                         onChange={(e) => setVpBins(Math.max(4, Number(e.target.value)))} />
                </label>
                <label className="space-y-1">
                  <span className="text-xs text-muted-foreground">value area percent</span>
                  <Input type="number" min={1} max={100} value={vpValueArea} aria-label="value area percent"
                         onChange={(e) => setVpValueArea(Number(e.target.value))} />
                </label>
                <div className="text-xs text-muted-foreground self-end pb-2">
                  Bands re-scale from the session sigma already computed for
                  these bars, so changes apply immediately.
                </div>
              </div>
            )}
          </Card>

          {/* DISPLAY -- Live Replay is a table, always. Charts were removed
              from this feature entirely: several candlestick panes split
              attention, and a single pane offered nothing the table does not.
              There is no chart fallback for one timeframe any more.

              Indicator columns come from two places, both reusing what the
              Backtest page already uses rather than a second implementation:
              VWAP/bands arrive in the frame at 2 sigma and are re-scaled here
              by the deviation settings, and Volume Profile is computed in the
              browser from each pane's accumulated bars. Both therefore react
              to the settings panel instantly. */}
          <Card className="p-0 border border-white/6 overflow-hidden">
              <div className="px-3 py-2 text-sm font-semibold border-b border-white/6">
                Live state &mdash; all timeframes
                {marketTime && (
                  <span className="ml-2 font-mono text-xs text-muted-foreground">
                  {/* market_time is the base bar-s OPEN; the clock the panes
                      were emitted against is one base bar later, which is also
                      what the Bar close column now shows. Same convention in
                      both places so they cannot read a minute apart. */}
                    market {closeInTz(marketTime, TF_MINUTES[baseTimeframe] ?? 1)} {TZ_LABEL}
                  </span>
                )}
                {/* THE DATA IS A SNAPSHOT, AND NOTHING USED TO SAY SO.
                    Bars are fetched once, at Load Data. On a live date the feed
                    keeps producing bars afterwards, and playback can only replay
                    what was downloaded -- so a finished replay sits at whatever
                    the newest bar was AT FETCH TIME, looking complete. Compared
                    against a broker screen that has moved on, that reads as
                    wrong values rather than old ones, and the only clue was a
                    timestamp nobody had reason to distrust.

                    A finished replay on today's date now says how far the
                    snapshot reaches and that Load Data is what extends it. */}
                {done && isToday && (
                  <span className="ml-2 text-xs rounded px-1.5 py-0.5"
                        style={{ background: "rgba(251,191,36,0.14)", color: "#fbbf24" }}>
                    snapshot ends {marketTime
                      ? closeInTz(marketTime, TF_MINUTES[baseTimeframe] ?? 1) + " " + TZ_LABEL
                      : "here"} &mdash; press Load Data to pull bars that have formed since
                  </span>
                )}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-[#0e1424] text-muted-foreground">
                    <tr>
                      <th className="text-left p-2 font-medium">TF</th>
                      <th className="text-left p-2 font-medium">Bar close ({TZ_LABEL})</th>
                      <th className="text-left p-2 font-medium">Opened ({TZ_LABEL})</th>
                      <th className="text-right p-2 font-medium">Open</th>
                      <th className="text-right p-2 font-medium">High</th>
                      <th className="text-right p-2 font-medium">Low</th>
                      <th className="text-right p-2 font-medium">Close</th>
                      <th className="text-right p-2 font-medium">Change</th>
                      <th className="text-right p-2 font-medium">Volume</th>
                      <th className="text-right p-2 font-medium">Bars</th>
                      <th className="text-left p-2 font-medium">Position</th>
                      <th className="text-right p-2 font-medium">P&amp;L</th>
                      {/* The deviation is spelled into the header because
                          "Upper" alone invites reading a band as the VWAP -- the
                          two sit adjacent and differ by whatever sigma happens
                          to be, so a 10-point gap looks like a disagreement
                          between platforms rather than two different rows. */}
                      {showVwap && <th className="text-right p-2 font-medium">VWAP</th>}
                      {showVwap && devLevels.flatMap((d) => [
                        <th key={`u${d}`} className="text-right p-2 font-medium">Upper +{d.toFixed(1)}&sigma;</th>,
                        <th key={`l${d}`} className="text-right p-2 font-medium">Lower -{d.toFixed(1)}&sigma;</th>,
                      ])}
                      {showVp && <th className="text-right p-2 font-medium">POC</th>}
                      {showVp && <th className="text-right p-2 font-medium">VAHigh</th>}
                      {showVp && <th className="text-right p-2 font-medium">VALow</th>}
                      <th className="text-left p-2 font-medium">Last signal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {shownTimeframes.map((tf) => {
                      const pane = panes[tf] ?? emptyPane(initialCapital)
                      const last = pane.bars[pane.bars.length - 1]
                      const delta = last ? last.c - last.o : 0
                      const pnl = pane.portfolioValue - initialCapital
                      // One pair of values per selected deviation level.
                      const bands = devLevels.flatMap((d) => [atDev(pane, d), atDev(pane, -d)])
                      const vp = profileFor(pane)
                      const num = price
                      return (
                        <tr key={tf} className="border-t border-white/6">
                          <td className="p-2 font-semibold">
                            {tf}
                            {tf === baseTimeframe && (
                              <span className="ml-1 text-[10px] text-muted-foreground">clock base</span>
                            )}
                          </td>
                          <td className="p-2 font-mono text-xs">
                            {last ? closeInTz(last.t, TF_MINUTES[tf]) : "—"}
                          </td>
                          <td className="p-2 font-mono text-xs text-muted-foreground">{last ? inTz(last.t) : "—"}</td>
                          <td className="p-2 text-right font-mono">{price(last?.o)}</td>
                          <td className="p-2 text-right font-mono">{price(last?.h)}</td>
                          <td className="p-2 text-right font-mono">{price(last?.l)}</td>
                          <td className="p-2 text-right font-mono font-semibold">{price(last?.c)}</td>
                          <td className="p-2 text-right font-mono"
                              style={{ color: delta === 0 ? NEUTRAL : delta > 0 ? GOOD : CRITICAL }}>
                            {last ? signed(delta) : "\u2014"}
                          </td>
                          <td className="p-2 text-right font-mono text-muted-foreground">
                            {last?.v != null ? last.v.toLocaleString() : "\u2014"}
                          </td>
                          <td className="p-2 text-right font-mono text-muted-foreground">
                            {pane.bars.length.toLocaleString()}
                          </td>
                          <td className="p-2 font-mono"
                              style={{ color: pane.position === 0 ? NEUTRAL : pane.position > 0 ? GOOD : CRITICAL }}>
                            {pane.position === 0 ? "FLAT" : pane.position > 0 ? `LONG +${pane.position}` : `SHORT ${pane.position}`}
                          </td>
                          <td className="p-2 text-right font-mono font-semibold"
                              style={{ color: pnl === 0 ? NEUTRAL : pnl > 0 ? GOOD : CRITICAL }}>
                            {pnl >= 0 ? "+" : ""}${Math.round(pnl).toLocaleString()}
                          </td>
                          {showVwap && <td className="p-2 text-right font-mono" style={{ color: "#ce93d8" }}>{num(pane.vwap)}</td>}
                          {showVwap && bands.map((b, k) => {
                            // Who else lands on this whole number? Empty unless
                            // two or more timeframes share it, so a tape showing
                            // a single timeframe never lights up.
                            const alsoOn = markAgreement
                              ? agreeingLabels(tapeAgreement, k, b, tf)
                              : []
                            const agreed = alsoOn.length > 0
                            return (
                              <td key={k}
                                  className="p-2 text-right font-mono"
                                  title={agreed
                                    ? `${Math.trunc(b as number)} also on ${alsoOn.join(", ")}`
                                    : undefined}
                                  style={{
                                    color: k % 2 === 0 ? "#e3b341" : "#f06292",
                                    // One highlight colour for both sides: the text
                                    // colour already separates upper from lower, so
                                    // tinting by side would say nothing new, and a
                                    // green would read as P&L.
                                    ...(agreed ? {
                                      backgroundColor: "rgba(45, 212, 191, 0.16)",
                                      boxShadow: "inset 0 0 0 1px rgba(45, 212, 191, 0.55)",
                                      borderRadius: 4,
                                      fontWeight: 600,
                                    } : {}),
                                  }}>
                                {num(b)}
                              </td>
                            )
                          })}
                          {showVp && <td className="p-2 text-right font-mono" style={{ color: "#38bdf8" }}>{num(vp?.poc)}</td>}
                          {showVp && <td className="p-2 text-right font-mono" style={{ color: "#7dd3fc" }}>{num(vp?.vah)}</td>}
                          {showVp && <td className="p-2 text-right font-mono" style={{ color: "#7dd3fc" }}>{num(vp?.val)}</td>}
                          <td className="p-2 text-xs">
                            {pane.lastSignal ? (
                              <span style={{ color: pane.lastSignal.type === "BUY" ? GOOD : pane.lastSignal.type === "SELL" ? CRITICAL : "#e3b341" }}>
                                <b>{pane.lastSignal.type}</b>{" "}
                                <span className="text-muted-foreground">{pane.lastSignal.reason}</span>
                              </span>
                            ) : <span className="text-muted-foreground">&mdash;</span>}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </Card>

            <Card className="p-0 border border-white/6 overflow-hidden">
              <div className="px-3 py-2 text-sm font-semibold border-b border-white/6 flex justify-between">
                <span>Consolidated tape &mdash; newest first</span>
                <span className="text-xs text-muted-foreground font-normal">
                  {jumpedRows
                    ? (jumpedRows.length === 1
                        ? "one bar"
                        : `${jumpedRows.length} timeframes at one moment`)
                    : shownTape.length === 0
                      ? "no bars yet"
                      : `newest ${Math.min(TAPE_WINDOW, shownTape.length)} of ${shownTape.length.toLocaleString()} bars`}
                </span>
              </div>

              {/* Reaching an earlier bar used to mean pausing playback on exactly
                  the right tick, which at 0.1s per tick nobody can do. Jump goes
                  straight to it and shows the matching bar on EVERY selected
                  timeframe -- one moment, resolved against each timeframe's own
                  boundaries -- and Clear returns to the live tape. There is
                  deliberately no paging here: three navigation buttons for a
                  table mostly read at its newest end were more to understand
                  than they were worth. */}
              <div className="flex flex-wrap items-end gap-2 px-3 py-2 border-b border-white/6">
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Jump to date</Label>
                  {/* min/max: a bare date input accepts any year the spec allows,
                      so a stray keystroke turned 2026 into 82026 and the jump
                      dutifully looked for a bar eighty thousand years out. The
                      browser now refuses anything outside the days on the tape,
                      and jumpToTime says so as well for the paths min/max cannot
                      cover (typing, pasting, autofill). */}
                  <Input type="date" className="w-40" value={jumpDate}
                         min={tapeDayRange?.[0]} max={tapeDayRange?.[1]}
                         onChange={(e) => setJumpDate(e.target.value)}
                         title={tapeDayRange
                           ? `Loaded: ${tapeDayRange[0]} to ${tapeDayRange[1]}. Leave blank for the newest day.`
                           : "Leave blank to use the newest day in the tape"} />
                </div>
                <div className="space-y-1">
                  {/* Says which end of the bar it means. "Time" alone was read as
                      the close by the code and as the open by everyone using it. */}
                  <Label className="text-xs text-muted-foreground">
                    Bar opened at
                  </Label>
                  <TimeField value={jumpTime} onChange={setJumpTime} label="Jump time" />
                </div>

                {/* Which timeframes the jump answers for, chosen HERE.
                    Jump has always returned a row per active timeframe, but the
                    only place to change that set was the selector at the top of
                    the page -- so picking "this moment on 1m, 5m and 10m" meant
                    scrolling away from the control you were using. These are the
                    same toggles and the same handler, put where the question is
                    asked. Ticking one that is not loaded adds it and backfills
                    it, exactly as it does above. */}
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">
                    Timeframes &mdash; {shownTimeframes.length} shown
                  </Label>
                  <div className="flex flex-wrap gap-1">
                    {ALL_TIMEFRAMES.map((tf) => {
                      const on = timeframes.includes(tf)
                      const needsRefetch =
                        ready && !!dataTimeframe && !isBuildableFrom(tf, dataTimeframe)
                      return (
                        <Button
                          key={tf} type="button" size="sm"
                          className="h-7 px-2 text-xs"
                          variant={on ? "default" : "secondary"}
                          aria-pressed={on}
                          aria-label={`jump timeframe ${tf}`}
                          title={
                            needsRefetch
                              ? `${tf} cannot be built from the loaded ${dataTimeframe} bars — selecting it refetches`
                              : on ? `${tf} is included in the jump` : `Add ${tf} to the jump`
                          }
                          onClick={() => handleTimeframeToggle(tf)}
                        >
                          {on ? "✓ " : ""}{tf}
                          {needsRefetch && <span className="ml-0.5 opacity-60">↻</span>}
                        </Button>
                      )
                    })}
                  </div>
                </div>
                {/* Disabled with nothing in the tape, and saying so. A greyed
                    button that explains nothing is what sent the last three
                    "where is it?" rounds: Jump can only reach bars that have
                    actually been replayed, so an empty tape has nothing to
                    match. */}
                {/* Set this to the clock of the platform you compare against.
                    Matching a label like "12:45" across two screens on different
                    clocks compares bars an hour apart, and the numbers really do
                    differ -- which is indistinguishable from an OHLC bug. */}
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Times shown in</Label>
                  <div className="flex gap-1">
                    {TZ_CHOICES.map((z) => (
                      <Button
                        key={z.short} type="button" size="sm"
                        className="h-7 px-2 text-xs"
                        variant={tzOffset === z.offset ? "default" : "secondary"}
                        aria-pressed={tzOffset === z.offset}
                        aria-label={`times in ${z.short}`}
                        title={z.label}
                        onClick={() => setTzOffset(z.offset)}
                      >
                        {z.short}
                      </Button>
                    ))}
                  </div>
                </div>

                <Button size="sm" onClick={jumpToTime} disabled={shownTape.length === 0}
                        title={shownTape.length === 0
                          ? "No bars yet. Press ▶ Play and let the replay run past the time you want, then Jump."
                          : `Show the bar at that moment on each of the ${shownTimeframes.length} selected timeframe(s)`}>
                  Jump
                </Button>
                {shownTape.length === 0 && (
                  <span className="text-xs text-muted-foreground">
                    Press <span className="text-foreground/70">&#9654; Play</span> first &mdash;
                    Jump searches bars that have already been replayed.
                  </span>
                )}
                {jumpedRows && (
                  <Button size="sm" variant="secondary"
                          onClick={() => { setJumpedRows(null); setJumpNote(null) }}>
                    Clear
                  </Button>
                )}
                {jumpNote && (
                  <span className="text-xs text-primary" role="status">{jumpNote}</span>
                )}
              </div>
              {/* table-sticky pins the header while the tape scrolls -- with 400
                  rows and 13 columns, losing the column names a screen down was
                  the main thing making this table hard to read. */}
              <div className="overflow-auto" style={{ maxHeight: 460 }}>
                <table className="w-full text-sm table-sticky">
                  <thead className="bg-[#0e1424] text-muted-foreground sticky top-0">
                    <tr>
                      <th className="text-left p-2 font-medium">Bar close ({TZ_LABEL})</th>
                      <th className="text-left p-2 font-medium">Opened ({TZ_LABEL})</th>
                      <th className="text-left p-2 font-medium">TF</th>
                      <th className="text-right p-2 font-medium">Open</th>
                      <th className="text-right p-2 font-medium">High</th>
                      <th className="text-right p-2 font-medium">Low</th>
                      <th className="text-right p-2 font-medium">Close</th>
                      <th className="text-right p-2 font-medium">Change</th>
                      <th className="text-right p-2 font-medium">Volume</th>
                      {showVwap && <th className="text-right p-2 font-medium">VWAP</th>}
                        {/* Same columns and labels as Live state above. These were
                            previously visible only for the newest tick, so reading a
                            band or the profile at an earlier bar meant pausing at
                            exactly that tick. */}
                        {showVwap && devLevels.flatMap((d) => [
                          <th key={`u${d}`} className="text-right p-2 font-medium">Upper +{d.toFixed(1)}&sigma;</th>,
                          <th key={`l${d}`} className="text-right p-2 font-medium">Lower -{d.toFixed(1)}&sigma;</th>,
                        ])}
                        {showVp && <th className="text-right p-2 font-medium">POC</th>}
                        {showVp && <th className="text-right p-2 font-medium">VAHigh</th>}
                        {showVp && <th className="text-right p-2 font-medium">VALow</th>}
                      <th className="text-left p-2 font-medium">Position</th>
                      <th className="text-left p-2 font-medium">Signal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tapeWindow.map((r) => {
                      const d = r.c - r.o
                        const vp = profileAtRow(r)
                      return (
                        <tr key={`${r.t}-${r.tf}`} className="border-t border-white/6">
                          <td className="p-2 font-mono text-xs">{closeInTz(r.t, TF_MINUTES[r.tf])}</td>
                          <td className="p-2 font-mono text-xs text-muted-foreground">{inTz(r.t)}</td>
                          <td className="p-2">
                            <span className="px-1.5 py-0.5 rounded text-[11px] font-semibold bg-white/8">{r.tf}</span>
                          </td>
                          <td className="p-2 text-right font-mono">{price(r.o)}</td>
                          <td className="p-2 text-right font-mono">{price(r.h)}</td>
                          <td className="p-2 text-right font-mono">{price(r.l)}</td>
                          <td className="p-2 text-right font-mono font-semibold">{price(r.c)}</td>
                          <td className="p-2 text-right font-mono"
                              style={{ color: d === 0 ? NEUTRAL : d > 0 ? GOOD : CRITICAL }}>
                            {signed(d)}
                          </td>
                          <td className="p-2 text-right font-mono text-muted-foreground">
                            {r.v != null ? r.v.toLocaleString() : "\u2014"}
                          </td>
                          {showVwap && (
                            <td className="p-2 text-right font-mono" style={{ color: "#ce93d8" }}>
                              {price(r.vwap)}
                            </td>
                          )}
                            {showVwap && devLevels.flatMap((d) => [
                              <td key={`u${d}`} className="p-2 text-right font-mono" style={{ color: "#e3b341" }}>
                                {tapeNum(rowBand(r, d))}
                              </td>,
                              <td key={`l${d}`} className="p-2 text-right font-mono" style={{ color: "#f06292" }}>
                                {tapeNum(rowBand(r, -d))}
                              </td>,
                            ])}
                            {showVp && (
                              <td className="p-2 text-right font-mono" style={{ color: "#38bdf8" }}>
                                {tapeNum(vp?.poc)}
                              </td>
                            )}
                            {showVp && (
                              <td className="p-2 text-right font-mono" style={{ color: "#7dd3fc" }}>
                                {tapeNum(vp?.vah)}
                              </td>
                            )}
                            {showVp && (
                              <td className="p-2 text-right font-mono" style={{ color: "#7dd3fc" }}>
                                {tapeNum(vp?.val)}
                              </td>
                            )}
                          <td className="p-2 font-mono text-xs"
                              style={{ color: r.position === 0 ? NEUTRAL : r.position > 0 ? GOOD : CRITICAL }}>
                            {r.position === 0 ? "FLAT" : r.position > 0 ? `+${r.position}` : String(r.position)}
                          </td>
                          <td className="p-2 text-xs">
                            {r.signalType ? (
                              <span style={{ color: r.signalType === "BUY" ? GOOD : r.signalType === "SELL" ? CRITICAL : "#e3b341" }}>
                                <b>{r.signalType}</b>
                              </span>
                            ) : <span className="text-muted-foreground">&mdash;</span>}
                          </td>
                        </tr>
                      )
                    })}
                    {shownTape.length === 0 && (
                      <tr><td colSpan={showVwap ? 11 : 10} className="p-6 text-center text-muted-foreground">
                        Press Play to start streaming bars.
                      </td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </Card>
          {completedTrades.length > 0 && (
            <Card className="p-4 border border-white/6 w-full">
              <p className="text-sm font-semibold mb-2">Recent Trades — {focusedTimeframe} pane</p>
              <div className="overflow-x-auto rounded-lg border border-white/6">
                <table className="w-full text-sm">
                  <thead className="bg-[#0e1424] text-muted-foreground">
                    <tr>
                      <th className="text-left p-2 font-medium">Entry</th>
                      <th className="text-left p-2 font-medium">Exit</th>
                      <th className="text-left p-2 font-medium">Dir</th>
                      <th className="text-right p-2 font-medium">Entry $</th>
                      <th className="text-right p-2 font-medium">Exit $</th>
                      <th className="text-right p-2 font-medium">P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {completedTrades.slice(-10).reverse().map((t, i) => (
                      <tr key={i} className="border-t border-white/6">
                        <td className="p-2">{t.entry_time.replace("T", " ").slice(0, 16)}</td>
                        <td className="p-2">{t.exit_time ? t.exit_time.replace("T", " ").slice(0, 16) : "OPEN"}</td>
                        <td className={`p-2 ${t.direction === "LONG" ? "text-green-400" : "text-red-400"}`}>{t.direction}</td>
                        <td className="p-2 text-right">{price(t.entry_price)}</td>
                        <td className="p-2 text-right">{price(t.exit_price)}</td>
                        <td className={`p-2 text-right font-semibold ${t.pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {t.pnl >= 0 ? "+" : ""}${t.pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}

      {!ready && !error && (
        <p className="text-muted-foreground p-8 text-center">
          Configure your strategy above, then click <b>⬇ Load Data</b> to begin.
        </p>
      )}
    </div>
  )
}
