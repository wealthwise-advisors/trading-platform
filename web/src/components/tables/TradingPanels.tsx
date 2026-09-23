/**
 * The bottom rail of the TradingView-style workspace: Positions, Orders,
 * Order History, Balance History and the Trading Journal.
 *
 * WHERE THE NUMBERS COME FROM.
 * Every figure on these five panels is derived from data the backtest already
 * returned -- the trade list and the equity curve. Nothing here invents a
 * fill, a balance or a quote, and nothing calls a broker. That matters most
 * on Positions: a row there is an OPEN trade (`exit_time === null`), marked
 * against the last price the chart itself was drawn from, so the unrealised
 * P&L on screen is the same number the engine would settle at that price.
 *
 * WHAT THIS DELIBERATELY DOES NOT DO.
 * The reference shows Stop Loss, Take Profit and a Close button on each
 * position. Those are ORDER ENTRY, and this platform is strategy-driven --
 * the strategy decides entries and exits, and there is no broker route behind
 * a Close button. Rather than paint controls that would lie when clicked,
 * the stop/target columns show what the trade actually carries and the
 * actions column says where the exit comes from. See README in this folder.
 */
import { useCallback, useEffect, useState } from "react"
import { ClipboardList, Inbox } from "lucide-react"

import type { EquityPoint, TradeRecord } from "@/lib/types"

/* ── shared formatting ─────────────────────────────────────────────────── */

const GAIN = "text-green-900 dark:text-green-400"
const LOSS = "text-red-900 dark:text-red-400"

function fmtTime(iso: string | null) {
  if (!iso) return "—"
  return iso.replace("T", " ").slice(0, 16)
}

function money(n: number, dp = 2) {
  return `${n < 0 ? "-" : ""}$${Math.abs(n).toLocaleString(undefined, {
    minimumFractionDigits: dp, maximumFractionDigits: dp,
  })}`
}

function signedMoney(n: number, dp = 2) {
  return `${n >= 0 ? "+" : "-"}$${Math.abs(n).toLocaleString(undefined, {
    minimumFractionDigits: dp, maximumFractionDigits: dp,
  })}`
}

/** An empty panel says which action fills it. A bare "no data" leaves the
 *  reader unable to tell a quiet market from a broken feed. */
function Empty({ icon, children }: { icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <p className="text-muted-foreground p-4 text-sm flex items-center gap-2">
      {icon && <span className="opacity-60" aria-hidden>{icon}</span>}
      {children}
    </p>
  )
}

/** One table shell, so all five panels line up to the pixel. */
function Grid({ head, children }: { head: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-[color:var(--hairline-soft)]">
      <table className="w-full text-sm">
        <thead className="bg-[var(--surface-2)] text-muted-foreground">
          <tr>{head}</tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

const TH = "text-left p-2 font-medium"
const THR = "text-right p-2 font-medium"

/* ── Positions ─────────────────────────────────────────────────────────── */

/**
 * Open trades, marked to `lastPrice`.
 *
 * `lastPrice` is the close of the final bar the chart drew. When it is absent
 * (price data still loading) the mark-to-market columns print an em dash
 * rather than falling back to the entry price -- which would render every
 * open position at exactly break-even and read as fact.
 */
export function PositionsTable({ trades, lastPrice, symbol }: {
  trades: TradeRecord[]
  lastPrice: number | null
  symbol: string
}) {
  const open = trades.filter((t) => t.exit_time == null)

  if (!open.length) {
    return <Empty icon={<Inbox className="h-4 w-4" />}>
      No open positions — every trade in this run was closed before the period ended.
    </Empty>
  }

  return (
    <Grid head={<>
      <th className={TH}>Symbol</th>
      <th className={TH}>Side</th>
      <th className={THR}>Qty</th>
      <th className={THR}>Avg Price</th>
      <th className={THR}>Last Price</th>
      <th className={THR}>Unrealized P&amp;L</th>
      <th className={THR}>P&amp;L %</th>
      <th className={THR}>Stop Loss</th>
      <th className={THR}>Take Profit</th>
      <th className={TH}>Opened</th>
      <th className={TH}>Actions</th>
    </>}>
      {open.map((t, i) => {
        // Direction-aware: a short gains when the mark falls below entry.
        const move = lastPrice == null ? null
          : (t.direction === "LONG" ? lastPrice - t.entry_price : t.entry_price - lastPrice)
        // Per-contract move scaled by size. The dollar multiplier belongs to
        // the contract spec, which this panel does not own -- so the value is
        // reported in POINTS and the percent is off the entry price, both of
        // which are exact without it.
        const pts = move == null ? null : move * t.qty
        const pct = move == null ? null : (move / t.entry_price) * 100
        const up = (pts ?? 0) >= 0
        return (
          <tr key={i} className="border-t border-[color:var(--hairline-soft)]">
            <td className="p-2 font-medium">{t.symbol || symbol}</td>
            <td className={`p-2 font-medium ${t.direction === "LONG" ? GAIN : LOSS}`}>
              {t.direction === "LONG" ? "Long" : "Short"}
            </td>
            <td className="p-2 text-right">{t.qty}</td>
            <td className="p-2 text-right">{t.entry_price.toFixed(2)}</td>
            <td className="p-2 text-right">{lastPrice?.toFixed(2) ?? "—"}</td>
            <td className={`p-2 text-right font-semibold ${pts == null ? "" : up ? GAIN : LOSS}`}
                title="Open P&L in points × quantity. Points, not dollars: the contract multiplier lives in the contract spec, not in this panel.">
              {pts == null ? "—" : `${up ? "+" : ""}${pts.toFixed(2)} pts`}
            </td>
            <td className={`p-2 text-right ${pct == null ? "" : up ? GAIN : LOSS}`}>
              {pct == null ? "—" : `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`}
            </td>
            {/* A protective stop and a target are BRACKET ORDERS, and the
                engine does not carry them on a trade -- the strategy decides
                the exit bar by bar. Printing a number here would invent a
                resting order that does not exist and that nothing would
                honour if price reached it. */}
            <td className="p-2 text-right text-muted-foreground"
                title="No resting stop: this strategy exits on its own signal, not a bracket order.">—</td>
            <td className="p-2 text-right text-muted-foreground"
                title="No resting target: this strategy exits on its own signal, not a bracket order.">—</td>
            <td className="p-2 whitespace-nowrap">{fmtTime(t.entry_time)}</td>
            {/* The reference puts a Close button here. There is no broker
                route behind it -- this is a backtest -- so the cell names the
                strategy that owns the exit instead of offering a control that
                would do nothing when clicked. */}
            <td className="p-2 text-muted-foreground text-xs">
              Exits on {t.strategy} signal
            </td>
          </tr>
        )
      })}
    </Grid>
  )
}

/** The count the Positions tab shows in its label. */
export function openPositionCount(trades: TradeRecord[]) {
  return trades.filter((t) => t.exit_time == null).length
}

/* ── Orders / Order History ────────────────────────────────────────────── */

type OrderRow = {
  at: string
  side: "BUY" | "SELL"
  qty: number
  price: number
  kind: "Entry" | "Exit"
  status: "Filled" | "Working"
  symbol: string
  strategy: string
  pnl: number | null
}

/**
 * Each trade is two orders -- the entry that opened it and the exit that
 * closed it. An open trade has no exit order yet, so it contributes one row
 * and that row is Working.
 */
function toOrders(trades: TradeRecord[], symbol: string): OrderRow[] {
  const rows: OrderRow[] = []
  for (const t of trades) {
    const sym = t.symbol || symbol
    const long = t.direction === "LONG"
    rows.push({
      at: t.entry_time, side: long ? "BUY" : "SELL", qty: t.qty,
      price: t.entry_price, kind: "Entry", status: "Filled",
      symbol: sym, strategy: t.strategy, pnl: null,
    })
    if (t.exit_time != null && t.exit_price != null) {
      rows.push({
        at: t.exit_time, side: long ? "SELL" : "BUY", qty: t.qty,
        price: t.exit_price, kind: "Exit", status: "Filled",
        symbol: sym, strategy: t.strategy, pnl: t.pnl,
      })
    }
  }
  // Newest first, the way an order blotter reads.
  return rows.sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0))
}

function OrderGrid({ rows, empty }: { rows: OrderRow[]; empty: React.ReactNode }) {
  if (!rows.length) return <Empty icon={<Inbox className="h-4 w-4" />}>{empty}</Empty>
  return (
    <Grid head={<>
      <th className={TH}>Time</th>
      <th className={TH}>Symbol</th>
      <th className={TH}>Side</th>
      <th className={TH}>Type</th>
      <th className={THR}>Qty</th>
      <th className={THR}>Fill Price</th>
      <th className={TH}>Status</th>
      <th className={THR}>Realized P&amp;L</th>
    </>}>
      {rows.map((o, i) => (
        <tr key={i} className="border-t border-[color:var(--hairline-soft)]">
          <td className="p-2">{fmtTime(o.at)}</td>
          <td className="p-2 font-medium">{o.symbol}</td>
          <td className={`p-2 font-medium ${o.side === "BUY" ? GAIN : LOSS}`}>{o.side}</td>
          <td className="p-2 text-muted-foreground">{o.kind}</td>
          <td className="p-2 text-right">{o.qty}</td>
          <td className="p-2 text-right">{o.price.toFixed(2)}</td>
          <td className="p-2">
            <span className={o.status === "Filled" ? "text-muted-foreground" : GAIN}>{o.status}</span>
          </td>
          <td className={`p-2 text-right font-semibold ${o.pnl == null ? "" : o.pnl >= 0 ? GAIN : LOSS}`}>
            {o.pnl == null ? "—" : signedMoney(o.pnl, 0)}
          </td>
        </tr>
      ))}
    </Grid>
  )
}

/** Working orders: the entry of any position still open at the end of the run. */
export function OrdersTable({ trades, symbol }: { trades: TradeRecord[]; symbol: string }) {
  const openEntries = trades.filter((t) => t.exit_time == null)
  const rows = toOrders(openEntries, symbol).map((o) => ({ ...o, status: "Working" as const }))
  return <OrderGrid rows={rows} empty="No working orders — nothing is open awaiting an exit." />
}

/** Order History: every fill of the run, entries and exits, newest first. */
export function OrderHistoryTable({ trades, symbol }: { trades: TradeRecord[]; symbol: string }) {
  return <OrderGrid rows={toOrders(trades, symbol)}
                    empty="No orders yet — run a backtest to fill this blotter." />
}

/* ── Balance History ───────────────────────────────────────────────────── */

/**
 * The equity curve as a ledger. Same series the Equity Curve chart draws, so
 * the two can never disagree; this view exists because a drawdown is easier
 * to read as a number than off a line.
 *
 * Only rows where the balance CHANGED are listed. A flat bar is not a ledger
 * entry, and printing thousands of them would bury the handful that matter.
 */
export function BalanceHistoryTable({ equity, initialCapital }: {
  equity: EquityPoint[]
  initialCapital: number
}) {
  if (!equity.length) {
    return <Empty icon={<Inbox className="h-4 w-4" />}>
      No balance history — run a backtest to build the equity curve.
    </Empty>
  }

  const rows: Array<{ t: string; equity: number; delta: number; dd: number }> = []
  let prev = initialCapital
  for (const p of equity) {
    const delta = p.equity - prev
    if (delta !== 0) rows.push({ t: p.t, equity: p.equity, delta, dd: p.drawdown_pct })
    prev = p.equity
  }

  if (!rows.length) {
    return <Empty icon={<Inbox className="h-4 w-4" />}>
      The balance never moved in this period — no trade closed.
    </Empty>
  }

  const peak = Math.max(...rows.map((r) => r.dd))

  return (
    <div>
      <p className="text-xs text-muted-foreground mb-2 px-1">
        Only bars where the balance changed. Opening balance {money(initialCapital)} · deepest
        drawdown {peak.toFixed(2)}% · {rows.length.toLocaleString()} movement
        {rows.length === 1 ? "" : "s"}.
      </p>
      <Grid head={<>
        <th className={TH}>Time</th>
        <th className={THR}>Change</th>
        <th className={THR}>Balance</th>
        <th className={THR}>Drawdown</th>
      </>}>
        {rows.map((r, i) => (
          <tr key={i} className="border-t border-[color:var(--hairline-soft)]">
            <td className="p-2">{fmtTime(r.t)}</td>
            <td className={`p-2 text-right font-semibold ${r.delta >= 0 ? GAIN : LOSS}`}>
              {signedMoney(r.delta, 0)}
            </td>
            <td className="p-2 text-right">{money(r.equity, 0)}</td>
            <td className={`p-2 text-right ${r.dd > 0 ? LOSS : "text-muted-foreground"}`}>
              {r.dd > 0 ? `-${r.dd.toFixed(2)}%` : "—"}
            </td>
          </tr>
        ))}
      </Grid>
    </div>
  )
}

/* ── Trading Journal ───────────────────────────────────────────────────── */

/** Notes are per (backtest, trade index) so a note cannot follow the wrong
 *  trade into a different run. Stored per browser, like the watchlist and the
 *  interval favourites -- it is a personal note, not shared state. */
const JOURNAL_KEY = "trading-journal"

type Journal = Record<string, string>

function loadJournal(): Journal {
  try {
    const raw = JSON.parse(localStorage.getItem(JOURNAL_KEY) ?? "null")
    return raw && typeof raw === "object" ? (raw as Journal) : {}
  } catch {
    return {}
  }
}

function saveJournal(j: Journal) {
  try {
    localStorage.setItem(JOURNAL_KEY, JSON.stringify(j))
  } catch {
    /* private window or blocked storage: notes still work for this session */
  }
}

/**
 * One row per trade, with the outcome the engine recorded and a free-text
 * note the trader writes. The note is the only thing here that is not derived
 * -- everything beside it is the trade as it happened, so a note can be read
 * against the result it is about.
 */
export function TradingJournalTable({ trades, backtestId }: {
  trades: TradeRecord[]
  backtestId: string | null
}) {
  const [journal, setJournal] = useState<Journal>(loadJournal)

  // Another tab editing the same journal should not be silently overwritten
  // by this one's stale copy.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === JOURNAL_KEY) setJournal(loadJournal())
    }
    window.addEventListener("storage", onStorage)
    return () => window.removeEventListener("storage", onStorage)
  }, [])

  const setNote = useCallback((key: string, text: string) => {
    setJournal((prev) => {
      const next = { ...prev }
      if (text.trim()) next[key] = text
      else delete next[key]   // an emptied note is a deleted note, not a blank one
      saveJournal(next)
      return next
    })
  }, [])

  if (!trades.length) {
    return <Empty icon={<ClipboardList className="h-4 w-4" />}>
      No trades to journal yet — run a backtest first.
    </Empty>
  }

  return (
    <div>
      <p className="text-xs text-muted-foreground mb-2 px-1">
        Notes are saved in this browser as you type, against this run's trades.
        They are not uploaded and do not appear in the exported report.
      </p>
      <Grid head={<>
        <th className={TH}>#</th>
        <th className={TH}>Side</th>
        <th className={TH}>Entry</th>
        <th className={TH}>Exit</th>
        <th className={THR}>P&amp;L</th>
        <th className={TH}>Note</th>
      </>}>
        {trades.map((t, i) => {
          const key = `${backtestId ?? "run"}:${i}`
          return (
            <tr key={i} className="border-t border-[color:var(--hairline-soft)]">
              <td className="p-2">{i + 1}</td>
              <td className={`p-2 font-medium ${t.direction === "LONG" ? GAIN : LOSS}`}>
                {t.direction === "LONG" ? "Long" : "Short"}
              </td>
              <td className="p-2 whitespace-nowrap">{fmtTime(t.entry_time)}</td>
              <td className="p-2 whitespace-nowrap">{fmtTime(t.exit_time)}</td>
              <td className={`p-2 text-right font-semibold ${t.pnl >= 0 ? GAIN : LOSS}`}>
                {signedMoney(t.pnl, 0)}
              </td>
              <td className="p-1 w-[45%]">
                <input
                  type="text"
                  value={journal[key] ?? ""}
                  onChange={(e) => setNote(key, e.target.value)}
                  placeholder="Why this trade? What would you do again?"
                  aria-label={`Journal note for trade ${i + 1}`}
                  className="w-full bg-transparent border border-[color:var(--hairline-soft)] rounded px-2 py-1
                             text-sm text-foreground placeholder:text-muted-foreground/60
                             focus:outline-none focus:border-[#38bdf8]"
                />
              </td>
            </tr>
          )
        })}
      </Grid>
    </div>
  )
}
