import { useState } from "react"
import { api } from "@/lib/api"
import { useConfigStore } from "@/store/configStore"
import { Button } from "@/components/ui/button"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import type { OptimizeResponse } from "@/lib/types"
import { GOOD, CRITICAL } from "@/components/cards/StatCard"

const METRICS = [
  { value: "sharpe_ratio", label: "Sharpe Ratio" },
  { value: "total_return_pct", label: "Total Return %" },
  { value: "profit_factor", label: "Profit Factor" },
]

export function OptimizerPanel() {
  const cfg = useConfigStore()
  const [metric, setMetric] = useState<"sharpe_ratio" | "total_return_pct" | "profit_factor">("sharpe_ratio")
  const [status, setStatus] = useState<"idle" | "running" | "done" | "error">("idle")
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<OptimizeResponse | null>(null)

  async function runOptimizer() {
    setStatus("running"); setError(null)
    try {
      const resp = await api.runOptimizer({
        data_source: cfg.dataSource, symbol: cfg.symbol, timeframe: cfg.timeframe,
        strategy_id: cfg.strategyId, initial_capital: cfg.initialCapital,
        contracts_per_trade: cfg.contractsPerTrade, commission_per_contract: cfg.commission,
        start_date: cfg.startDate, end_date: cfg.endDate,
        session_start: cfg.sessionStart, session_end: cfg.sessionEnd, metric,
      })
      setResult(resp)
      setStatus("done")
    } catch (e) {
      setError((e as Error).message)
      setStatus("error")
    }
  }

  function viewWinner() {
    if (result?.best_backtest_id) {
      cfg.setBacktestId(result.best_backtest_id)
      cfg.setLastRunAt(new Date().toISOString())
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Sweeps {cfg.strategyId === "regime_adaptive" ? "this strategy (no tunable parameters)" : "this strategy's own parameter sliders"} through
        the real backtest engine on the current symbol/timeframe/date range from the sidebar, and ranks the results.
        Pure computation, no API call — same engine as a normal backtest, just run many times.
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <Select value={metric} onValueChange={(v) => setMetric(v as typeof metric)} disabled={status === "running"}>
          <SelectTrigger className="w-[180px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            {METRICS.map((m) => <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button onClick={runOptimizer} disabled={status === "running"}>
          {status === "running" ? "Sweeping parameters…" : "✨ Run Optimizer"}
        </Button>
        {result?.best_backtest_id && (
          <Button variant="secondary" onClick={viewWinner}>📊 View Winning Backtest</Button>
        )}
      </div>

      {error && <p className="text-xs text-destructive">{error}</p>}

      {result && (
        <div>
          <p className="text-xs text-muted-foreground mb-2">
            Tested {result.combos_tested} parameter combinations, ranked by {METRICS.find((m) => m.value === result.metric)?.label}.
          </p>
          <div className="overflow-x-auto rounded-lg border border-white/6">
            <table className="w-full text-sm">
              <thead className="bg-[#1a1c24] text-muted-foreground">
                <tr>
                  <th className="text-left p-2 font-medium">#</th>
                  <th className="text-left p-2 font-medium">Parameters</th>
                  <th className="text-right p-2 font-medium">Return %</th>
                  <th className="text-right p-2 font-medium">Sharpe</th>
                  <th className="text-right p-2 font-medium">Win Rate</th>
                  <th className="text-right p-2 font-medium">Trades</th>
                  <th className="text-right p-2 font-medium">Profit Factor</th>
                  <th className="text-right p-2 font-medium">Max DD</th>
                </tr>
              </thead>
              <tbody>
                {result.results.map((c, i) => (
                  <tr key={i} className="border-t border-white/6" style={{ background: i === 0 ? "color-mix(in srgb, #9b8afb 10%, transparent)" : undefined }}>
                    <td className="p-2">{i === 0 ? "🏆" : i + 1}</td>
                    <td className="p-2 text-xs text-muted-foreground">
                      {Object.entries(c.params).map(([k, v]) => `${k}=${v}`).join(", ") || "(no params)"}
                    </td>
                    <td className={`p-2 text-right font-semibold ${c.total_return_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {c.total_return_pct >= 0 ? "+" : ""}{c.total_return_pct.toFixed(1)}%
                    </td>
                    <td className="p-2 text-right">{c.sharpe_ratio.toFixed(2)}</td>
                    <td className="p-2 text-right" style={{ color: c.win_rate >= 50 ? GOOD : CRITICAL }}>{c.win_rate.toFixed(0)}%</td>
                    <td className="p-2 text-right">{c.total_trades}</td>
                    <td className="p-2 text-right">{c.profit_factor.toFixed(2)}</td>
                    <td className="p-2 text-right">{c.max_drawdown_pct.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
