/**
 * Paper Trading (upgrade plan, Feature 5): the session, an order ticket with brackets and
 * trailing stops, the working orders, and a risk / reward calculator.
 *
 * PAPER ONLY, said on every surface: the server builds a PaperBroker and nothing else
 * (api/routers/live.py). This tab replaces the header's "Deploy" button, which read as
 * deploying the application.
 *
 * The session itself is driven by ResultsPage (useLiveSession), so it keeps getting bars
 * whichever tab is open; this panel only reads and acts on it.
 */
import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { FlaskConical } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { api } from "@/lib/api"
import { riskReward } from "@/lib/riskReward"
import type { LiveStatus, OrderTicket, PaperOrderType, WorkingOrder } from "@/lib/types"
import { useConfigStore } from "@/store/configStore"
import { DeployDialog } from "./DeployDialog"
import type { useLiveSession } from "./useLiveSession"

type Session = ReturnType<typeof useLiveSession>

const num = (s: string) => (s.trim() === "" ? undefined : Number(s))
const money = (n: number) => `$${n.toLocaleString("en-US", { maximumFractionDigits: 2 })}`
const TYPE_LABEL: Record<PaperOrderType, string> = { MARKET: "Market", LIMIT: "Limit", STOP: "Stop", STOP_LIMIT: "Stop limit" }

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-muted-foreground">
      <span>{label}</span>
      {children}
    </label>
  )
}

function useTickSpec(symbol: string) {
  const q = useQuery({ queryKey: ["contracts"], queryFn: () => api.contracts(), staleTime: 10 * 60_000 })
  const spec = (q.data?.[symbol] ?? {}) as { tick_size?: number; tick_value?: number }
  return { tickSize: spec.tick_size ?? 0.25, tickValue: spec.tick_value ?? 12.5 }
}

export function PaperTradingPanel({ live }: { live: Session }) {
  const { status, running } = live
  const symbol = useConfigStore((s) => s.symbol)
  const strategyId = useConfigStore((s) => s.strategyId)
  const params = useConfigStore((s) => s.params)
  const dataSource = useConfigStore((s) => s.dataSource)
  const timeframe = useConfigStore((s) => s.timeframe)
  const [dialog, setDialog] = useState(false)

  return (
    <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_340px]">
      <div className="space-y-3 min-w-0">
        <Card className="p-3 border border-[color:var(--hairline-soft)]">
          <div className="flex flex-wrap items-center gap-3">
            <FlaskConical className="h-4 w-4 text-sky-700 dark:text-sky-300" aria-hidden />
            <span className="rounded bg-sky-500/15 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.08em] text-sky-800 dark:text-sky-200">
              Paper, no real orders
            </span>
            {running && status ? (
              <>
                <span className="text-sm">{status.strategy} on <b>{status.symbol}</b></span>
                <span className="text-sm tabular-nums" data-testid="paper-position">
                  Position {status.position === 0 ? "flat" : `${status.position > 0 ? "+" : ""}${status.position}`}
                </span>
                <span className="text-sm tabular-nums">Cash {money(status.cash)}</span>
                <span className="text-xs text-muted-foreground">{status.bars_seen} bars, {status.orders_remaining} orders left</span>
                <Button size="sm" variant="secondary" className="ml-auto" onClick={() => void live.stop()}>Stop session</Button>
              </>
            ) : (
              <>
                <span className="text-sm text-muted-foreground">
                  {status?.halted ? `Halted: ${status.halt_reason}` : "No paper session running."}
                </span>
                <Button size="sm" className="ml-auto" onClick={() => setDialog(true)}>Start paper session</Button>
              </>
            )}
          </div>
        </Card>
        {running && status && <OrderTicketCard status={status} />}
        {running && status && <WorkingOrdersCard orders={status.working_orders ?? []} />}
        {status && status.events.length > 0 && (
          <Card className="p-3 border border-[color:var(--hairline-soft)]">
            <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Session log</div>
            <ul className="max-h-56 overflow-y-auto text-xs tabular-nums space-y-0.5">
              {status.events.slice(0, 20).map((e, i) => (
                <li key={i}><span className="text-muted-foreground">{e.at.slice(11)}</span> {e.text}</li>
              ))}
            </ul>
          </Card>
        )}
      </div>
      <RiskRewardCard symbol={running && status ? status.symbol : symbol} />
      <DeployDialog
        open={dialog} onOpenChange={setDialog}
        plan={{ mode: "paper", dataSource, symbol, timeframe, strategyName: strategyId, params, contracts: 1 }}
        starting={live.isStarting} error={live.startError?.message ?? null}
        onConfirm={async () => {
          try {
            await live.start({ strategy_id: strategyId, symbol, params, contracts: 1 })
            setDialog(false)
          } catch { /* shown in the dialog */ }
        }}
      />
    </div>
  )
}

function OrderTicketCard({ status }: { status: LiveStatus }) {
  const qc = useQueryClient()
  const [side, setSide] = useState<"BUY" | "SELL">("BUY")
  const [type, setType] = useState<PaperOrderType>("MARKET")
  const [qty, setQty] = useState("1")
  const [limit, setLimit] = useState("")
  const [stop, setStop] = useState("")
  const [target, setTarget] = useState("")
  const [stopTicks, setStopTicks] = useState("")
  const [trail, setTrail] = useState("")
  const place = useMutation({
    mutationFn: (t: OrderTicket) => api.livePlaceOrder(t),
    onSuccess: (s) => qc.setQueryData(["live-status"], s),
  })
  const needsLimit = type === "LIMIT" || type === "STOP_LIMIT"
  const needsStop = type === "STOP" || type === "STOP_LIMIT"
  const submit = () => place.mutate({
    side, quantity: Number(qty) || 0, order_type: type,
    limit_price: needsLimit ? num(limit) : undefined, stop_price: needsStop ? num(stop) : undefined,
    target_ticks: num(target), stop_ticks: num(stopTicks),
    trail_ticks: type === "STOP" ? num(trail) : undefined,
  })
  return (
    <Card className="p-3 border border-[color:var(--hairline-soft)]">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Order ticket: {status.symbol}</div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex rounded-md border border-[color:var(--hairline-mid)] overflow-hidden" role="group" aria-label="Side">
          {(["BUY", "SELL"] as const).map((s) => (
            <button key={s} type="button" aria-pressed={side === s} onClick={() => setSide(s)}
                    className={`px-4 py-1.5 text-sm font-bold ${side === s
                      ? (s === "BUY" ? "bg-[var(--gain)] text-white" : "bg-[var(--loss)] text-white")
                      : "text-muted-foreground hover:bg-[color:var(--raise-3)]"}`}>{s === "BUY" ? "Buy" : "Sell"}</button>
          ))}
        </div>
        <Field label="Contracts"><Input className="w-20" type="number" min={1} value={qty} onChange={(e) => setQty(e.target.value)} aria-label="Contracts" /></Field>
        <Field label="Type">
          <Select value={type} onValueChange={(v) => setType(v as PaperOrderType)}>
            <SelectTrigger className="w-32" aria-label="Order type"><SelectValue /></SelectTrigger>
            <SelectContent>
              {(Object.keys(TYPE_LABEL) as PaperOrderType[]).map((t) => <SelectItem key={t} value={t}>{TYPE_LABEL[t]}</SelectItem>)}
            </SelectContent>
          </Select>
        </Field>
        {needsStop && <Field label="Stop price"><Input className="w-28" type="number" step="any" value={stop} onChange={(e) => setStop(e.target.value)} aria-label="Stop price" /></Field>}
        {needsLimit && <Field label="Limit price"><Input className="w-28" type="number" step="any" value={limit} onChange={(e) => setLimit(e.target.value)} aria-label="Limit price" /></Field>}
        {type === "STOP" && <Field label="Trail (ticks)"><Input className="w-24" type="number" min={1} value={trail} onChange={(e) => setTrail(e.target.value)} aria-label="Trail ticks" placeholder="off" /></Field>}
        <Field label="Target (ticks)"><Input className="w-24" type="number" min={1} value={target} onChange={(e) => setTarget(e.target.value)} aria-label="Bracket target ticks" placeholder="none" /></Field>
        <Field label="Stop loss (ticks)"><Input className="w-24" type="number" min={1} value={stopTicks} onChange={(e) => setStopTicks(e.target.value)} aria-label="Bracket stop ticks" placeholder="none" /></Field>
        <Button onClick={submit} disabled={place.isPending}>Place paper order</Button>
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground">
        Target and stop loss make a bracket: both wait for the entry to fill, and one cancels the other.
        Ticks count from the entry price, or from the last close for a market order.
        When one bar reaches both, the stop is assumed to fill first.
      </p>
      {place.error && <p role="alert" className="mt-1 text-xs text-[var(--loss)]">{(place.error as Error).message}</p>}
    </Card>
  )
}

function WorkingOrdersCard({ orders }: { orders: WorkingOrder[] }) {
  const qc = useQueryClient()
  const cancel = useMutation({
    mutationFn: (id: string) => api.liveCancelOrder(id),
    onSuccess: (s) => qc.setQueryData(["live-status"], s),
  })
  return (
    <Card className="p-3 border border-[color:var(--hairline-soft)]">
      <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Working orders</div>
      {orders.length === 0 ? <p className="text-xs text-muted-foreground">None.</p> : (
        <table className="w-full text-xs tabular-nums" aria-label="Working orders">
          <thead><tr className="text-left text-muted-foreground">
            <th className="py-1">Side</th><th>Qty</th><th>Type</th><th>Price</th><th>Role</th><th />
          </tr></thead>
          <tbody>
            {orders.map((o) => (
              <tr key={o.id} className="border-t border-[color:var(--hairline-soft)]">
                <td className="py-1 font-semibold" style={{ color: o.side === "BUY" ? "var(--gain)" : "var(--loss)" }}>{o.side === "BUY" ? "Buy" : "Sell"}</td>
                <td>{o.quantity}</td>
                <td>{TYPE_LABEL[o.order_type]}{o.trail_ticks ? `, trailing ${o.trail_ticks} ticks` : ""}</td>
                <td>{[o.stop_price != null && `stop ${o.stop_price.toFixed(2)}`, o.limit_price != null && `limit ${o.limit_price.toFixed(2)}`].filter(Boolean).join(", ") || "at market"}</td>
                <td className="text-muted-foreground">{o.parent_id ? (o.order_type === "LIMIT" ? "bracket target, after entry" : "bracket stop, after entry") : "entry"}</td>
                <td className="text-right">
                  {!o.parent_id && <button type="button" className="underline underline-offset-2 hover:text-foreground text-muted-foreground"
                                           aria-label={`Cancel order ${o.id}`} onClick={() => cancel.mutate(o.id)}>Cancel</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  )
}

function RiskRewardCard({ symbol }: { symbol: string }) {
  const { tickSize, tickValue } = useTickSpec(symbol)
  const [v, setV] = useState({ entry: "", stop: "", target: "", contracts: "1", account: "100000" })
  const r = useMemo(() => riskReward({
    entry: Number(v.entry || NaN), stop: Number(v.stop || NaN), target: Number(v.target || NaN),
    contracts: Number(v.contracts), account: Number(v.account) || 0, tickSize, tickValue,
  }), [v, tickSize, tickValue])
  const set = (k: keyof typeof v) => (e: React.ChangeEvent<HTMLInputElement>) => setV((s) => ({ ...s, [k]: e.target.value }))
  return (
    <Card className="p-3 border border-[color:var(--hairline-soft)] h-fit">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Risk / reward: {symbol}</div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Entry"><Input type="number" step="any" value={v.entry} onChange={set("entry")} aria-label="R:R entry" /></Field>
        <Field label="Contracts"><Input type="number" min={1} value={v.contracts} onChange={set("contracts")} aria-label="R:R contracts" /></Field>
        <Field label="Stop"><Input type="number" step="any" value={v.stop} onChange={set("stop")} aria-label="R:R stop" /></Field>
        <Field label="Target"><Input type="number" step="any" value={v.target} onChange={set("target")} aria-label="R:R target" /></Field>
        <div className="col-span-2"><Field label="Account ($)"><Input type="number" value={v.account} onChange={set("account")} aria-label="R:R account" /></Field></div>
      </div>
      <div className="mt-3 text-sm tabular-nums" data-testid="rr-result">
        {r ? (
          <dl className="grid grid-cols-2 gap-y-1">
            <dt className="text-muted-foreground">Trade</dt><dd className="text-right font-semibold">{r.side === "long" ? "Long" : "Short"}</dd>
            <dt className="text-muted-foreground">Risk</dt><dd className="text-right text-[var(--loss)]">{money(r.risk)} ({r.riskTicks} ticks)</dd>
            <dt className="text-muted-foreground">Reward</dt><dd className="text-right text-[var(--gain)]">{money(r.reward)} ({r.rewardTicks} ticks)</dd>
            <dt className="text-muted-foreground">Reward : risk</dt><dd className="text-right font-semibold">{r.ratio.toFixed(2)} : 1</dd>
            {r.riskPct != null && <><dt className="text-muted-foreground">Account at risk</dt><dd className="text-right">{r.riskPct.toFixed(2)}%</dd></>}
          </dl>
        ) : (
          <p className="text-xs text-muted-foreground">Enter an entry, a stop on one side of it and a target on the other.</p>
        )}
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground">{symbol}: {tickSize} a tick, ${tickValue} a tick per contract.</p>
    </Card>
  )
}
