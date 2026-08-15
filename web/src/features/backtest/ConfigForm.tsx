import { useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import {
  useConfigStore, ZIGZAG_DEV_MIN, ZIGZAG_DEV_MAX, ZIGZAG_DEV_STEP,
} from "@/store/configStore"
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
import { TimeField } from "@/components/ui/time-field"

export function ConfigForm() {
  const cfg = useConfigStore()
  const queryClient = useQueryClient()

  const { data: strategies } = useQuery({ queryKey: ["strategies"], queryFn: api.strategies })
  const { data: dataSources } = useQuery({ queryKey: ["data-sources"], queryFn: api.dataSources })
  // Symbols depend on the source: external_csv reports what is on disk,
  // synthetic reports what the generator can model. Re-fetched on change.
  const { data: symbols } = useQuery({
    queryKey: ["symbols", cfg.dataSource],
    queryFn: () => api.symbols(cfg.dataSource),
  })

  // Switching source can strand the form on a symbol the new source cannot
  // serve -- e.g. NVDA selected under CSV, then switching to synthetic. Snap
  // to the first valid option instead of posting a request that will 404.
  const { setField, symbol: selectedSymbol } = cfg
  useEffect(() => {
    if (!symbols || symbols.length === 0) return
    if (!symbols.some((s) => s.symbol === selectedSymbol)) {
      setField("symbol", symbols[0].symbol)
    }
  }, [symbols, selectedSymbol, setField])

  // Windows the selected symbol actually has data for. Only file-backed
  // sources report this; synthetic generates whatever range is asked for, so
  // an absent/empty coverage list means "any date is fine".
  const coverage = symbols?.find((s) => s.symbol === selectedSymbol)?.coverage ?? []
  const overlapsCoverage = (from: string, to: string) =>
    coverage.length === 0 || coverage.some((w) => from <= w.end && to >= w.start)

  // The store defaults the range to the last trading day, which is right for
  // synthetic data (generated on demand) and wrong for a file: the bundled ES
  // sample stops in Jan 2025, so the out-of-the-box range produced
  // "No bars found for ES between 2026-08-07 ... and ...". Snap into the most
  // recent window that exists whenever the current range misses entirely.
  // Deliberately only when it MISSES -- a range the user chose that does hold
  // data is never overwritten.
  const { startDate, endDate } = cfg
  useEffect(() => {
    if (coverage.length === 0) return
    if (overlapsCoverage(startDate, endDate)) return
    const latest = coverage[coverage.length - 1]
    setField("startDate", latest.start)
    setField("endDate", latest.end)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSymbol, cfg.dataSource, symbols])

  const rangeIsValid = overlapsCoverage(startDate, endDate)
  const coverageHint = coverage.map((w) => `${w.start} → ${w.end}`).join("  ·  ")

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
        // null on both edges tells the engine to skip session filtering.
        session_start: cfg.session24h ? null : cfg.sessionStart,
        session_end: cfg.session24h ? null : cfg.sessionEnd,
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
            {(symbols ?? []).map((s) => (
              <SelectItem key={s.symbol} value={s.symbol}>
                {s.symbol}{s.name && s.name !== s.symbol ? ` — ${s.name}` : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Timeframe</Label>
        <Select value={cfg.timeframe} onValueChange={(v) => cfg.setField("timeframe", v)}>
          <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
          <SelectContent>
            {/* Same eleven the Live Replay grid offers. This was five, so a backtest
                could not use the intervals a replay could -- and asking for one
                that the provider had no alias for surfaced as a 500. */}
            {["1m", "5m", "10m", "15m", "20m", "25m", "30m", "35m", "40m", "45m", "1h"]
              .map((tf) => <SelectItem key={tf} value={tf}>{tf}</SelectItem>)}
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
      {/* Say what this symbol actually covers, rather than letting the user
          discover it from a failed request. Shown as a plain hint normally,
          and escalated when the chosen range falls outside every window. */}
      {coverage.length > 0 && (
        rangeIsValid ? (
          <p className="text-xs text-muted-foreground">
            {selectedSymbol} data available: {coverageHint}
          </p>
        ) : (
          <p className="text-xs text-destructive">
            No {selectedSymbol} data in this range. Available: {coverageHint}
          </p>
        )
      )}

      <Separator />
      <Label className="text-muted-foreground text-xs uppercase tracking-wide">Session Hours (EST)</Label>
      {/* 24-hour keeps every bar. It is not just a viewing preference: BTC
          trades continuously, so a 09:30-16:00 window silently discards 54%
          of its bars and changes the backtest, not only the chart. */}
      <label className="flex items-center gap-2 cursor-pointer text-xs">
        <input
          type="checkbox"
          checked={cfg.session24h}
          onChange={(e) => cfg.setField("session24h", e.target.checked)}
        />
        <span>24 hours <span className="text-muted-foreground">(keep every bar — crypto, pre/post-market)</span></span>
      </label>
      <div className={`grid grid-cols-2 gap-2 ${cfg.session24h ? "opacity-40" : ""}`}>
        <div className="space-y-1">
          <Label className="text-xs">From</Label>
          <TimeField value={cfg.sessionStart} disabled={cfg.session24h}
                     label="Session start"
                     onChange={(v) => cfg.setField("sessionStart", v)} />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">To</Label>
          <TimeField value={cfg.sessionEnd} disabled={cfg.session24h}
                     label="Session end"
                     onChange={(v) => cfg.setField("sessionEnd", v)} />
        </div>
      </div>

      <Separator />
      <Label className="text-muted-foreground text-xs uppercase tracking-wide">ZigZag Swings</Label>
      <div className="space-y-1">
        <div className="flex justify-between text-sm">
          {/* Yellow/gold dot matches the chart's "ZigZag (3L)" dotted line
              color (#f0c040) exactly, so it's clear which slider controls
              which line on the chart. */}
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-2 h-2 rounded-full shrink-0" style={{ background: "#f0c040" }} />
            3-Leg Deviation % <span className="text-muted-foreground">(yellow line)</span>
          </span>
          <span className="font-mono text-muted-foreground">{cfg.zigzagDev3.toFixed(2)}</span>
        </div>
        {/* Range chosen from a measured sweep on ES 5m (see
            src/analysis/zigzag.py). At 0.05% (~3.9pt) a session yields ~4-5
            minor pivots per major swing; below 0.02% the filter stops
            discriminating and every fractal pivot survives. The old
            0.05-5 range was calibrated against a units bug that made every
            value 100x weaker than it read. */}
        <Slider min={ZIGZAG_DEV_MIN} max={ZIGZAG_DEV_MAX} step={ZIGZAG_DEV_STEP}
                value={[cfg.zigzagDev3]}
                onValueChange={([v]) => cfg.setField("zigzagDev3", v)} />
      </div>
      <div className="space-y-1">
        <div className="flex justify-between text-sm">
          {/* Blue dot matches the chart's "ZigZag (10L)" dotted line color
              (#2196f3) exactly. */}
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-2 h-2 rounded-full shrink-0" style={{ background: "#2196f3" }} />
            10-Leg Deviation % <span className="text-muted-foreground">(blue line)</span>
          </span>
          <span className="font-mono text-muted-foreground">{cfg.zigzagDev10.toFixed(2)}</span>
        </div>
        <Slider min={ZIGZAG_DEV_MIN} max={ZIGZAG_DEV_MAX} step={ZIGZAG_DEV_STEP}
                value={[cfg.zigzagDev10]}
                onValueChange={([v]) => cfg.setField("zigzagDev10", v)} />
      </div>

      <Separator />
      <Button
        className="w-full"
        size="lg"
        disabled={runMutation.isPending || !rangeIsValid}
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
