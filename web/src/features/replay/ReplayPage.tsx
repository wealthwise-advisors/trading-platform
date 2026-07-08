// In-app port of ui/live_app.py — configure a strategy, then watch it trade
// bar-by-bar over a WebSocket (api/routers/replay.py drives ReplayEngine.step()
// server-side on a timer, one frame per message).

import { useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { ReplayBar, ReplayTrade, ReplaySignal, ReplayWsMessage } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Slider } from "@/components/ui/slider"
import { Card } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { LiveReplayChart } from "@/components/charts/LiveReplayChart"
import { EquityChart } from "@/components/charts/EquityChart"
import { GOOD, CRITICAL, NEUTRAL } from "@/components/cards/StatCard"

type Status = "idle" | "loading" | "ready" | "playing" | "paused" | "done"

function defaultDateRange() {
  const today = new Date()
  const end = new Date(today)
  end.setDate(end.getDate() - 1)
  const start = new Date(end)
  start.setDate(start.getDate() - 4)
  return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) }
}

const SPEED_OPTIONS = [
  { label: "0.05s", value: 0.05 }, { label: "0.1s", value: 0.1 }, { label: "0.2s", value: 0.2 },
  { label: "0.5s", value: 0.5 }, { label: "1s", value: 1.0 },
]

function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-[#0e1424] border border-white/6 rounded-lg px-3 py-2">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="text-lg font-bold" style={{ color: color ?? NEUTRAL }}>{value}</div>
    </div>
  )
}

export function ReplayPage() {
  const { data: strategies } = useQuery({ queryKey: ["strategies"], queryFn: api.strategies })

  const dr = defaultDateRange()
  const [symbol, setSymbol] = useState("ES")
  const [timeframe, setTimeframe] = useState("5m")
  const [strategyId, setStrategyId] = useState("rsi_divergence")
  const [params, setParams] = useState<Record<string, number>>({ rsi_overbought: 94, rsi_oversold: 2, swing_lookback: 5 })
  const [initialCapital, setInitialCapital] = useState(100_000)
  const [contractsPerTrade, setContractsPerTrade] = useState(1)
  const [startDate, setStartDate] = useState(dr.start)
  const [endDate, setEndDate] = useState(dr.end)
  const [visibleBars, setVisibleBars] = useState(150)
  const [speed, setSpeed] = useState(0.1)

  const [status, setStatus] = useState<Status>("idle")
  const [error, setError] = useState<string | null>(null)
  const [strategyName, setStrategyName] = useState("")
  const [barsProcessed, setBarsProcessed] = useState(0)
  const [totalBars, setTotalBars] = useState(0)
  const [bars, setBars] = useState<ReplayBar[]>([])
  const [completedTrades, setCompletedTrades] = useState<ReplayTrade[]>([])
  const [openTrade, setOpenTrade] = useState<ReplayTrade | null>(null)
  const [equityPoints, setEquityPoints] = useState<{ t: string; equity: number }[]>([])
  const [position, setPosition] = useState(0)
  const [portfolioValue, setPortfolioValue] = useState(initialCapital)
  const [lastSignal, setLastSignal] = useState<ReplaySignal | null>(null)

  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => () => wsRef.current?.close(), [])

  const currentStrategy = strategies?.find((s) => s.id === strategyId)

  function resetAccumulators() {
    setBars([]); setCompletedTrades([]); setOpenTrade(null); setEquityPoints([])
    setPosition(0); setPortfolioValue(initialCapital); setLastSignal(null); setBarsProcessed(0)
  }

  async function handleLoad() {
    setStatus("loading"); setError(null)
    wsRef.current?.close()
    try {
      const resp = await api.createReplay({
        symbol, timeframe, strategy_id: strategyId, params,
        initial_capital: initialCapital, contracts_per_trade: contractsPerTrade,
        start_date: startDate, end_date: endDate,
      })
      setStrategyName(resp.strategy_name)
      setTotalBars(resp.total_bars)
      resetAccumulators()
      setPortfolioValue(resp.initial_capital)

      const ws = new WebSocket(api.replayWsUrl(resp.replay_id))
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data) as ReplayWsMessage
        if (msg.type === "frame") {
          setBars((prev) => [...prev, msg.bar])
          setCompletedTrades(msg.completed_trades)
          setOpenTrade(msg.open_trade)
          setPosition(msg.position)
          setPortfolioValue(msg.portfolio_value)
          setLastSignal(msg.signal)
          setBarsProcessed(msg.bars_processed)
          setTotalBars(msg.total_bars)
          if (msg.equity_point) {
            setEquityPoints((prev) => [...prev, msg.equity_point!])
          }
        } else if (msg.type === "reset") {
          resetAccumulators(); setStatus("ready")
        } else if (msg.type === "done") {
          setStatus("done")
        } else if (msg.type === "error") {
          setError(msg.message); setStatus("idle")
        }
      }
      ws.onerror = () => setError("WebSocket connection failed.")
      wsRef.current = ws
      setStatus("ready")
    } catch (e) {
      setError((e as Error).message)
      setStatus("idle")
    }
  }

  function send(action: string, extra?: Record<string, unknown>) {
    wsRef.current?.send(JSON.stringify({ action, ...extra }))
  }

  const play = () => { send("play"); setStatus("playing") }
  const pause = () => { send("pause"); setStatus("paused") }
  const reset = () => { send("reset") }
  const changeSpeed = (v: number) => { setSpeed(v); send("set_speed", { speed: v }) }

  const ready = status !== "idle" && status !== "loading"
  const done = status === "done"

  const pnls = completedTrades.map((t) => t.pnl)
  const wins = pnls.filter((p) => p > 0)
  const losses = pnls.filter((p) => p <= 0)
  const totalPnl = pnls.reduce((a, b) => a + b, 0)
  const winRate = completedTrades.length ? (wins.length / completedTrades.length) * 100 : 0
  const avgWin = wins.length ? wins.reduce((a, b) => a + b, 0) / wins.length : 0
  const avgLoss = losses.length ? losses.reduce((a, b) => a + b, 0) / losses.length : 0

  let equityMax = -Infinity
  const equityWithDrawdown = equityPoints.map((p) => {
    equityMax = Math.max(equityMax, p.equity)
    return { t: p.t, equity: p.equity, drawdown_pct: equityMax > 0 ? ((p.equity - equityMax) / equityMax) * 100 : 0 }
  })

  return (
    <div className="space-y-4 p-4 w-full max-w-none">
      <Card className="p-4 border border-white/6 w-full">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 items-end">
          <div className="space-y-1">
            <Label className="text-xs">Symbol</Label>
            <Select value={symbol} onValueChange={setSymbol} disabled={ready}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>{["ES", "NQ", "MES", "CL"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Timeframe</Label>
            <Select value={timeframe} onValueChange={setTimeframe} disabled={ready}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>{["1m", "5m", "15m", "1h"].map((tf) => <SelectItem key={tf} value={tf}>{tf}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-1 col-span-2">
            <Label className="text-xs">Strategy</Label>
            <Select
              value={strategyId} disabled={ready}
              onValueChange={(v) => {
                setStrategyId(v)
                const s = strategies?.find((x) => x.id === v)
                if (s) setParams(Object.fromEntries(s.params.map((p) => [p.name, p.default])))
              }}
            >
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>{(strategies ?? []).map((s) => <SelectItem key={s.id} value={s.id}>{s.label}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Start</Label>
            <Input type="date" value={startDate} disabled={ready} onChange={(e) => setStartDate(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">End</Label>
            <Input type="date" value={endDate} disabled={ready} onChange={(e) => setEndDate(e.target.value)} />
          </div>
        </div>

        {currentStrategy && currentStrategy.params.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-3">
            {currentStrategy.params.map((p) => (
              <div key={p.name} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span>{p.label}</span>
                  <span className="font-mono text-muted-foreground">{params[p.name] ?? p.default}</span>
                </div>
                <Slider min={p.min} max={p.max} step={p.step} disabled={ready}
                        value={[params[p.name] ?? p.default]}
                        onValueChange={([v]) => setParams((prev) => ({ ...prev, [p.name]: v }))} />
              </div>
            ))}
          </div>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
          <div className="space-y-1">
            <Label className="text-xs">Initial Capital ($)</Label>
            <Input type="number" step={10000} value={initialCapital} disabled={ready}
                   onChange={(e) => setInitialCapital(Number(e.target.value))} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Contracts / Trade</Label>
            <Input type="number" min={1} max={10} value={contractsPerTrade} disabled={ready}
                   onChange={(e) => setContractsPerTrade(Number(e.target.value))} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Speed</Label>
            <Select value={String(speed)} onValueChange={(v) => changeSpeed(Number(v))}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>{SPEED_OPTIONS.map((o) => <SelectItem key={o.value} value={String(o.value)}>{o.label}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Visible bars: {visibleBars}</Label>
            <Slider min={50} max={500} step={25} value={[visibleBars]} onValueChange={([v]) => setVisibleBars(v)} />
          </div>
        </div>

        <Separator className="my-3" />
        <div className="flex flex-wrap gap-2 items-center">
          <Button onClick={handleLoad} disabled={status === "loading"} variant={ready ? "secondary" : "default"}>
            {status === "loading" ? "Loading…" : "⬇ Load Data"}
          </Button>
          <Button onClick={play} disabled={!ready || status === "playing" || done}>▶ Play</Button>
          <Button onClick={pause} disabled={!ready || status !== "playing"} variant="secondary">⏸ Pause</Button>
          <Button onClick={reset} disabled={!ready} variant="secondary">↺ Reset</Button>
          {ready && (
            <span className="text-sm text-muted-foreground ml-2">
              {strategyName} — Bar {barsProcessed.toLocaleString()} / {totalBars.toLocaleString()}
              {done && " — Complete"}
              {status === "playing" && " — ▶ Playing"}
              {status === "paused" && " — ⏸ Paused"}
            </span>
          )}
        </div>
        {ready && totalBars > 0 && (
          <div className="w-full bg-[#0e1424] rounded-full h-1.5 mt-2 overflow-hidden">
            <div className="h-full bg-primary transition-[width]" style={{ width: `${(barsProcessed / totalBars) * 100}%` }} />
          </div>
        )}
        {error && <p className="text-xs text-destructive mt-2">{error}</p>}
      </Card>

      {ready && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            <Metric label="Portfolio" value={`$${portfolioValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                    color={portfolioValue >= initialCapital ? GOOD : CRITICAL} />
            <Metric label="Total P&L" value={`${totalPnl >= 0 ? "+" : ""}$${totalPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                    color={totalPnl >= 0 ? GOOD : CRITICAL} />
            <Metric label="Trades" value={String(completedTrades.length)} />
            <Metric label="Win Rate" value={`${winRate.toFixed(0)}%`} />
            <Metric label="Avg Win" value={`$${avgWin.toLocaleString(undefined, { maximumFractionDigits: 0 })}`} color={GOOD} />
            <Metric label="Avg Loss" value={`$${avgLoss.toLocaleString(undefined, { maximumFractionDigits: 0 })}`} color={CRITICAL} />
            <Metric label="Position" value={position === 0 ? "FLAT" : position > 0 ? `LONG +${position}` : `SHORT ${position}`}
                    color={position === 0 ? NEUTRAL : position > 0 ? GOOD : CRITICAL} />
          </div>

          {lastSignal && (
            <div className="rounded-md px-3 py-2 border-l-4"
                 style={{
                   borderColor: lastSignal.type === "SELL" ? CRITICAL : lastSignal.type === "BUY" ? GOOD : "#e3b341",
                   background: `color-mix(in srgb, ${lastSignal.type === "SELL" ? CRITICAL : lastSignal.type === "BUY" ? GOOD : "#e3b341"} 12%, transparent)`,
                 }}>
              <b>{lastSignal.type}</b> <span className="text-muted-foreground">{lastSignal.reason}</span>
            </div>
          )}

          <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
            <Card className="p-2 border border-white/6 xl:col-span-3">
              <LiveReplayChart bars={bars} completedTrades={completedTrades} openTrade={openTrade} visibleBars={visibleBars} />
            </Card>
            <Card className="p-2 border border-white/6">
              {equityWithDrawdown.length > 1 && (
                <EquityChart points={equityWithDrawdown} initialCapital={initialCapital} />
              )}
            </Card>
          </div>

          {completedTrades.length > 0 && (
            <Card className="p-4 border border-white/6 w-full">
              <p className="text-sm font-semibold mb-2">Recent Trades</p>
              <div className="overflow-x-auto rounded-lg border border-white/6">
                <table className="w-full text-sm">
                  <thead className="bg-[#0e1424] text-muted-foreground">
                    <tr>
                      <th className="text-left p-2 font-medium">Entry</th>
                      <th className="text-left p-2 font-medium">Exit</th>
                      <th className="text-left p-2 font-medium">Dir</th>
                      <th className="text-right p-2 font-medium">Entry $</th>
                      <th className="text-right p-2 font-medium">Exit $</th>
                      <th className="text-right p-2 font-medium">P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {completedTrades.slice(-10).reverse().map((t, i) => (
                      <tr key={i} className="border-t border-white/6">
                        <td className="p-2">{t.entry_time.replace("T", " ").slice(0, 16)}</td>
                        <td className="p-2">{t.exit_time ? t.exit_time.replace("T", " ").slice(0, 16) : "OPEN"}</td>
                        <td className={`p-2 ${t.direction === "LONG" ? "text-green-400" : "text-red-400"}`}>{t.direction}</td>
                        <td className="p-2 text-right">{t.entry_price.toFixed(2)}</td>
                        <td className="p-2 text-right">{t.exit_price?.toFixed(2) ?? "—"}</td>
                        <td className={`p-2 text-right font-semibold ${t.pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {t.pnl >= 0 ? "+" : ""}${t.pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}

      {!ready && !error && (
        <p className="text-muted-foreground p-8 text-center">
          Configure your strategy above, then click <b>⬇ Load Data</b> to begin.
        </p>
      )}
    </div>
  )
}
