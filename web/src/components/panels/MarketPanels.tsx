/**
 * The right rail: Watchlist, Market Summary, Trade Statistics.
 *
 * WHERE THE NUMBERS COME FROM, AND WHAT HAPPENS WHEN THEY DO NOT.
 * Watchlist and Market Summary are live Schwab quotes. Schwab needs a 7-day
 * login the user performs themselves, so "no data" is a normal state, not an
 * error — and the panels say "connect Schwab" rather than showing 0.00. A
 * zero on a price panel is indistinguishable from a market that has crashed,
 * and an invented number is worse than a blank.
 *
 * Trade Statistics needs no feed at all: every line is a field of the summary
 * the backtest already returned, so it is exact whenever a result exists.
 */
import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Activity, BarChart3, Plus, Star } from "lucide-react"

import { api } from "@/lib/api"
import { useConfigStore } from "@/store/configStore"
import type { BacktestSummary, Quote } from "@/lib/types"
import { GOOD, CRITICAL } from "@/components/cards/StatCard"

/** The futures roots the platform trades. The backend maps them to Schwab. */
const WATCHLIST = ["ES", "NQ", "YM", "RTY", "CL", "GC"]

/** Added symbols survive a reload, per browser, like the interval favourites.
 *  A watchlist you have to rebuild every morning is not a watchlist. */
const WATCHLIST_KEY = "watchlist-symbols"

function loadWatchlist(): string[] {
  try {
    const raw = JSON.parse(localStorage.getItem(WATCHLIST_KEY) ?? "null")
    return Array.isArray(raw) && raw.every((s) => typeof s === "string") ? raw : WATCHLIST
  } catch {
    return WATCHLIST
  }
}

function saveWatchlist(list: string[]) {
  try {
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(list))
  } catch {
    /* private window or blocked storage: the list still works for this session */
  }
}

/** The four tabs of the Market Summary, each a real symbol set.
 *
 *  Forex and crypto are asked for exactly as Schwab spells them. If the
 *  account is not entitled to a set, those symbols simply return no quote and
 *  the tab says so — which is the truth, and better than hiding a tab that
 *  another account would be able to use. */
const SUMMARY_TABS = [
  {
    id: "indices", label: "Indices", rows: [
      { symbol: "$SPX", label: "S&P 500" },
      { symbol: "$NDX", label: "NASDAQ 100" },
      { symbol: "$DJI", label: "DOW JONES" },
      { symbol: "$VIX", label: "VIX" },
    ],
  },
  {
    id: "futures", label: "Futures", rows: [
      { symbol: "ES", label: "E-mini S&P" },
      { symbol: "NQ", label: "E-mini Nasdaq" },
      { symbol: "CL", label: "Crude Oil" },
      { symbol: "GC", label: "Gold" },
    ],
  },
  {
    id: "forex", label: "Forex", rows: [
      { symbol: "EUR/USD", label: "EUR / USD" },
      { symbol: "GBP/USD", label: "GBP / USD" },
      { symbol: "USD/JPY", label: "USD / JPY" },
      { symbol: "AUD/USD", label: "AUD / USD" },
    ],
  },
  {
    id: "crypto", label: "Crypto", rows: [
      { symbol: "BTC/USD", label: "Bitcoin" },
      { symbol: "ETH/USD", label: "Ethereum" },
    ],
  },
] as const

/** Quotes go stale; 15s is the same cadence the live tape polls at. */
const REFRESH_MS = 15_000

function Panel({ icon, title, action, children }: {
  icon: React.ReactNode
  title: string
  action?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <section className="rail-card">
      <header className="flex items-center gap-2 mb-2">
        <span className="text-[#38bdf8]" aria-hidden>{icon}</span>
        <h2 className="text-[13px] font-semibold text-foreground">{title}</h2>
        {action && <span className="ml-auto">{action}</span>}
      </header>
      {children}
    </section>
  )
}

/**
 * A price, to the precision the number actually needs.
 *
 * Two decimals everywhere printed EUR/USD as "1.15", which throws away the
 * digits a currency pair is quoted in — the whole day's range lives in the
 * fourth decimal. Anything under 10 gets four; an index or a future gets two,
 * so 7,666.50 still reads as a price beside 7,551.81 rather than as 7,666.5.
 */
const price = (n: number) => {
  const d = Math.abs(n) < 10 ? 4 : 2
  return n.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d })
}

/** A signed number, coloured only when it is actually non-zero: painting a
 *  flat market green says something happened that did not. */
function Delta({ value, suffix = "", digits = 2 }: { value: number; suffix?: string; digits?: number }) {
  const colour = value > 0 ? GOOD : value < 0 ? CRITICAL : undefined
  const sign = value > 0 ? "+" : ""
  return (
    <span className="tabular-nums" style={colour ? { color: colour } : undefined}>
      {sign}{value.toFixed(digits)}{suffix}
    </span>
  )
}

function Disconnected({ reason }: { reason?: string | null }) {
  return (
    <p className="text-[11px] leading-relaxed text-muted-foreground">
      {reason || "No live quote source connected."}
    </p>
  )
}

function useQuotes(symbols: string[], key: string) {
  return useQuery({
    queryKey: ["quotes", key],
    queryFn: () => api.quotes(symbols),
    refetchInterval: REFRESH_MS,
    // A quote failing must never blank the panel that already has prices.
    placeholderData: (prev) => prev,
  })
}

export function WatchlistPanel() {
  // The instrument the backtest is configured for, highlighted in the list —
  // the reference marks the active row, and it answers "which of these am I
  // actually testing" without reading the sidebar.
  const activeSymbol = useConfigStore((s) => s.symbol)
  const [symbols, setSymbols] = useState<string[]>(loadWatchlist)
  const [adding, setAdding] = useState(false)
  const [draft, setDraft] = useState("")
  const q = useQuotes(symbols, `watchlist:${symbols.join(",")}`)
  const rows: Quote[] = q.data?.quotes ?? []

  const add = () => {
    const sym = draft.trim().toUpperCase()
    if (!sym || symbols.includes(sym)) { setAdding(false); setDraft(""); return }
    const next = [...symbols, sym]
    setSymbols(next)
    saveWatchlist(next)
    setAdding(false)
    setDraft("")
  }

  const remove = (sym: string) => {
    const next = symbols.filter((s) => s !== sym)
    setSymbols(next)
    saveWatchlist(next)
  }

  return (
    <Panel
      icon={<Star className="h-4 w-4" />}
      title="Watchlist"
      action={
        <button type="button" onClick={() => setAdding((v) => !v)}
                className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px]
                           text-muted-foreground hover:text-foreground hover:bg-[color:var(--raise-3)]"
                aria-expanded={adding} aria-label="Add a symbol to the watchlist">
          <Plus className="h-3 w-3" aria-hidden /> Add
        </button>
      }
    >
      {adding && (
        <form className="flex gap-1 mb-2"
              onSubmit={(e) => { e.preventDefault(); add() }}>
          <input
            autoFocus value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder="ES, NQ, AAPL…" aria-label="Symbol to add"
            className="min-w-0 flex-1 rounded-md border border-[color:var(--hairline-mid)] bg-[color:var(--raise-1)]
                       px-2 py-1 text-[11.5px] outline-none focus:border-[color:var(--hairline-focus)]"
          />
          <button type="submit"
                  className="rounded-md border border-[color:var(--hairline-mid)] px-2 py-1 text-[11px]
                             text-foreground hover:bg-[color:var(--raise-3)]">
            Add
          </button>
        </form>
      )}
      {q.data && !q.data.connected ? (
        <Disconnected reason={q.data.reason} />
      ) : (
        <table className="w-full text-[11.5px]">
          <thead>
            <tr className="text-muted-foreground/75">
              <th className="text-left font-medium pb-1">Symbol</th>
              <th className="text-right font-medium pb-1">Last</th>
              <th className="text-right font-medium pb-1">Chg</th>
              <th className="text-right font-medium pb-1">Chg%</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.symbol}
                  aria-current={r.symbol === activeSymbol ? "true" : undefined}
                  className={`group border-t border-[color:var(--hairline-soft)] ${
                    r.symbol === activeSymbol ? "bg-sky-500/10" : ""}`}>
                <td className="py-1.5 font-semibold text-foreground"
                    title={r.contract ? `Quoting ${r.contract}` : undefined}>
                  {r.symbol}
                  <button type="button" onClick={() => remove(r.symbol)}
                          aria-label={`Remove ${r.symbol} from the watchlist`}
                          className="ml-1 opacity-0 group-hover:opacity-100 focus-visible:opacity-100
                                     text-muted-foreground/75 hover:text-foreground">
                    ×
                  </button>
                </td>
                <td className="py-1.5 text-right tabular-nums text-foreground">{price(r.last)}</td>
                <td className="py-1.5 text-right"><Delta value={r.change} /></td>
                <td className="py-1.5 text-right"><Delta value={r.change_pct} suffix="%" /></td>
              </tr>
            ))}
            {/* A symbol that returns no quote is dropped by the backend, so
                say which ones rather than leaving a silent gap in the list. */}
            {symbols.filter((sym) => !rows.some((r) => r.symbol === sym)).map((sym) => (
              <tr key={sym} className="group border-t border-[color:var(--hairline-soft)] text-muted-foreground/75">
                <td className="py-1.5 font-semibold">
                  {sym}
                  <button type="button" onClick={() => remove(sym)}
                          aria-label={`Remove ${sym} from the watchlist`}
                          className="ml-1 opacity-0 group-hover:opacity-100 focus-visible:opacity-100
                                     hover:text-foreground">
                    ×
                  </button>
                </td>
                <td colSpan={3} className="py-1.5 text-right text-[10.5px]">
                  {q.isLoading ? "loading…" : "no quote"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  )
}

export function MarketSummaryPanel() {
  const [tab, setTab] = useState<string>(SUMMARY_TABS[0].id)
  const active = SUMMARY_TABS.find((t) => t.id === tab) ?? SUMMARY_TABS[0]
  const q = useQuotes(active.rows.map((r) => r.symbol), `summary:${active.id}`)
  const by = new Map((q.data?.quotes ?? []).map((r) => [r.symbol, r]))
  const nothing = q.data?.connected && q.data.quotes.length === 0

  return (
    <Panel icon={<BarChart3 className="h-4 w-4" />} title="Market Summary">
      <div role="tablist" aria-label="Market summary" className="flex gap-1 mb-2">
        {SUMMARY_TABS.map((t) => (
          <button
            key={t.id} type="button" role="tab" aria-selected={t.id === tab}
            onClick={() => setTab(t.id)}
            className={`rounded-md px-2 py-1 text-[11px] font-medium transition-colors ${
              t.id === tab
                ? "bg-[#1d4ed8]/25 text-sky-800 dark:text-sky-200 ring-1 ring-sky-400/30"
                : "text-muted-foreground hover:text-foreground hover:bg-[color:var(--raise-3)]"}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {q.data && !q.data.connected ? (
        <Disconnected reason={q.data.reason} />
      ) : nothing ? (
        // Connected, asked, and Schwab returned nothing for this set. Usually
        // an entitlement: say that rather than showing four dashes forever.
        <p className="text-[11px] text-muted-foreground">
          No {active.label.toLowerCase()} quotes available on this Schwab account.
        </p>
      ) : (
        <ul className="text-[11.5px]">
          {active.rows.map(({ symbol, label }) => {
            const r = by.get(symbol)
            return (
              <li key={symbol} className="flex items-center justify-between gap-2 py-1.5 border-t border-[color:var(--hairline-soft)] first:border-t-0">
                <span className="text-foreground">{label}</span>
                <span className="flex items-center gap-3">
                  <span className="tabular-nums text-foreground">{r ? price(r.last) : "—"}</span>
                  {r ? <Delta value={r.change_pct} suffix="%" /> : <span className="text-muted-foreground/75">—</span>}
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </Panel>
  )
}

/** Every row is a field of the summary — nothing here is derived twice. */
export function TradeStatsPanel({ s }: { s: BacktestSummary | null }) {
  const money = (n: number) =>
    `${n < 0 ? "-" : ""}$${Math.abs(n).toLocaleString(undefined, {
      minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

  if (!s) {
    return (
      <Panel icon={<Activity className="h-4 w-4" />} title="Trade Statistics">
        <p className="text-[11px] text-muted-foreground">Run a backtest to see its trade statistics.</p>
      </Panel>
    )
  }

  // Expectancy: what one trade is worth on average, from the win rate and the
  // two averages the engine already reports. Shown because a profit factor
  // above 1 with a tiny edge per trade is a different business from the same
  // factor earned in size.
  const p = s.win_rate / 100
  const expectancy = p * s.avg_win + (1 - p) * s.avg_loss

  const rows: Array<[string, React.ReactNode]> = [
    ["Total Trades", s.total_trades.toLocaleString()],
    ["Winning Trades", <span style={{ color: GOOD }}>{s.winning_trades}</span>],
    ["Losing Trades", <span style={{ color: s.losing_trades ? CRITICAL : undefined }}>{s.losing_trades}</span>],
    ["Win Rate", `${s.win_rate.toFixed(0)}%`],
    ["Avg Win", <span style={{ color: s.winning_trades ? GOOD : undefined }}>{money(s.avg_win)}</span>],
    ["Avg Loss", <span style={{ color: s.losing_trades ? CRITICAL : undefined }}>{money(s.avg_loss)}</span>],
    ["Expectancy", <span style={{ color: expectancy >= 0 ? GOOD : CRITICAL }}>{money(expectancy)}</span>],
    // null means "no finite ratio"; the counts say whether that was unbounded
    // (winners, no losers) or undefined (nothing won and nothing lost).
    ["Profit Factor", s.profit_factor == null
      ? (s.winning_trades > 0 ? <span style={{ color: GOOD }}>∞</span> : "—")
      : s.profit_factor.toFixed(2)],
    ["Max Drawdown", <span style={{ color: CRITICAL }}>{s.max_drawdown_pct.toFixed(1)}%</span>],
  ]

  return (
    <Panel icon={<Activity className="h-4 w-4" />} title="Trade Statistics">
      <ul className="text-[11.5px]">
        {rows.map(([label, value]) => (
          <li key={label} className="flex items-center justify-between gap-2 py-1 border-t border-[color:var(--hairline-soft)] first:border-t-0">
            <span className="text-muted-foreground">{label}</span>
            <span className="tabular-nums text-foreground">{value}</span>
          </li>
        ))}
      </ul>
    </Panel>
  )
}
