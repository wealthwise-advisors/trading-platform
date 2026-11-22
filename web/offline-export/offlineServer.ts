/**
 * The offline copy's stand-in for the server.
 *
 * The app talks to its server with fetch("/api/..."). In a file sent by email there is no
 * server, so every answer the screens need was recorded beforehand (record_app.py) for one
 * long run per timeframe (its whole date range) and is embedded as window.__REC__. This replaces fetch
 * for /api/* and answers from it:
 *   - account, strategies, symbols, quotes ...         -> the recorded answer
 *   - POST /api/backtests (Run Backtest)               -> the recorded run for that timeframe,
 *                                                          CUT to the dates picked in the sidebar
 *   - GET /api/backtests/OFFLINE-<tf>[~from~to]/<what> -> that run's answer, cut the same way
 *   - anything else (Market Grid, optimiser, saving)   -> a plain message saying so
 *
 * Cutting a run to fewer days: bars, indicators, swing points, trades, patterns and Elliott
 * waves are kept where they fall inside the dates; the equity curve is restarted at the
 * starting capital; the summary is recomputed with src/backtesting/metrics.py's formulas.
 * shortcut: trades and swing letters come from the whole recorded run (a live run started on the
 * later date would count them from there); exact only with the live app.
 */
type Json = any // eslint-disable-line @typescript-eslint/no-explicit-any
type Rec = { get: Record<string, Json>; bt: Record<string, Record<string, Json>> }
const REC = (window as unknown as { __REC__: Rec }).__REC__
export const OFFLINE_TFS = Object.keys(REC.bt)
const FULL = REC.bt[OFFLINE_TFS[0]].summary as { start_date: string; end_date: string }
const LIVE_ONLY = `This offline copy holds ${FULL.start_date} to ${FULL.end_date}. `
const reply = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })

const inRange = (t: string | undefined, a: string, b: string) => !!t && t >= `${a}T00:00:00` && t <= `${b}T23:59:59`
const cache = new Map<string, Record<string, Json>>()

/** One run cut to [a, b], every answer the screens ask for. */
function cut(tf: string, a: string, b: string): Record<string, Json> {
  const key = `${tf}~${a}~${b}`
  if (cache.has(key)) return cache.get(key)!
  const run = REC.bt[tf]
  if (a <= FULL.start_date && b >= FULL.end_date) return run
  const id = `OFFLINE-${key}`
  const price = run["/price-data"]
  const keep = price.bars.map((x: Json) => inRange(x.t, a, b))
  const pick = (xs: Json[]) => xs.filter((_: Json, i: number) => keep[i])
  const first = keep.indexOf(true)
  const before = first > 0 ? price.bars.slice(0, first) : []
  const indicators: Json = {}
  for (const [k, v] of Object.entries(price.indicators)) indicators[k] = Array.isArray(v) && v.length === keep.length ? pick(v) : v
  // Vol Avg (20) stays warm: the earlier bars' volumes join its context.
  const ctx = price.volume_context ?? { t: [], v: [] }
  const volume_context = { t: [...ctx.t, ...before.map((x: Json) => x.t)], v: [...ctx.v, ...before.map((x: Json) => x.v)] }
  const trades = run["/trades"].filter((x: Json) => inRange(x.entry_time, a, b) && (!x.exit_time || inRange(x.exit_time, a, b)))
  // Equity rebuilt from THIS range's trades only: the starting capital, each closed trade's
  // P&L at its exit, an open one marked at the bar's close. Cutting the recorded curve kept the
  // swings of a trade opened before the range, so Total Return and Monthly Returns disagreed.
  const cap = run.summary.initial_capital
  const pv = pointValue(run["/trades"])
  const bars = price.bars.filter((x: Json) => inRange(x.t, a, b))
  let peak = -Infinity
  const equity = bars.map((x: Json) => {
    let e = cap
    for (const tr of trades) {
      if (tr.exit_time && tr.exit_time <= x.t) e += tr.pnl
      else if (tr.entry_time <= x.t) e += (x.c - tr.entry_price) * (tr.direction === "LONG" ? 1 : -1) * tr.qty * pv - tr.commission / 2
    }
    peak = Math.max(peak, e)
    return { t: x.t, equity: e, drawdown_pct: peak > 0 ? ((e - peak) / peak) * 100 : 0 }
  })
  const zz = run["/zigzag"]
  const zigzag: Json = {}
  for (const [k, v] of Object.entries(zz)) zigzag[k] = (v as Json[]).filter((p) => inRange(p.t, a, b))
  const ew = run["/elliott-wave"]
  const elliott = { ...ew, pivots: (ew.pivots ?? []).filter((p: Json) => inRange(p.t, a, b)),
                    waves: (ew.waves ?? []).filter((w: Json) => inRange(w.start_t, a, b) && inRange(w.end_t, a, b)) }
  const summary = { ...run.summary, backtest_id: id, start_date: a, end_date: b, ...metrics(trades, equity, cap) }
  const out: Record<string, Json> = {
    post: summary, summary,
    "/price-data": { ...price, bars: pick(price.bars), indicators, volume_context },
    "/trades": trades, "/equity-curve": equity, "/zigzag": zigzag, "/elliott-wave": elliott,
    "/monthly-returns": monthly(equity, cap),
    "/chart-patterns": run["/chart-patterns"].filter((x: Json) => inRange(x.start, a, b) && inRange(x.end, a, b)),
    "/candlestick-patterns": run["/candlestick-patterns"].filter((x: Json) => inRange(x.timestamp, a, b)),
  }
  cache.set(key, out)
  return out
}

/** Dollars per point, read back from a recorded trade: pnl = points x qty x pv - commission. */
function pointValue(trades: Json[]): number {
  for (const t of trades) {
    const pts = (t.exit_price - t.entry_price) * (t.direction === "LONG" ? 1 : -1) * t.qty
    if (t.exit_price != null && Math.abs(pts) > 1e-9) return Math.round((t.pnl + t.commission) / pts)
  }
  return 50   // /ES
}

/** src/backtesting/metrics.py, for a run cut to fewer days. */
function metrics(trades: Json[], equity: Json[], cap: number) {
  const pnls = trades.map((t) => t.pnl as number)
  const wins = pnls.filter((p) => p > 0), losses = pnls.filter((p) => p <= 0)
  const sum = (xs: number[]) => xs.reduce((s, x) => s + x, 0)
  const mean = (xs: number[]) => (xs.length ? sum(xs) / xs.length : 0)
  const points = (t: Json) => (t.exit_price - t.entry_price) * (t.direction === "LONG" ? 1 : -1)
  const total = sum(pnls), gw = sum(wins), gl = Math.abs(sum(losses))
  const eq = equity.map((x) => x.equity as number)
  const rets = eq.slice(1).map((e, i) => e / eq[i] - 1)
  const sd = (xs: number[]) => { const m = mean(xs); return Math.sqrt(sum(xs.map((x) => (x - m) ** 2)) / Math.max(1, xs.length - 1)) }
  const down = rets.filter((r) => r < 0)
  let peak = -Infinity, dd = 0
  for (const e of eq) { peak = Math.max(peak, e); dd = Math.min(dd, (e - peak) / peak) }
  const durs = trades.map((t) => t.duration_min).filter((d) => d != null)
  return {
    total_trades: trades.length, winning_trades: wins.length, losing_trades: losses.length,
    total_pnl: total, final_capital: cap + total, total_return_pct: (total / cap) * 100,
    win_rate: trades.length ? (wins.length / trades.length) * 100 : 0,
    avg_win: mean(wins), avg_loss: mean(losses),
    avg_win_points: mean(trades.filter((t) => t.pnl > 0).map(points)),
    avg_loss_points: mean(trades.filter((t) => t.pnl <= 0).map(points)),
    profit_factor: gl > 0 ? gw / gl : null,   // inf / nan both travel as null, as the API sends them
    avg_trade_duration_min: mean(durs),
    sharpe_ratio: rets.length > 1 && sd(rets) > 0 ? (mean(rets) / sd(rets)) * Math.sqrt(252) : 0,
    sortino_ratio: down.length > 1 && sd(down) > 0 ? (mean(rets) / sd(down)) * Math.sqrt(252) : 0,
    max_drawdown_pct: Math.abs(dd) * 100,
    ...(trades.length ? {} : { profit_factor: null, total_pnl: 0, final_capital: cap, total_return_pct: 0 }),
  }
}

/** api/serializers.monthly_returns: each month from the month before, the first from the capital. */
function monthly(equity: Json[], cap: number) {
  const last = new Map<string, number>()
  for (const x of equity) last.set(x.t.slice(0, 7), x.equity)
  const years = [...new Set([...last.keys()].map((k) => k.slice(0, 4)))].sort()
  let prev = cap
  const byMonth = new Map<string, number>()
  for (const k of [...last.keys()].sort()) { const v = last.get(k)!; byMonth.set(k, Math.round((v / prev - 1) * 10000) / 100); prev = v }
  return {
    years, months: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    values: years.map((y) => Array.from({ length: 12 }, (_, m) => byMonth.get(`${y}-${String(m + 1).padStart(2, "0")}`) ?? null)),
  }
}

// The file needs no network, so the app's "No connection" banner would only ever mislead:
// it is always "online" here, and the browser's online/offline events never reach the app.
Object.defineProperty(navigator, "onLine", { get: () => true, configurable: true })
for (const ev of ["online", "offline"]) window.addEventListener(ev, (e) => e.stopImmediatePropagation(), true)

// Export Data / Export Report are plain download links to the server, which a file has not got:
// Chrome would list a failed download. Say why instead, and stay on the page.
document.addEventListener("click", (e) => {
  const a = (e.target as Element | null)?.closest?.("a[href*='/api/']")
  if (!a) return
  e.preventDefault()
  e.stopPropagation()
  window.alert("Downloads (CSV, Excel, PDF, Word and the HTML report) need the live AutoTrader app.\n\n" +
               `Everything else works in this offline copy: the charts, Run Backtest for ${FULL.start_date} to ${FULL.end_date}, and every results tab.`)
}, true)

const realFetch = window.fetch.bind(window)
window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url
  const i = url.indexOf("/api/")
  if (i < 0) return realFetch(input, init)
  const path = url.slice(i)
  const method = (init?.method ?? "GET").toUpperCase()
  const bare = path.split("?")[0]

  if (method === "POST" && bare === "/api/backtests") {
    const req = JSON.parse(String(init?.body ?? "{}"))
    const tf = req.timeframe as string
    if (!REC.bt[tf]) return reply(400, { detail: `${tf} is not in this file: it holds ${OFFLINE_TFS[0]} to ${OFFLINE_TFS[OFFLINE_TFS.length - 1]}.` })
    const a = (req.start_date as string) ?? FULL.start_date, b = (req.end_date as string) ?? FULL.end_date
    if (b < FULL.start_date || a > FULL.end_date || a > b) {
      return reply(400, { detail: LIVE_ONLY + `Pick dates between ${FULL.start_date} and ${FULL.end_date}.` })
    }
    const run = cut(tf, a < FULL.start_date ? FULL.start_date : a, b > FULL.end_date ? FULL.end_date : b)
    if (!run["/price-data"].bars.length) return reply(400, { detail: LIVE_ONLY + "No trading in those dates (a weekend?)." })
    return reply(200, run.post)
  }
  const m = bare.match(/^\/api\/backtests\/OFFLINE-([^/~]+)(?:~([\d-]+)~([\d-]+))?(\/[^/]+)?$/)
  if (m && method === "GET") {
    const run = m[2] ? cut(m[1], m[2], m[3]) : REC.bt[m[1]]
    const body = run?.[m[4] ?? "summary"]
    return body !== undefined ? reply(200, body) : reply(404, { detail: LIVE_ONLY + "This view needs the live app." })
  }
  if (method === "GET") {
    if (path in REC.get) return reply(200, REC.get[path])
    if (bare === "/api/symbols") return reply(200, REC.get["/api/symbols?data_source=schwab"])
    if (bare in REC.get) return reply(200, REC.get[bare])
  }
  return reply(400, { detail: LIVE_ONLY + "Running the Market Grid replay, the optimiser and saving need the live app." })
}
