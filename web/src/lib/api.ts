// Typed fetch client for the FastAPI backend. Always calls relative /api/...
// paths — Vite's dev server proxies these to uvicorn (see vite.config.ts);
// in production the same relative paths work if FastAPI serves the built
// frontend directly.

import type {
  StrategyMeta, DataSourceMeta, BacktestRequest, BacktestSummary,
  TradeRecord, PriceDataResponse, EquityPoint, ZigZagResponse, WinLoss,
  CandlestickPatternRecord, ChartPatternRecord, MonthlyReturns,
  ReplayCreateRequest, ReplayCreateResponse, SchwabStatus,
} from "./types"

const BASE = "/api"

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => "")
    throw new Error(`${res.status} ${res.statusText}: ${body}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  strategies: () => request<StrategyMeta[]>("/strategies"),
  dataSources: () => request<DataSourceMeta[]>("/data-sources"),
  contracts: () => request<Record<string, unknown>>("/contracts"),

  runBacktest: (req: BacktestRequest) =>
    request<BacktestSummary>("/backtests", { method: "POST", body: JSON.stringify(req) }),
  getBacktest: (id: string) => request<BacktestSummary>(`/backtests/${id}`),
  getTrades: (id: string) => request<TradeRecord[]>(`/backtests/${id}/trades`),
  getPriceData: (id: string) => request<PriceDataResponse>(`/backtests/${id}/price-data`),
  getEquityCurve: (id: string) => request<EquityPoint[]>(`/backtests/${id}/equity-curve`),
  getZigZag: (id: string, dev3: number, dev10: number) =>
    request<ZigZagResponse>(`/backtests/${id}/zigzag?dev_3=${dev3}&dev_10=${dev10}`),
  getWinLoss: (id: string) => request<WinLoss>(`/backtests/${id}/win-loss`),
  getCandlestickPatterns: (id: string, minConfidence = 70) =>
    request<CandlestickPatternRecord[]>(`/backtests/${id}/candlestick-patterns?min_confidence=${minConfidence}`),
  getChartPatterns: (id: string) =>
    request<ChartPatternRecord[]>(`/backtests/${id}/chart-patterns`),
  getMonthlyReturns: (id: string) =>
    request<MonthlyReturns>(`/backtests/${id}/monthly-returns`),
  reportUrl: (id: string) => `${BASE}/backtests/${id}/report`,

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
}
