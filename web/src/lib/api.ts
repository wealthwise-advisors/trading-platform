// Typed fetch client for the FastAPI backend. Always calls relative /api/...
// paths — Vite's dev server proxies these to uvicorn (see vite.config.ts);
// in production the same relative paths work if FastAPI serves the built
// frontend directly.

import type {
  StrategyMeta, DataSourceMeta, SymbolMeta, BacktestRequest, BacktestSummary,
  TradeRecord, PriceDataResponse, EquityPoint, ZigZagResponse, WinLoss,
  CandlestickPatternRecord, ChartPatternRecord, MonthlyReturns,
  ReplayCreateRequest, ReplayCreateResponse, SchwabStatus,
  OptimizeRequest, OptimizeResponse, ElliottWaveResponse,
} from "./types"

const BASE = "/api"

/** Where an unauthenticated visitor is sent. */
export const SIGN_IN_PAGE = "/autotrader_signin.html"

/**
 * Bounce to the sign-in page once, carrying a reason.
 *
 * Guarded by a module-level flag: several panels fetch in parallel, so a single
 * expired session produces a burst of 401s, and without this each one would
 * schedule its own navigation. The `next` parameter lets the user come back to
 * the page they were on rather than the dashboard root.
 */
let redirecting = false
function toSignIn(reason: string) {
  if (redirecting) return
  redirecting = true
  const here = window.location.pathname + window.location.search
  // Do not append `next` if we are ALREADY on the sign-in page: that is how a
  // redirect loop starts.
  if (window.location.pathname.endsWith("autotrader_signin.html")) return
  const q = new URLSearchParams({ reason, next: here })
  window.location.assign(`${SIGN_IN_PAGE}?${q}`)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",   // send the session cookie
    ...init,
  })
  // 401 means the session is gone or was never there. It is the ONLY status
  // treated this way -- a 403 is a real authorisation refusal and a 500 is a
  // defect, and bouncing either to a login screen would hide the actual
  // problem behind a sign-in prompt.
  if (res.status === 401) {
    toSignIn("expired")
    throw new Error("Your session has expired. Please sign in again.")
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "")
    // FastAPI puts the human-readable reason in `detail`. Surfacing the whole
    // response instead meant the UI showed
    // `400 Bad Request: {"detail":"No bars found for ES between …"}` --
    // the useful sentence wrapped in JSON and a status line. Unwrap it when
    // it's there, and only fall back to the raw body when it isn't.
    let detail = ""
    try {
      const parsed = JSON.parse(body)
      if (typeof parsed?.detail === "string") detail = parsed.detail
      else if (Array.isArray(parsed?.detail)) {
        // Pydantic validation errors arrive as a list of {loc, msg}.
        detail = parsed.detail
          .map((d: { loc?: (string | number)[]; msg?: string }) =>
            `${(d.loc ?? []).filter((p) => p !== "body").join(".")}: ${d.msg ?? ""}`.trim())
          .join("; ")
      }
    } catch {
      /* not JSON — fall through to the raw body */
    }
    throw new Error(detail || body || `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export interface Me {
  username: string
  full_name: string
  email: string
  country: string
}

/**
 * Auth calls, kept apart from `api` on purpose.
 *
 * `whoami` must NOT go through request(): request() bounces a 401 to the sign-in
 * page, and the whole point of whoami is to ASK whether there is a session.
 * Routing it through the same helper would turn "not signed in" into a redirect
 * before the caller ever saw the answer.
 */
export const auth = {
  async whoami(): Promise<Me | null> {
    const res = await fetch(`${BASE}/auth/me`, { credentials: "same-origin" })
    if (res.status === 401) return null
    if (!res.ok) throw new Error(`Could not check the session (${res.status}).`)
    return res.json() as Promise<Me>
  },

  async logout(): Promise<void> {
    await fetch(`${BASE}/auth/logout`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
    }).catch(() => {
      /* the redirect below matters more than a failed POST */
    })
  },
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  strategies: () => request<StrategyMeta[]>("/strategies"),
  dataSources: () => request<DataSourceMeta[]>("/data-sources"),
  contracts: () => request<Record<string, unknown>>("/contracts"),
  // Symbols the given data source can actually serve. For external_csv this
  // is derived from the files on disk, so the dropdown cannot offer a symbol
  // with no data behind it.
  symbols: (dataSource: string) =>
    request<SymbolMeta[]>(`/symbols?data_source=${encodeURIComponent(dataSource)}`),

  runBacktest: (req: BacktestRequest) =>
    request<BacktestSummary>("/backtests", { method: "POST", body: JSON.stringify(req) }),
  getBacktest: (id: string) => request<BacktestSummary>(`/backtests/${id}`),
  getTrades: (id: string) => request<TradeRecord[]>(`/backtests/${id}/trades`),
  getPriceData: (id: string) => request<PriceDataResponse>(`/backtests/${id}/price-data`),
  getEquityCurve: (id: string) => request<EquityPoint[]>(`/backtests/${id}/equity-curve`),
  getZigZag: (id: string, dev3: number, dev10: number) =>
    request<ZigZagResponse>(`/backtests/${id}/zigzag?dev_3=${dev3}&dev_10=${dev10}`),
  // Elliott Wave. The three params are the pivot ladder's D-13 values -- the
  // only knobs the backend actually exposes. Defaults intentionally omitted so
  // the server's own defaults apply and the two cannot drift (SRS FR-1e.4).
  getElliottWave: (id: string, opts?: { thetaBase?: number; ratio?: number; scales?: number }) => {
    const q = new URLSearchParams()
    if (opts?.thetaBase !== undefined) q.set("theta_base", String(opts.thetaBase))
    if (opts?.ratio !== undefined) q.set("ratio", String(opts.ratio))
    if (opts?.scales !== undefined) q.set("scales", String(opts.scales))
    const qs = q.toString()
    return request<ElliottWaveResponse>(`/backtests/${id}/elliott-wave${qs ? `?${qs}` : ""}`)
  },
  getWinLoss: (id: string) => request<WinLoss>(`/backtests/${id}/win-loss`),
  getCandlestickPatterns: (id: string, minConfidence = 70) =>
    request<CandlestickPatternRecord[]>(`/backtests/${id}/candlestick-patterns?min_confidence=${minConfidence}`),
  getChartPatterns: (id: string) =>
    request<ChartPatternRecord[]>(`/backtests/${id}/chart-patterns`),
  getMonthlyReturns: (id: string) =>
    request<MonthlyReturns>(`/backtests/${id}/monthly-returns`),
  reportUrl: (id: string, format: string = "html") => `${BASE}/backtests/${id}/report?format=${format}`,
  dataExportUrl: (params: { symbol: string; timeframe: string; start: string; end: string; dataSource: string; format: string }) =>
    `${BASE}/data/export?symbol=${params.symbol}&timeframe=${params.timeframe}&start=${params.start}&end=${params.end}&data_source=${params.dataSource}&format=${params.format}`,

  createReplay: (req: ReplayCreateRequest) =>
    request<ReplayCreateResponse>("/replay", { method: "POST", body: JSON.stringify(req) }),
  replayWsUrl: (id: string) => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:"
    return `${proto}//${window.location.host}${BASE}/replay/ws/${id}`
  },

  schwabStatus: () => request<SchwabStatus>("/schwab/status"),
  schwabAuthUrl: () => request<{ auth_url: string }>("/schwab/auth-url"),
  schwabCompleteAuth: (redirect_url: string) =>
    request<SchwabStatus>("/schwab/complete-auth", { method: "POST", body: JSON.stringify({ redirect_url }) }),

  runOptimizer: (req: OptimizeRequest) =>
    request<OptimizeResponse>("/optimize", { method: "POST", body: JSON.stringify(req) }),
}
