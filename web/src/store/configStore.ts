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
  /** Which results tab is showing. Lifted out of the Tabs component so a
   *  header link can open the view it names -- "Strategy Lab" that lands on
   *  the page but not the optimiser has not taken you anywhere. */
  resultsTab: string

  setField: <K extends keyof ConfigState>(key: K, value: ConfigState[K]) => void
  setParam: (name: string, value: number) => void
  setParams: (params: Record<string, number>) => void
  setBacktestId: (id: string | null) => void
  setPage: (page: "backtest" | "replay" | "export") => void
  setResultsTab: (tab: string) => void
  /** Go to a page and, on the results page, a specific tab in one step. */
  /** The header section last chosen, so the lit pill reflects intent.
   *  Null means "nothing chosen yet, derive it from the page and tab". */
  navSection: string | null
  goTo: (page: "backtest" | "replay" | "export", tab?: string, section?: string) => void
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

/** A local date as YYYY-MM-DD.
 *
 *  NOT toISOString(), which formats in UTC. `new Date()` is local, so mixing
 *  the two shifts the answer by a day for anyone whose offset pushes the
 *  current local time onto a different UTC date -- every morning before 05:30
 *  in IST, for instance, which is where this app is used. */
function localISODate(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/**
 * The last completed trading day.
 *
 * MONDAY IS THE CASE THIS GOT WRONG. The old table rolled back one day for
 * everything except Sunday, so a Monday landed on SUNDAY -- a day the
 * regular session does not exist. The run then fetched the Sunday-evening
 * futures reopen (18:00 onwards) and the 09:30-16:00 session filter removed
 * every bar, which surfaced as "No bars remain after applying the session
 * filter" on the first run of the week.
 *
 * Sat and Sun roll back to Friday as before; Monday now rolls back three days
 * to Friday too. Tue-Fri still take the previous weekday.
 *
 * Holidays are NOT handled -- this is the previous weekday, not an exchange
 * calendar. A run on the day after a holiday can still land on a closed
 * session, and the error message names the date and the window so it is
 * obvious when that happens.
 */
export function defaultDateRange(now: Date = new Date()) {
  const today = now
  const day = today.getDay()          // 0 = Sunday ... 6 = Saturday
  const back = day === 0 ? 2 : day === 1 ? 3 : 1
  const d = new Date(today)
  d.setDate(d.getDate() - back)
  const iso = localISODate(d)
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
  resultsTab: "price",

  setField: (key, value) => set({ [key]: value } as Pick<ConfigState, typeof key>),
  setParam: (name, value) => set((s) => ({ params: { ...s.params, [name]: value } })),
  setParams: (params) => set({ params }),
  setBacktestId: (id) => set({ backtestId: id }),
  setPage: (page) => set({ page }),
  setResultsTab: (resultsTab) => set({ resultsTab }),
  navSection: null,
  goTo: (page, tab, section) =>
    set(tab ? { page, resultsTab: tab, navSection: section ?? null }
            : { page, navSection: section ?? null }),
  setLastRunAt: (iso) => set({ lastRunAt: iso }),
  getSnapshot: () => {
    const s = get()
    return Object.fromEntries(CONFIG_SNAPSHOT_KEYS.map((k) => [k, s[k]])) as ConfigSnapshot
  },
  loadSnapshot: (snapshot) => set(migrateZigzagDefaults(snapshot)),
}))
