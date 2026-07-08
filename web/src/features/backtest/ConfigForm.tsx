import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { useConfigStore } from "@/store/configStore"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Slider } from "@/components/ui/slider"
import { Separator } from "@/components/ui/separator"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { SchwabAuthWidget } from "@/components/SchwabAuthWidget"
import { SavedConfigsPanel } from "@/components/SavedConfigsPanel"

export function ConfigForm() {
  const cfg = useConfigStore()
  const queryClient = useQueryClient()

  const { data: strategies } = useQuery({ queryKey: ["strategies"], queryFn: api.strategies })
  const { data: dataSources } = useQuery({ queryKey: ["data-sources"], queryFn: api.dataSources })

  const currentStrategy = strategies?.find((s) => s.id === cfg.strategyId)

  const runMutation = useMutation({
    mutationFn: () =>
      api.runBacktest({
        data_source: cfg.dataSource,
        symbol: cfg.symbol,
        timeframe: cfg.timeframe,
        strategy_id: cfg.strategyId,
        params: cfg.params,
        initial_capital: cfg.initialCapital,
        contracts_per_trade: cfg.contractsPerTrade,
        commission_per_contract: cfg.commission,
        start_date: cfg.startDate,
        end_date: cfg.endDate,
        session_start: cfg.sessionStart,
        session_end: cfg.sessionEnd,
        zigzag_dev_3: cfg.zigzagDev3 / 100,
        zigzag_dev_10: cfg.zigzagDev10 / 100,
      }),
    onSuccess: (summary) => {
      cfg.setBacktestId(summary.backtest_id)
      cfg.setLastRunAt(new Date().toISOString())
      queryClient.invalidateQueries({ queryKey: ["backtest", summary.backtest_id] })
    },
  })

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-bold flex items-center gap-2">⚙️ Backtest Config</h2>
      </div>
      <Separator />

      <div className="space-y-2">
        <Label>Data Source</Label>
        <Select value={cfg.dataSource} onValueChange={(v) => cfg.setField("dataSource", v)}>
          <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
          <SelectContent>
            {(dataSources ?? []).map((ds) => (
              <SelectItem key={ds.id} value={ds.id} disabled={!ds.available}>
                {ds.label}{!ds.available ? " (unavailable)" : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {cfg.dataSource === "schwab" && <SchwabAuthWidget />}

      <div className="space-y-2">
        <Label>Symbol</Label>
        <Select value={cfg.symbol} onValueChange={(v) => cfg.setField("symbol", v)}>
          <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
          <SelectContent>
            {["ES", "NQ", "MES", "CL"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Timeframe</Label>
        <Select value={cfg.timeframe} onValueChange={(v) => cfg.setField("timeframe", v)}>
          <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
          <SelectContent>
            {["1m", "5m", "15m", "30m", "1h"].map((tf) => <SelectItem key={tf} value={tf}>{tf}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Strategy</Label>
        <Select
          value={cfg.strategyId}
          onValueChange={(v) => {
            cfg.setField("strategyId", v)
            const s = strategies?.find((x) => x.id === v)
            if (s) cfg.setParams(Object.fromEntries(s.params.map((p) => [p.name, p.default])))
          }}
        >
          <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
          <SelectContent>
            {(strategies ?? []).map((s) => <SelectItem key={s.id} value={s.id}>{s.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {currentStrategy && currentStrategy.params.length > 0 && (
        <div className="space-y-4">
          <Label className="text-muted-foreground text-xs uppercase tracking-wide">Strategy Parameters</Label>
          {currentStrategy.params.map((p) => (
            <div key={p.name} className="space-y-1">
              <div className="flex justify-between text-sm">
                <span>{p.label}</span>
                <span className="font-mono text-muted-foreground">{cfg.params[p.name] ?? p.default}</span>
              </div>
              <Slider
                min={p.min} max={p.max} step={p.step}
                value={[cfg.params[p.name] ?? p.default]}
                onValueChange={([v]) => cfg.setParam(p.name, v)}
              />
            </div>
          ))}
        </div>
      )}
      {currentStrategy && currentStrategy.params.length === 0 && (
        <p className="text-xs text-muted-foreground">
          Auto-switches trend-following / mean-reversion / breakout logic based on detected
          market regime. No parameters to tune.
        </p>
      )}

      <Separator />
      <Label className="text-muted-foreground text-xs uppercase tracking-wide">Capital & Risk</Label>
      <div className="space-y-2">
        <Label>Initial Capital ($)</Label>
        <Input type="number" step={10000} value={cfg.initialCapital}
               onChange={(e) => cfg.setField("initialCapital", Number(e.target.value))} />
      </div>
      <div className="space-y-2">
        <Label>Contracts per Trade</Label>
        <Input type="number" min={1} max={10} value={cfg.contractsPerTrade}
               onChange={(e) => cfg.setField("contractsPerTrade", Number(e.target.value))} />
      </div>
      <div className="space-y-2">
        <Label>Commission / Contract ($)</Label>
        <Input type="number" step={0.25} value={cfg.commission}
               onChange={(e) => cfg.setField("commission", Number(e.target.value))} />
      </div>

      <Separator />
      <Label className="text-muted-foreground text-xs uppercase tracking-wide">Date Range</Label>
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <Label className="text-xs">Start</Label>
          <Input type="date" value={cfg.startDate} onChange={(e) => cfg.setField("startDate", e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">End</Label>
          <Input type="date" value={cfg.endDate} onChange={(e) => cfg.setField("endDate", e.target.value)} />
        </div>
      </div>

      <Separator />
      <Label className="text-muted-foreground text-xs uppercase tracking-wide">Session Hours (EST)</Label>
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <Label className="text-xs">From</Label>
          <Input type="time" value={cfg.sessionStart} onChange={(e) => cfg.setField("sessionStart", e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">To</Label>
          <Input type="time" value={cfg.sessionEnd} onChange={(e) => cfg.setField("sessionEnd", e.target.value)} />
        </div>
      </div>

      <Separator />
      <Label className="text-muted-foreground text-xs uppercase tracking-wide">ZigZag Swings</Label>
      <div className="space-y-1">
        <div className="flex justify-between text-sm">
          <span>3-Leg Deviation %</span><span className="font-mono text-muted-foreground">{cfg.zigzagDev3.toFixed(2)}</span>
        </div>
        <Slider min={0.05} max={5} step={0.05} value={[cfg.zigzagDev3]}
                onValueChange={([v]) => cfg.setField("zigzagDev3", v)} />
      </div>
      <div className="space-y-1">
        <div className="flex justify-between text-sm">
          <span>10-Leg Deviation %</span><span className="font-mono text-muted-foreground">{cfg.zigzagDev10.toFixed(2)}</span>
        </div>
        <Slider min={0.05} max={5} step={0.05} value={[cfg.zigzagDev10]}
                onValueChange={([v]) => cfg.setField("zigzagDev10", v)} />
      </div>

      <Separator />
      <Button
        className="w-full"
        size="lg"
        disabled={runMutation.isPending}
        onClick={() => runMutation.mutate()}
      >
        {runMutation.isPending ? "Running…" : "▶ Run Backtest"}
      </Button>
      {runMutation.isError && (
        <p className="text-xs text-destructive">{(runMutation.error as Error).message}</p>
      )}

      <Separator />
      <SavedConfigsPanel />
    </div>
  )
}
