// UI/config state that mirrors what ui/app.py kept in st.session_state's
// sidebar widgets. Server-derived data (backtest results) is NOT here — that
// lives in TanStack Query, keyed off `backtestId`.

import { create } from "zustand"

interface ConfigState {
  dataSource: string
  symbol: string
  timeframe: string
  strategyId: string
  params: Record<string, number>
  initialCapital: number
  contractsPerTrade: number
  commission: number
  startDate: string
  endDate: string
  sessionStart: string
  sessionEnd: string
  zigzagDev3: number
  zigzagDev10: number

  backtestId: string | null
  lastRunAt: string | null
  page: "backtest" | "replay" | "export"

  setField: <K extends keyof ConfigState>(key: K, value: ConfigState[K]) => void
  setParam: (name: string, value: number) => void
  setParams: (params: Record<string, number>) => void
  setBacktestId: (id: string | null) => void
  setPage: (page: "backtest" | "replay" | "export") => void
  setLastRunAt: (iso: string | null) => void
  getSnapshot: () => ConfigSnapshot
  loadSnapshot: (snapshot: ConfigSnapshot) => void
}

export const CONFIG_SNAPSHOT_KEYS = [
  "dataSource", "symbol", "timeframe", "strategyId", "params", "initialCapital",
  "contractsPerTrade", "commission", "startDate", "endDate", "sessionStart",
  "sessionEnd", "zigzagDev3", "zigzagDev10",
] as const

export type ConfigSnapshot = Pick<ConfigState, typeof CONFIG_SNAPSHOT_KEYS[number]>

function defaultDateRange() {
  const today = new Date()
  const day = today.getDay()
  // Roll back to the last trading day (skip Sat/Sun) — mirrors _last_trading_day in ui/app.py
  const back = day === 0 ? 2 : day === 6 ? 1 : 1
  const d = new Date(today)
  d.setDate(d.getDate() - back)
  const iso = d.toISOString().slice(0, 10)
  return { start: iso, end: iso }
}

const { start, end } = defaultDateRange()

export const useConfigStore = create<ConfigState>((set, get) => ({
  dataSource: "synthetic",
  symbol: "ES",
  timeframe: "5m",
  strategyId: "rsi_divergence",
  params: { rsi_overbought: 94, rsi_oversold: 2, swing_lookback: 5 },
  initialCapital: 100_000,
  contractsPerTrade: 1,
  commission: 2.5,
  startDate: start,
  endDate: end,
  sessionStart: "09:30",
  sessionEnd: "16:00",
  zigzagDev3: 0.3,
  zigzagDev10: 0.3,

  backtestId: null,
  lastRunAt: null,
  page: "backtest",

  setField: (key, value) => set({ [key]: value } as Pick<ConfigState, typeof key>),
  setParam: (name, value) => set((s) => ({ params: { ...s.params, [name]: value } })),
  setParams: (params) => set({ params }),
  setBacktestId: (id) => set({ backtestId: id }),
  setPage: (page) => set({ page }),
  setLastRunAt: (iso) => set({ lastRunAt: iso }),
  getSnapshot: () => {
    const s = get()
    return Object.fromEntries(CONFIG_SNAPSHOT_KEYS.map((k) => [k, s[k]])) as ConfigSnapshot
  },
  loadSnapshot: (snapshot) => set(snapshot),
}))
