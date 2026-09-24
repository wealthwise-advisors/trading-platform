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
import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Activity, BarChart3, Bell, Plus, Star, Wallet, X } from "lucide-react"

import { api } from "@/lib/api"
import { useConfigStore } from "@/store/configStore"
import type { BacktestSummary, Quote } from "@/lib/types"
import { GOOD, CRITICAL } from "@/components/cards/StatCard"
import {
  loadAlerts, saveAlerts, alertTriggered, type PriceAlert,
} from "@/lib/priceAlerts"

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
      <header className="flex items-center gap-2 mb-1">
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
                <td className="py-[3px] font-semibold text-foreground"
                    title={r.contract ? `Quoting ${r.contract}` : undefined}>
                  {r.symbol}
                  <button type="button" onClick={() => remove(r.symbol)}
                          aria-label={`Remove ${r.symbol} from the watchlist`}
                          className="ml-1 opacity-0 group-hover:opacity-100 focus-visible:opacity-100
                                     text-muted-foreground/75 hover:text-foreground">
                    ×
                  </button>
                </td>
                <td className="py-[3px] text-right tabular-nums text-foreground">{price(r.last)}</td>
                <td className="py-[3px] text-right"><Delta value={r.change} /></td>
                <td className="py-[3px] text-right"><Delta value={r.change_pct} suffix="%" /></td>
              </tr>
            ))}
            {/* A symbol that returns no quote is dropped by the backend, so
                say which ones rather than leaving a silent gap in the list. */}
            {symbols.filter((sym) => !rows.some((r) => r.symbol === sym)).map((sym) => (
              <tr key={sym} className="group border-t border-[color:var(--hairline-soft)] text-muted-foreground/75">
                <td className="py-[3px] font-semibold">
                  {sym}
                  <button type="button" onClick={() => remove(sym)}
                          aria-label={`Remove ${sym} from the watchlist`}
                          className="ml-1 opacity-0 group-hover:opacity-100 focus-visible:opacity-100
                                     hover:text-foreground">
                    ×
                  </button>
                </td>
                <td colSpan={3} className="py-[3px] text-right text-[10.5px]">
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
            className={`rounded-md px-2 py-0.5 text-[11px] font-medium transition-colors ${
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
  // IN POINTS, as the reference shows this panel. avg_win_points and
  // avg_loss_points come from the trades' own entry and exit prices
  // (api/serializers.py::_avg_points), so nothing here divides a dollar figure
  // by a contract multiplier.
  //
  // A SIDE WITH NO TRADES HAS NO AVERAGE, and prints an em dash -- "0.0 pts"
  // would say the losing trades went nowhere rather than that there were none.
  //
  // Expectancy still works in that case, and exactly: it weights each side by
  // its share of the trades, and a side with no trades has a weight of zero,
  // so the missing average cannot affect the result. It is only unavailable
  // when a side that DID trade has no point figure -- which happens when its
  // trades are still open and have no exit price to measure.
  const wPts = s.avg_win_points
  const lPts = s.avg_loss_points
  const haveWin = wPts != null || s.winning_trades === 0
  const haveLoss = lPts != null || s.losing_trades === 0
  const expectancyPts = haveWin && haveLoss
    ? p * (wPts ?? 0) + (1 - p) * (lPts ?? 0)
    : null
  const pts = (n: number | null | undefined) =>
    n == null ? "—" : `${n > 0 ? "+" : ""}${n.toFixed(1)} pts`

  const rows: Array<[string, React.ReactNode]> = [
    ["Total Trades", s.total_trades.toLocaleString()],
    ["Winning Trades", <span style={{ color: GOOD }}>{s.winning_trades}</span>],
    ["Losing Trades", <span style={{ color: s.losing_trades ? CRITICAL : undefined }}>{s.losing_trades}</span>],
    ["Win Rate", `${s.win_rate.toFixed(0)}%`],
    // Moved here from the KPI row, which the reference has at six cards. The
    // pairing is the point -- "27%" alone does not say how much of the rest
    // was a loss rather than a scratch -- so it is kept as one line rather
    // than left to be inferred from the two counts above.
    ["Win % / Loss %",
      `${s.win_rate.toFixed(0)}% / ${(s.total_trades > 0 ? 100 - s.win_rate : 0).toFixed(0)}%`],
    // The dollar figure is on the hover of each, so nothing is lost: it is
    // what the exported report carries and what the P&L is actually in.
    ["Avg Win", <span style={{ color: s.winning_trades ? GOOD : undefined }}
                      title={`${money(s.avg_win)} across ${s.winning_trades} winning trade(s)`}>
                  {haveWin ? pts(wPts) : money(s.avg_win)}</span>],
    ["Avg Loss", <span style={{ color: s.losing_trades ? CRITICAL : undefined }}
                       title={`${money(s.avg_loss)} across ${s.losing_trades} losing trade(s)`}>
                   {haveLoss ? pts(lPts) : money(s.avg_loss)}</span>],
    ["Expectancy", <span style={{ color: (expectancyPts ?? expectancy) >= 0 ? GOOD : CRITICAL }}
                         title={`${money(expectancy)} per trade`}>
                     {expectancyPts == null ? money(expectancy) : pts(expectancyPts)}</span>],
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
          <li key={label} className="flex items-center justify-between gap-2 py-[3px] border-t border-[color:var(--hairline-soft)] first:border-t-0">
            <span className="text-muted-foreground">{label}</span>
            <span className="tabular-nums text-foreground">{value}</span>
          </li>
        ))}
      </ul>
    </Panel>
  )
}

/**
 * Account Summary — the capital the run was traded with, and where it ended.
 *
 * WHAT EACH LINE IS, because three of the four are easy to misread as broker
 * figures and they are not. This platform runs backtests and a paper session;
 * there is no funded account behind these numbers.
 *
 *   Account Balance   closed equity: starting capital plus realised P&L.
 *   Equity            balance plus open P&L. Identical to balance when
 *                     nothing is open, which is the normal end state.
 *   Available Funds   equity minus the margin the open positions tie up.
 *   Margin            initial margin of what is open, from the contract spec.
 *
 * Margin needs a per-contract requirement that lives in the contract spec,
 * which this panel is not given. So when something IS open, the two lines
 * that depend on it print an em dash rather than a guess -- an invented
 * margin figure would make Available Funds wrong in the one state where a
 * trader would actually act on it. With a flat book both are exact, and that
 * is the state the panel is in after almost every backtest.
 */
export function AccountSummaryPanel({ s, openPositions }: {
  s: BacktestSummary | null
  openPositions: number
}) {
  const money = (n: number) =>
    `${n < 0 ? "-" : ""}$${Math.abs(n).toLocaleString(undefined, {
      minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

  if (!s) {
    return (
      <Panel icon={<Wallet className="h-4 w-4" />} title="Account Summary">
        <p className="text-[11px] text-muted-foreground">Run a backtest to see the account it traded.</p>
      </Panel>
    )
  }

  const flat = openPositions === 0
  const balance = s.final_capital
  const pnl = s.total_pnl

  const rows: Array<[string, React.ReactNode]> = [
    ["Account Balance", money(balance)],
    ["Realized P&L",
      <span style={{ color: pnl === 0 ? undefined : pnl > 0 ? GOOD : CRITICAL }}>
        {`${pnl >= 0 ? "+" : "-"}$${Math.abs(pnl).toLocaleString(undefined, {
          minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
      </span>],
    // Flat book: equity IS the balance, exactly. Open book: the open P&L is
    // in points on the Positions panel and needs the multiplier to become
    // dollars, which this panel does not have.
    ["Equity", flat ? money(balance)
      : <span title="A position is open. Its P&L is in points on the Positions panel; converting it to dollars needs the contract multiplier.">—</span>],
    ["Available Funds", flat ? money(balance)
      : <span title="Depends on the margin tied up by the open position.">—</span>],
    ["Margin", flat ? money(0)
      : <span title="Initial margin comes from the contract spec, which this panel is not given.">—</span>],
  ]

  return (
    <Panel
      icon={<Wallet className="h-4 w-4" />}
      title="Account Summary"
      action={
        <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground"
              title={flat
                ? "Flat — no open positions. These are closed-run figures, not a broker account."
                : `${openPositions} open position(s) carried to the end of the run.`}>
          <span className="h-1.5 w-1.5 rounded-full"
                style={{ background: flat ? "var(--muted-foreground, #7a8699)" : GOOD }} aria-hidden />
          {flat ? "Flat" : "Open"}
        </span>
      }
    >
      <ul className="text-[11.5px]">
        {rows.map(([label, value]) => (
          <li key={label} className="flex items-center justify-between gap-2 py-[3px] border-t border-[color:var(--hairline-soft)] first:border-t-0">
            <span className="text-muted-foreground">{label}</span>
            <span className="tabular-nums text-foreground">{value}</span>
          </li>
        ))}
      </ul>
      <p className="mt-1.5 text-[10px] text-muted-foreground/80">
        Backtest capital, not a funded account.
      </p>
    </Panel>
  )
}

/**
 * Alerts — the price levels the user has marked, and whether the bars on
 * screen have reached them.
 *
 * WHAT "TRIGGERED" MEANS HERE, because the word promises more than this can
 * deliver. Nothing watches the market while the app is closed: there is no
 * server-side feed subscription and no push channel to reach the user
 * through. So an alert is checked against the bars currently loaded, high and
 * low rather than close, and the panel reports "Reached" or "Waiting" for
 * that range only. With no bars loaded it says so instead of showing a tick,
 * because "not reached" and "nothing to check against" are different answers.
 */
export function AlertsPanel({ bars }: { bars: Array<{ h: number; l: number }> }) {
  const [alerts, setAlerts] = useState<PriceAlert[]>(loadAlerts)
  const activeSymbol = useConfigStore((s) => s.symbol)

  // Another tab adding an alert should show up here rather than being
  // clobbered by this tab's stale copy.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === "price-alerts") setAlerts(loadAlerts())
    }
    window.addEventListener("storage", onStorage)
    return () => window.removeEventListener("storage", onStorage)
  }, [])

  const remove = (id: string) => {
    const next = alerts.filter((a) => a.id !== id)
    setAlerts(next)
    saveAlerts(next)
  }

  // NOTHING AT ALL WHEN THERE ARE NO ALERTS.
  //
  // The rail is four panels in the reference -- Watchlist, Market Summary,
  // Trade Statistics, Account Summary -- and a fifth showing only the sentence
  // "no alerts yet" earns none of that height. It also had a real cost: five
  // stacked panels ran the rail past the fold, and e2e/layering.spec.ts failed
  // on Linux (taller fonts) while passing here. An empty panel is not worth a
  // regression guard.
  //
  // The entry point is not lost: the header bell says how many alerts are set
  // and the chart toolbar's Alert button is where one is made. The panel
  // appears the moment there is something to put in it.
  if (!alerts.length) return null

  return (
    <div data-panel="alerts">
    <Panel icon={<Bell className="h-4 w-4" />} title="Alerts">
      <ul className="text-[11.5px]">
        {alerts.map((a) => {
          // Only judge an alert against bars that belong to it. A level set on
          // NQ cannot be answered by the ES bars on screen, and saying
          // "Waiting" would imply it had been checked.
          const sameInstrument = !activeSymbol || a.symbol === activeSymbol
          const hit = sameInstrument ? alertTriggered(a, bars) : null
          const state = !sameInstrument ? { text: "Other symbol", color: undefined }
            : hit == null ? { text: "No bars", color: undefined }
            : hit ? { text: "Reached", color: GOOD }
            : { text: "Waiting", color: undefined }
          return (
            <li key={a.id}
                className="flex items-center gap-2 py-[3px] border-t border-[color:var(--hairline-soft)] first:border-t-0">
              <span className="text-foreground font-medium">{a.symbol}</span>
              <span className="text-muted-foreground">{a.direction === "above" ? "≥" : "≤"}</span>
              <span className="tabular-nums text-foreground">{a.price.toFixed(2)}</span>
              <span className="ml-auto tabular-nums" style={{ color: state.color }}>{state.text}</span>
              <button type="button" onClick={() => remove(a.id)}
                      aria-label={`Remove alert on ${a.symbol} at ${a.price}`}
                      title="Remove this alert"
                      className="text-muted-foreground hover:text-foreground">
                <X className="h-3 w-3" aria-hidden />
              </button>
            </li>
          )
        })}
      </ul>
      <p className="mt-1.5 text-[10px] text-muted-foreground/80">
        Checked against the bars on screen. Nothing watches the market while this is closed.
      </p>
    </Panel>
    </div>
  )
}

/**
 * The header bell: how many price alerts are set.
 *
 * The badge is a COUNT, not an unread indicator. Nothing watches the market
 * while the app is closed -- see priceAlerts.ts -- so there is no category of
 * "alert that fired and you have not seen". Claiming otherwise with a red dot
 * would be the badge lying about what the app can do.
 */
export function AlertsBell() {
  const [count, setCount] = useState(() => loadAlerts().length)

  useEffect(() => {
    const refresh = () => setCount(loadAlerts().length)
    window.addEventListener("storage", refresh)
    // The chart writes alerts in this same tab, where `storage` does not fire.
    window.addEventListener("alerts-changed", refresh)
    return () => {
      window.removeEventListener("storage", refresh)
      window.removeEventListener("alerts-changed", refresh)
    }
  }, [])

  return (
    <button
      type="button"
      className="relative inline-flex h-8 items-center rounded-md px-2 text-muted-foreground
                 hover:bg-[color:var(--raise-3)] hover:text-foreground"
      title={count ? `${count} price alert${count === 1 ? "" : "s"} set` : "No price alerts set"}
      onClick={() => {
        document.querySelector("[data-panel='alerts']")?.scrollIntoView({
          behavior: "smooth", block: "center",
        })
      }}
    >
      <Bell className="h-4 w-4" aria-hidden />
      {count > 0 && (
        <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center
                         rounded-full bg-[#2563eb] px-1 text-[9px] font-semibold text-white">
          {count}
        </span>
      )}
      <span className="sr-only">
        {count ? `${count} price alerts set` : "No price alerts set"}
      </span>
    </button>
  )
}
