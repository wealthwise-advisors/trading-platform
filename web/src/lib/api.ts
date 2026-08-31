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

/**
 * How long a request may take before it is abandoned.
 *
 * A fetch with no timeout does not fail when the server stops answering -- it
 * waits, and the panel that fired it spins forever with no error and no way
 * back. The browser's own limit is minutes, which is indistinguishable from
 * hung to anyone watching.
 *
 * Two values, because one number cannot serve both: a metadata read that has
 * not answered in 30s is broken, while a backtest legitimately spends minutes
 * loading bars and running an engine. A single short timeout would cancel real
 * work; a single long one would leave a dead panel spinning.
 */
export const TIMEOUT_MS = 30_000
export const LONG_TIMEOUT_MS = 300_000

/** Thrown when we gave up waiting, as opposed to the server saying no. */
export class TimeoutError extends Error {
  constructor(ms: number) {
    super(`The server did not respond within ${Math.round(ms / 1000)}s. It may be busy or unreachable.`)
    this.name = "TimeoutError"
  }
}

/**
 * Deliberately NO automatic retry.
 *
 * Every mutation here creates something -- a backtest, a replay session, an
 * account closure -- and none is idempotent. A transparent retry on a request
 * that actually succeeded but whose response was lost would run it twice, and
 * the user would never know which of the two they were looking at. Retrying is
 * the caller's decision, offered as a button, not taken on their behalf.
 */
async function request<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const { timeoutMs = TIMEOUT_MS, ...rest } = init ?? {}

  // AbortSignal.timeout() would be shorter, but it reports as a plain
  // AbortError, indistinguishable from a caller who navigated away. An
  // explicit controller lets the two be told apart below.
  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",   // send the session cookie
      signal: controller.signal,
      ...rest,
    })
  } catch (e) {
    if (timedOut) throw new TimeoutError(timeoutMs)
    // fetch rejects with a bare "Failed to fetch" for DNS failure, a refused
    // connection and an offline machine alike. That sentence tells the user
    // nothing they can act on, so say which of those it most likely is.
    if (!navigator.onLine) {
      throw new Error("You appear to be offline. Check your connection and try again.")
    }
    throw new Error(`Could not reach the server. ${(e as Error)?.message ?? ""}`.trim())
  } finally {
    clearTimeout(timer)
  }
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
  /** Whether the address has been proved, not merely typed. */
  email_verified: boolean
  /** Whether this person has already been shown the introduction. */
  onboarded: boolean
  /** Whether an unproved address is actually blocking this account right now.
   *  False while mail is unconfigured or sandboxed -- the page must not send
   *  someone to an inbox that will never receive anything. */
  verification_required: boolean
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
    // Bypasses request() -- see above -- so it needs its own timeout, or the
    // very first thing the app does can hang with no error and no dashboard.
    const controller = new AbortController()
    let timedOut = false
    const timer = setTimeout(() => { timedOut = true; controller.abort() }, TIMEOUT_MS)
    let res: Response
    try {
      res = await fetch(`${BASE}/auth/me`, {
        credentials: "same-origin", signal: controller.signal,
      })
    } catch (e) {
      if (timedOut) throw new TimeoutError(TIMEOUT_MS)
      if (!navigator.onLine) {
        throw new Error("You appear to be offline. Check your connection and try again.")
      }
      throw new Error(`Could not reach the server. ${(e as Error)?.message ?? ""}`.trim())
    } finally {
      clearTimeout(timer)
    }
    if (res.status === 401) return null
    if (!res.ok) throw new Error(`Could not check the session (${res.status}).`)
    return res.json() as Promise<Me>
  },

  async logout(): Promise<void> {
    await fetch(`${BASE}/auth/logout`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    }).catch(() => {
      /* the redirect below matters more than a failed POST */
    })
  },

  /** Mark the introduction as seen. Server-side, so it holds across devices. */
  finishOnboarding: () =>
    request<{ ok: boolean }>("/auth/onboarded", { method: "POST", body: "{}" }),

  /** Where the browser should go to download this account's data. */
  exportUrl: () => "/api/auth/export",

  /** Ask for another confirmation link. */
  resendVerification: () =>
    request<{ ok: boolean; detail?: string }>("/auth/resend-verification", {
      method: "POST", body: JSON.stringify({}),
    }),

  /**
   * Close the account for good.
   *
   * Takes no username: the server reads the identity from the session, so
   * there is no parameter that could aim this at somebody else.
   */
  closeAccount: (confirm: string, password: string) =>
    request<{ ok: boolean; backtests: number; trades: number }>("/auth/me", {
      method: "DELETE", body: JSON.stringify({ confirm, password }),
    }),
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  // Served since v1.0 and never shown to anyone. It is what turns
  // "it broke" into a report somebody can act on.
  version: () => request<{ version: string; api: string; commit: string }>("/version"),
  strategies: () => request<StrategyMeta[]>("/strategies"),
  dataSources: () => request<DataSourceMeta[]>("/data-sources"),
  contracts: () => request<Record<string, unknown>>("/contracts"),
  // Symbols the given data source can actually serve. For external_csv this
  // is derived from the files on disk, so the dropdown cannot offer a symbol
  // with no data behind it.
  symbols: (dataSource: string) =>
    request<SymbolMeta[]>(`/symbols?data_source=${encodeURIComponent(dataSource)}`),

  // Loading bars and running an engine legitimately takes minutes on a wide
  // date range, so this gets the long budget rather than the default 30s.
  runBacktest: (req: BacktestRequest) =>
    request<BacktestSummary>("/backtests", {
      method: "POST", body: JSON.stringify(req), timeoutMs: LONG_TIMEOUT_MS,
    }),
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
    request<ReplayCreateResponse>("/replay", {
      method: "POST", body: JSON.stringify(req), timeoutMs: LONG_TIMEOUT_MS,
    }),
  replayWsUrl: (id: string) => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:"
    return `${proto}//${window.location.host}${BASE}/replay/ws/${id}`
  },

  schwabStatus: () => request<SchwabStatus>("/schwab/status"),
  schwabAuthUrl: () => request<{ auth_url: string }>("/schwab/auth-url"),
  schwabCompleteAuth: (redirect_url: string) =>
    request<SchwabStatus>("/schwab/complete-auth", { method: "POST", body: JSON.stringify({ redirect_url }) }),

  // A sweep runs one backtest per combination; it is the slowest call here.
  // ── the account's own saved configurations ────────────────────────────────
  // Every one of these is scoped server-side by the session's user id; there is
  // no parameter here that names an account.
  listConfigs: () =>
    request<{ name: string; saved_at: string; config: Record<string, unknown> }[]>(
      "/account/configs"),
  saveConfig: (name: string, config: Record<string, unknown>) =>
    request<{ name: string; saved_at: string; config: Record<string, unknown> }>(
      `/account/configs/${encodeURIComponent(name)}`,
      { method: "PUT", body: JSON.stringify({ config }) }),
  deleteConfig: (name: string) =>
    request<{ ok: boolean }>(`/account/configs/${encodeURIComponent(name)}`,
      { method: "DELETE" }),

  runOptimizer: (req: OptimizeRequest) =>
    request<OptimizeResponse>("/optimize", {
      method: "POST", body: JSON.stringify(req), timeoutMs: LONG_TIMEOUT_MS,
    }),
}
