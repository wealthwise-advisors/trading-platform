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
  /** Ignore the session window entirely and keep every bar. Correct
   *  for anything that trades continuously, and the only way to see
   *  pre/post-market activity. */
  session24h: boolean
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

// ZigZag deviation slider bounds, in PERCENT (the value shown on the slider).
// ConfigForm divides by 100 before sending, and src/analysis/zigzag.py converts
// that fraction back to the percentage pandas_ta expects.
//
// Chosen from a measured sweep on ES 5m, 424 bars, ~35pt session range:
//
//     dev_10   pts   major swings          dev_3   pts   pivots/major swing
//      0.02%  1.56             18           0.02%  1.56               10.5
//      0.05%  3.89             15           0.05%  3.89                4.5
//      0.10%  7.78             10           0.10%  7.78                1.8
//      0.30% 23.35              1           0.15% 11.67                1.3
//
// The minor (3-leg) zigzag nests inside each major swing, so its default is
// deliberately finer than the major one -- they used to share a value, which
// left the minor zigzag unable to resolve substructure.
export const ZIGZAG_DEV_MIN = 0.01
export const ZIGZAG_DEV_MAX = 2
export const ZIGZAG_DEV_STEP = 0.01
export const ZIGZAG_DEV_3_DEFAULT = 0.05
export const ZIGZAG_DEV_10_DEFAULT = 0.1

// Saved configs written before the units fix carry 0.3 for both sliders, which
// was the old default and meant 0.003% in practice. Read literally now it is a
// 23pt threshold that collapses an intraday chart to one or two swings. Only
// the exact untouched-default pair is migrated; a value the user actually
// chose is left alone.
const LEGACY_DEV_DEFAULT = 0.3

export function migrateZigzagDefaults<T extends { zigzagDev3: number; zigzagDev10: number }>(
  snapshot: T,
): T {
  if (snapshot.zigzagDev3 === LEGACY_DEV_DEFAULT && snapshot.zigzagDev10 === LEGACY_DEV_DEFAULT) {
    return { ...snapshot, zigzagDev3: ZIGZAG_DEV_3_DEFAULT, zigzagDev10: ZIGZAG_DEV_10_DEFAULT }
  }
  return snapshot
}

export const CONFIG_SNAPSHOT_KEYS = [
  "dataSource", "symbol", "timeframe", "strategyId", "params", "initialCapital",
  "contractsPerTrade", "commission", "startDate", "endDate", "sessionStart",
  "sessionEnd", "session24h", "zigzagDev3", "zigzagDev10",
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
  session24h: false,
  zigzagDev3: ZIGZAG_DEV_3_DEFAULT,
  zigzagDev10: ZIGZAG_DEV_10_DEFAULT,

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
  loadSnapshot: (snapshot) => set(migrateZigzagDefaults(snapshot)),
}))
