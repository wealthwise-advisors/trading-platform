/**
 * Strategy research (upgrade plan, Feature 6): walk-forward, Monte Carlo on the current
 * run, and a side-by-side comparison of saved runs.
 *
 * Walk-forward runs as a server job (api/research.py): this page starts it, shows its
 * progress, and can cancel it. Monte Carlo answers at once. Comparison reads the runs'
 * own summaries and equity curves, so its numbers are the same ones each run reports.
 */
import { useEffect, useMemo, useState } from "react"
import { useQueries, useQuery } from "@tanstack/react-query"
import type { Data, Layout } from "plotly.js"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api } from "@/lib/api"
import { chartTheme } from "@/lib/chartTheme"
import Plot from "@/lib/plot"
import { efficiencyNote, type MonteCarloResult, type MonteCarloSide, type ResearchJob } from "@/lib/research"
import { useConfigStore } from "@/store/configStore"
import { useThemeStore } from "@/store/themeStore"

const money = (n: number) => `${n < 0 ? "-" : ""}$${Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 0 })}`
const pct = (n: number) => `${n.toFixed(1)}%`
/** Clearly different hues, never shades of one: told apart without a legend. */
const RUN_COLORS = ["#38bdf8", "#f59e0b", "#e879f9", "#22c55e"]

function Heading({ children }: { children: React.ReactNode }) {
  return <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{children}</div>
}

function useLayout(title: string, yTitle: string): Partial<Layout> {
  useThemeStore((s) => s.theme)
  const { paper: BG, grid: GRID, ink: INK, hover: HOVER } = chartTheme()
  return {
    title: { text: title, font: { size: 13, color: INK } }, paper_bgcolor: BG, plot_bgcolor: BG,
    font: { color: INK }, height: 340, margin: { l: 70, r: 20, t: 40, b: 45 }, hovermode: "x unified",
    legend: { bgcolor: HOVER, orientation: "h", y: -0.2 },
    xaxis: { gridcolor: GRID }, yaxis: { gridcolor: GRID, title: { text: yTitle } },
  }
}

export function ResearchPanel({ backtestId }: { backtestId: string | null }) {
  return (
    <Tabs defaultValue="walk" className="w-full">
      <TabsList aria-label="Research">
        <TabsTrigger value="walk">Walk-forward</TabsTrigger>
        <TabsTrigger value="mc">Monte Carlo</TabsTrigger>
        <TabsTrigger value="compare">Compare runs</TabsTrigger>
      </TabsList>
      <TabsContent value="walk" className="mt-3"><WalkForward /></TabsContent>
      <TabsContent value="mc" className="mt-3"><MonteCarlo backtestId={backtestId} /></TabsContent>
      <TabsContent value="compare" className="mt-3"><CompareRuns current={backtestId} /></TabsContent>
    </Tabs>
  )
}

// ── walk-forward ────────────────────────────────────────────────────────────

function WalkForward() {
  const cfg = useConfigStore()
  const [folds, setFolds] = useState("4")
  const [train, setTrain] = useState("3")
  const [metric, setMetric] = useState<"sharpe_ratio" | "total_return_pct" | "profit_factor">("total_return_pct")
  const [jobId, setJobId] = useState<string | null>(null)
  const [startError, setStartError] = useState<string | null>(null)
  const jobQ = useQuery({
    queryKey: ["research-job", jobId], queryFn: () => api.researchJob(jobId!), enabled: !!jobId,
    refetchInterval: (q) => ((q.state.data as ResearchJob | undefined)?.status === "running" ? 1000 : false),
  })
  const job = jobQ.data
  const layout = useLayout("Walk-forward: the test windows joined", "Equity ($)")

  const start = async () => {
    setStartError(null)
    try {
      const { job_id } = await api.startWalkForward({
        data_source: cfg.dataSource, symbol: cfg.symbol, timeframe: cfg.timeframe, strategy_id: cfg.strategyId,
        initial_capital: cfg.initialCapital, contracts_per_trade: cfg.contractsPerTrade,
        commission_per_contract: cfg.commission, start_date: cfg.startDate, end_date: cfg.endDate,
        session_start: cfg.sessionStart, session_end: cfg.sessionEnd, metric,
        folds: Number(folds), train_blocks: Number(train),
      })
      setJobId(job_id)
    } catch (e) { setStartError((e as Error).message) }
  }
  const running = job?.status === "running"
  const r = job?.result
  return (
    <div className="space-y-3">
      <Card className="p-3 border border-[color:var(--hairline-soft)]">
        <Heading>Walk-forward: {cfg.strategyId} on {cfg.symbol} {cfg.timeframe}, {cfg.startDate} to {cfg.endDate}</Heading>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-muted-foreground flex flex-col gap-1">Test windows
            <Input className="w-20" type="number" min={2} max={8} value={folds} onChange={(e) => setFolds(e.target.value)} aria-label="Test windows" /></label>
          <label className="text-xs text-muted-foreground flex flex-col gap-1">Training length (windows)
            <Input className="w-20" type="number" min={1} max={6} value={train} onChange={(e) => setTrain(e.target.value)} aria-label="Training windows" /></label>
          <label className="text-xs text-muted-foreground flex flex-col gap-1">Optimise for
            <select className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm" value={metric}
                    onChange={(e) => setMetric(e.target.value as typeof metric)} aria-label="Optimise for">
              <option value="total_return_pct">Total return</option><option value="sharpe_ratio">Sharpe ratio</option>
              <option value="profit_factor">Profit factor</option>
            </select></label>
          {running
            ? <Button variant="secondary" onClick={() => void api.cancelResearchJob(jobId!).then(() => jobQ.refetch())}>Cancel</Button>
            : <Button onClick={() => void start()}>Run walk-forward</Button>}
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">
          The dates are cut into equal windows. Each test window is traded with the settings the Strategy Optimizer
          picked on the windows just before it, which it never saw. Uses the sidebar's symbol, timeframe, strategy and dates.
        </p>
        {startError && <p role="alert" className="mt-1 text-xs text-[var(--loss)]">{startError}</p>}
        {job && (
          <div className="mt-2 text-xs" role="status">
            {running && <>Running: {job.progress.done} of {job.progress.total || "?"} backtests
              <div className="mt-1 h-1.5 w-64 rounded bg-[color:var(--raise-3)]"><div className="h-1.5 rounded bg-[#38bdf8]"
                style={{ width: `${job.progress.total ? (100 * job.progress.done) / job.progress.total : 0}%` }} /></div></>}
            {job.status === "failed" && <span className="text-[var(--loss)]">Failed: {job.error}</span>}
            {job.status === "cancelled" && <span>Cancelled. Folds finished before that are shown.</span>}
            {r && r.folds.length === 0 && (
              <div data-testid="wf-empty" className="text-[var(--loss)]">
                No window could be tested.{r.notes.map((n) => <div key={n} className="text-muted-foreground">{n}</div>)}
              </div>
            )}
          </div>
        )}
      </Card>
      {r && r.folds.length > 0 && (
        <>
          <Card className="p-3 border border-[color:var(--hairline-soft)]">
            <div className="flex flex-wrap gap-6 text-sm tabular-nums" data-testid="wf-summary">
              <div><div className="text-xs text-muted-foreground">Unseen-data return</div><b>{pct(r.test_return_pct)}</b></div>
              <div><div className="text-xs text-muted-foreground">Test trades</div><b>{r.test_trades}</b></div>
              <div><div className="text-xs text-muted-foreground">Walk-forward efficiency</div><b>{r.efficiency ?? "n/a"}</b></div>
              <div className="max-w-md text-xs text-muted-foreground self-end">{efficiencyNote(r.efficiency)}</div>
            </div>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-xs tabular-nums" aria-label="Walk-forward folds">
                <thead><tr className="text-left text-muted-foreground">
                  <th className="py-1">Trained on</th><th>Tested on</th><th>Settings chosen</th>
                  <th className="text-right">Train return</th><th className="text-right">Test return</th>
                  <th className="text-right">Trades</th><th className="text-right">Max DD</th></tr></thead>
                <tbody>{r.folds.map((f) => (
                  <tr key={f.test_start} className="border-t border-[color:var(--hairline-soft)]">
                    <td className="py-1">{f.train_start} to {f.train_end}</td><td>{f.test_start} to {f.test_end}</td>
                    <td>{Object.entries(f.params).map(([k, v]) => `${k} ${v}`).join(", ") || "defaults"}</td>
                    <td className="text-right">{pct(f.train_return_pct)}</td>
                    <td className="text-right" style={{ color: f.test_return_pct >= 0 ? "var(--gain)" : "var(--loss)" }}>{pct(f.test_return_pct)}</td>
                    <td className="text-right">{f.test_trades}</td><td className="text-right">{pct(f.test_max_drawdown_pct)}</td>
                  </tr>))}</tbody>
              </table>
            </div>
            {r.notes.map((n) => <p key={n} className="mt-1 text-[11px] text-muted-foreground">{n}</p>)}
          </Card>
          <Card className="p-2 border border-[color:var(--hairline-soft)]">
            <Plot data={[{ type: "scatter", mode: "lines", x: r.equity.map((p) => p.t), y: r.equity.map((p) => p.equity),
                           name: "Test windows", line: { color: "#38bdf8", width: 2, shape: "hv" } } as Data]}
                  layout={layout} config={{ displaylogo: false }} style={{ width: "100%" }} useResizeHandler />
          </Card>
        </>
      )}
    </div>
  )
}

// ── Monte Carlo ─────────────────────────────────────────────────────────────

function MonteCarlo({ backtestId }: { backtestId: string | null }) {
  const [runs, setRuns] = useState("1000")
  const [threshold, setThreshold] = useState("")
  const [res, setRes] = useState<MonteCarloResult | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const layout = useLayout("Bootstrap: 5%, 50% and 95% of the simulated equity paths", "Equity ($)")
  useEffect(() => { setRes(null) }, [backtestId])
  if (!backtestId) return <p className="text-sm text-muted-foreground">Run a backtest first: Monte Carlo works on its trades.</p>
  const go = async () => {
    setBusy(true); setErr(null)
    try { setRes(await api.monteCarlo(backtestId, { runs: Number(runs), seed: 0, loss_threshold: Number(threshold) || undefined })) }
    catch (e) { setErr((e as Error).message) }
    setBusy(false)
  }
  const fan = res?.bootstrap.equity_fan
  const x = fan ? fan.p50.map((_, i) => i) : []
  return (
    <div className="space-y-3">
      <Card className="p-3 border border-[color:var(--hairline-soft)]">
        <Heading>Monte Carlo on this run's trades</Heading>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-muted-foreground flex flex-col gap-1">Simulations
            <Input className="w-24" type="number" min={100} max={20000} value={runs} onChange={(e) => setRuns(e.target.value)} aria-label="Simulations" /></label>
          <label className="text-xs text-muted-foreground flex flex-col gap-1">Chance of losing more than ($)
            <Input className="w-32" type="number" min={1} value={threshold} onChange={(e) => setThreshold(e.target.value)} aria-label="Loss threshold" placeholder="optional" /></label>
          <Button onClick={() => void go()} disabled={busy}>{busy ? "Simulating..." : "Run Monte Carlo"}</Button>
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">
          Shuffle: the same trades in other orders, so the result is fixed and only the drawdown moves.
          Bootstrap: trades drawn again at random, so the result spreads too. Seeded: the same run gives the same answer.
        </p>
        {err && <p role="alert" className="mt-1 text-xs text-[var(--loss)]">{err}</p>}
      </Card>
      {res && (
        <>
          <Card className="p-3 border border-[color:var(--hairline-soft)] overflow-x-auto">
            <table className="w-full text-xs tabular-nums" aria-label="Monte Carlo results" data-testid="mc-table">
              <thead><tr className="text-left text-muted-foreground"><th className="py-1" />
                <th className="text-right">This run</th><th className="text-right">Shuffle 50%</th><th className="text-right">Shuffle 95%</th>
                <th className="text-right">Bootstrap 5%</th><th className="text-right">Bootstrap 50%</th><th className="text-right">Bootstrap 95%</th></tr></thead>
              <tbody>
                <McRow label="Final P&L" actual={money(res.actual.final_pnl)} s={res.shuffle} b={res.bootstrap} f={(m) => m.final_pnl} fmt={money} />
                <McRow label="Max drawdown" actual={pct(res.actual.max_drawdown_pct)} s={res.shuffle} b={res.bootstrap} f={(m) => m.max_drawdown_pct} fmt={pct} />
              </tbody>
            </table>
            <p className="mt-2 text-sm">
              Chance of ending below the starting capital: <b>{pct(res.bootstrap.prob_loss * 100)}</b>
              {res.bootstrap.prob_loss_over != null && <> &middot; of losing more than {money(Number(threshold))}: <b>{pct(res.bootstrap.prob_loss_over * 100)}</b></>}
              <span className="text-muted-foreground"> ({res.runs.toLocaleString()} simulations of {res.trades} trades)</span>
            </p>
          </Card>
          <Card className="p-2 border border-[color:var(--hairline-soft)]">
            <Plot data={[
              { type: "scatter", mode: "lines", x, y: fan!.p95, name: "95%", line: { color: "#22c55e", width: 1 } },
              { type: "scatter", mode: "lines", x, y: fan!.p50, name: "Median", line: { color: "#38bdf8", width: 2 } },
              { type: "scatter", mode: "lines", x, y: fan!.p5, name: "5%", line: { color: "#f0576b", width: 1 } },
            ] as Data[]} layout={{ ...layout, xaxis: { ...layout.xaxis, title: { text: "Trade number" } } }}
              config={{ displaylogo: false }} style={{ width: "100%" }} useResizeHandler />
          </Card>
        </>
      )}
    </div>
  )
}

function McRow({ label, actual, s, b, f, fmt }: {
  label: string; actual: string; s: MonteCarloSide; b: MonteCarloSide
  f: (m: MonteCarloSide) => Record<string, number>; fmt: (n: number) => string
}) {
  return (
    <tr className="border-t border-[color:var(--hairline-soft)]">
      <td className="py-1 text-muted-foreground">{label}</td><td className="text-right font-semibold">{actual}</td>
      <td className="text-right">{fmt(f(s).p50)}</td><td className="text-right">{fmt(f(s).p95)}</td>
      <td className="text-right">{fmt(f(b).p5)}</td><td className="text-right">{fmt(f(b).p50)}</td><td className="text-right">{fmt(f(b).p95)}</td>
    </tr>
  )
}

// ── compare runs ────────────────────────────────────────────────────────────

function CompareRuns({ current }: { current: string | null }) {
  const runsQ = useQuery({ queryKey: ["backtest-list"], queryFn: () => api.listBacktests() })
  const [picked, setPicked] = useState<string[]>(() => (current ? [current] : []))
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length < 4 ? [...p, id] : p))
  const curves = useQueries({ queries: picked.map((id) => ({ queryKey: ["backtest", id, "equity-curve"], queryFn: () => api.getEquityCurve(id) })) })
  const rows = useMemo(() => (runsQ.data ?? []).filter((r) => picked.includes(r.id)), [runsQ.data, picked])
  const layout = useLayout("Equity curves", "Equity ($)")
  const name = (id: string) => { const r = runsQ.data?.find((x) => x.id === id); return r ? `${r.strategy_name} ${r.symbol} ${r.timeframe}` : id }
  return (
    <div className="space-y-3">
      <Card className="p-3 border border-[color:var(--hairline-soft)]">
        <Heading>Pick up to 4 saved runs</Heading>
        <div className="max-h-56 overflow-y-auto">
          <table className="w-full text-xs tabular-nums" aria-label="Saved runs">
            <thead><tr className="text-left text-muted-foreground"><th className="py-1" /><th>Run</th><th>When</th>
              <th className="text-right">Return</th><th className="text-right">Sharpe</th><th className="text-right">Trades</th></tr></thead>
            <tbody>{(runsQ.data ?? []).map((r) => (
              <tr key={r.id} className="border-t border-[color:var(--hairline-soft)]">
                <td className="py-1"><input type="checkbox" checked={picked.includes(r.id)} onChange={() => toggle(r.id)}
                                            aria-label={`Compare ${r.id}`} disabled={!picked.includes(r.id) && picked.length >= 4} /></td>
                <td>{r.strategy_name} {r.symbol} {r.timeframe} <span className="text-muted-foreground">{r.id}</span></td>
                <td className="text-muted-foreground">{r.created_at.slice(0, 16).replace("T", " ")}</td>
                <td className="text-right">{pct(r.total_return_pct)}</td><td className="text-right">{r.sharpe_ratio?.toFixed(2) ?? "n/a"}</td>
                <td className="text-right">{r.total_trades}</td>
              </tr>))}</tbody>
          </table>
          {runsQ.data?.length === 0 && <p className="text-xs text-muted-foreground">No saved runs yet.</p>}
        </div>
      </Card>
      {rows.length > 0 && (
        <Card className="p-3 border border-[color:var(--hairline-soft)] overflow-x-auto">
          <table className="w-full text-xs tabular-nums" aria-label="Comparison" data-testid="compare-table">
            <thead><tr className="text-left text-muted-foreground"><th className="py-1">Run</th><th className="text-right">Return</th>
              <th className="text-right">P&L</th><th className="text-right">Sharpe</th><th className="text-right">Max DD</th>
              <th className="text-right">Win rate</th><th className="text-right">Trades</th></tr></thead>
            <tbody>{picked.map((id, i) => { const r = rows.find((x) => x.id === id); if (!r) return null; return (
              <tr key={id} className="border-t border-[color:var(--hairline-soft)]">
                <td className="py-1 font-semibold" style={{ color: RUN_COLORS[i] }}>{name(id)}</td>
                <td className="text-right">{pct(r.total_return_pct)}</td><td className="text-right">{money(r.total_pnl)}</td>
                <td className="text-right">{r.sharpe_ratio?.toFixed(2) ?? "n/a"}</td><td className="text-right">{pct(r.max_drawdown_pct)}</td>
                <td className="text-right">{pct(r.win_rate)}</td><td className="text-right">{r.total_trades}</td>
              </tr>) })}</tbody>
          </table>
        </Card>
      )}
      {picked.length > 0 && (
        <Card className="p-2 border border-[color:var(--hairline-soft)]">
          <Plot data={picked.map((id, i) => ({
            type: "scatter", mode: "lines", name: name(id), line: { color: RUN_COLORS[i], width: 2 },
            x: (curves[i]?.data ?? []).map((p) => p.t), y: (curves[i]?.data ?? []).map((p) => p.equity),
          })) as Data[]} layout={layout} config={{ displaylogo: false }} style={{ width: "100%" }} useResizeHandler />
        </Card>
      )}
    </div>
  )
}
