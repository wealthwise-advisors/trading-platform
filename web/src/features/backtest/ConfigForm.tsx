import { useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import {
  useConfigStore, ZIGZAG_DEV_MIN, ZIGZAG_DEV_MAX, ZIGZAG_DEV_STEP,
} from "@/store/configStore"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { SchwabAuthWidget } from "@/components/SchwabAuthWidget"
import { DayCountStepper } from "@/components/DayCountStepper"
import { steppedEndDate } from "@/lib/dayRange"
import { SavedConfigsPanel } from "@/components/SavedConfigsPanel"
import { TimeField } from "@/components/ui/time-field"
import { SymbolMark } from "@/components/SymbolMark"
import { Section, Panel, Choice, FieldRow, SliderField } from "./ConfigParts"
import {
  Settings2, Database, FileSpreadsheet, LineChart, Radio, Clock, Target,
  TrendingUp, Waves, ArrowUpRight, GitCompareArrows, Wallet, Layers, Percent, Play,
} from "lucide-react"

/** Icon and one-line description per data source, keyed on the API's id. */
const SOURCE_META: Record<string, { Icon: typeof Database; note: string }> = {
  synthetic:    { Icon: Database,         note: "Generated bars, no credentials" },
  external_csv: { Icon: FileSpreadsheet,  note: "Your own CSV archive" },
  schwab:       { Icon: LineChart,        note: "Live and recent history" },
  rithmic:      { Icon: Radio,            note: "Real-time streaming" },
}

/** Icon per strategy, keyed on the registry's id. Falls back to the section icon. */
const STRATEGY_ICON: Record<string, typeof Target> = {
  ma_crossover:       TrendingUp,
  rsi_mean_reversion: Waves,
  breakout:           ArrowUpRight,
  rsi_divergence:     GitCompareArrows,
  regime_adaptive:    Settings2,
}

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
      {/* ── panel header ─────────────────────────────────────────────────── */}
      <header className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl
                         border border-violet-400/25 bg-violet-500/10">
          <Settings2 className="h-5 w-5 text-violet-300" aria-hidden />
        </span>
        <div className="min-w-0">
          <h2 className="text-lg font-bold leading-tight">Backtest Config</h2>
          <p className="text-xs text-muted-foreground">Configure your backtest parameters</p>
        </div>
      </header>

      {/* ── data source ──────────────────────────────────────────────────── */}
      <Section icon="source" label="Data Source" accent="blue">
        <Select value={cfg.dataSource} onValueChange={(v) => cfg.setField("dataSource", v)}>
          <SelectTrigger className="w-full h-auto py-2"><SelectValue /></SelectTrigger>
          <SelectContent>
            {(dataSources ?? []).map((ds) => {
              const d = SOURCE_META[ds.id] ?? { Icon: Database, note: "" }
              return (
                <SelectItem key={ds.id} value={ds.id} disabled={!ds.available}>
                  <Choice
                    icon={<d.Icon className="h-4 w-4 text-sky-400" />}
                    title={ds.label + (ds.available ? "" : " (unavailable)")}
                    description={d.note}
                  />
                </SelectItem>
              )
            })}
          </SelectContent>
        </Select>
      </Section>

      {cfg.dataSource === "schwab" && <SchwabAuthWidget />}

      {/* ── symbol ───────────────────────────────────────────────────────── */}
      <Section icon="symbol" label="Symbol" accent="green">
        <Select value={cfg.symbol} onValueChange={(v) => cfg.setField("symbol", v)}>
          <SelectTrigger className="w-full h-auto py-2"><SelectValue /></SelectTrigger>
          <SelectContent>
            {(symbols ?? []).map((s) => (
              <SelectItem key={s.symbol} value={s.symbol}>
                <span className="flex items-center gap-2.5">
                  <SymbolMark symbol={s.symbol} />
                  <span className="font-semibold">{s.symbol}</span>
                  {s.name && s.name !== s.symbol && (
                    <span className="text-muted-foreground">{s.name}</span>
                  )}
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Section>

      {/* ── timeframe ────────────────────────────────────────────────────── */}
      <Section icon="timeframe" label="Timeframe" accent="blue">
        <Select value={cfg.timeframe} onValueChange={(v) => cfg.setField("timeframe", v)}>
          <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
          <SelectContent>
            {/* Same eleven the Live Replay grid offers. This was five, so a backtest
                could not use the intervals a replay could -- and asking for one
                that the provider had no alias for surfaced as a 500. */}
            {["1m", "5m", "10m", "15m", "20m", "25m", "30m", "35m", "40m", "45m", "1h"]
              .map((tf) => (
                <SelectItem key={tf} value={tf}>
                  <span className="flex items-center gap-2">
                    <Clock className="h-3.5 w-3.5 text-sky-400/70" aria-hidden />
                    {tf}
                  </span>
                </SelectItem>
              ))}
          </SelectContent>
        </Select>
      </Section>

      {/* ── strategy ─────────────────────────────────────────────────────── */}
      <Section icon="strategy" label="Strategy" accent="blue">
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
            {(strategies ?? []).map((s) => {
              const Icon = STRATEGY_ICON[s.id] ?? Target
              return (
                <SelectItem key={s.id} value={s.id}>
                  <span className="flex items-center gap-2.5">
                    <Icon className="h-4 w-4 text-violet-300" aria-hidden />
                    {s.label}
                  </span>
                </SelectItem>
              )
            })}
          </SelectContent>
        </Select>
      </Section>

      {/* ── strategy parameters ──────────────────────────────────────────── */}
      {currentStrategy && currentStrategy.params.length > 0 && (
        <Section icon="params" label="Strategy Parameters" accent="violet">
          <Panel>
            {currentStrategy.params.map((p) => (
              <SliderField
                key={p.name}
                label={p.label}
                help={`Range ${p.min}–${p.max}, step ${p.step} · default ${p.default}`}
                value={cfg.params[p.name] ?? p.default}
                onChange={(v) => cfg.setParam(p.name, v)}
                min={p.min} max={p.max} step={p.step}
              />
            ))}
          </Panel>
        </Section>
      )}
      {currentStrategy && currentStrategy.params.length === 0 && (
        <p className="text-xs text-muted-foreground">
          Auto-switches trend-following / mean-reversion / breakout logic based on detected
          market regime. No parameters to tune.
        </p>
      )}

      {/* ── capital & risk ───────────────────────────────────────────────── */}
      <Section icon="capital" label="Capital & Risk" accent="violet">
        <Panel>
          <FieldRow icon={<Wallet className="h-4 w-4 text-violet-300" />} label="Initial Capital ($)">
            <Input type="number" step={10000} value={cfg.initialCapital}
                   onChange={(e) => cfg.setField("initialCapital", Number(e.target.value))} />
          </FieldRow>
          <FieldRow icon={<Layers className="h-4 w-4 text-violet-300" />} label="Contracts per Trade">
            <Input type="number" min={1} max={10} value={cfg.contractsPerTrade}
                   onChange={(e) => cfg.setField("contractsPerTrade", Number(e.target.value))} />
          </FieldRow>
          <FieldRow icon={<Percent className="h-4 w-4 text-violet-300" />} label="Commission / Contract ($)">
            <Input type="number" step={0.25} value={cfg.commission}
                   onChange={(e) => cfg.setField("commission", Number(e.target.value))} />
          </FieldRow>
        </Panel>
      </Section>

      {/* ── date range ───────────────────────────────────────────────────── */}
      <Section icon="dates" label="Date Range" accent="cyan">
        <Panel>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-xs">Start Date</Label>
              <Input type="date" value={cfg.startDate}
                     onChange={(e) => cfg.setField("startDate", e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">End Date</Label>
              <Input type="date" value={cfg.endDate}
                     onChange={(e) => cfg.setField("endDate", e.target.value)} />
            </div>
          </div>

          {/* After the dates, before Timeframe -- the same control and the same
              semantics as Live Replay. It writes the End date; the count itself
              is derived from the range, so the two cannot disagree. */}
          <DayCountStepper
            startDate={cfg.startDate}
            endDate={cfg.endDate}
            onStep={(delta) => {
              // getState() rather than the rendered props: zustand applies
              // each set synchronously, so a burst of clicks composes.
              const live = useConfigStore.getState()
              cfg.setField("endDate", steppedEndDate(live.startDate, live.endDate, delta))
            }}
          />
        </Panel>

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
      </Section>

      {/* ── session hours ────────────────────────────────────────────────── */}
      <Section icon="session" label="Session Hours (EST)" accent="amber">
        <Panel>
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
        </Panel>
      </Section>

      {/* ── zigzag ───────────────────────────────────────────────────────── */}
      <Section icon="zigzag" label="ZigZag Swings" accent="amber">
        <Panel>
          {/* The dots match the chart's dotted lines exactly -- #f0c040 for the
              3-leg series and #2196f3 for the 10-leg -- so it is clear which
              slider moves which line.

              Range from a measured sweep on ES 5m (see src/analysis/zigzag.py):
              at 0.05% (~3.9pt) a session yields ~4-5 minor pivots per major
              swing; below 0.02% the filter stops discriminating and every
              fractal pivot survives. The old 0.05-5 range was calibrated
              against a units bug that made every value 100x weaker than it read. */}
          <SliderField
            label="3-Leg Deviation %"
            dot="#f0c040"
            help="Minimum move, as a percentage, before a new 3-leg swing is recorded. Matches the yellow dotted line on the chart."
            value={cfg.zigzagDev3}
            onChange={(v) => cfg.setField("zigzagDev3", v)}
            min={ZIGZAG_DEV_MIN} max={ZIGZAG_DEV_MAX} step={ZIGZAG_DEV_STEP}
          />
          <SliderField
            label="10-Leg Deviation %"
            dot="#2196f3"
            help="Minimum move, as a percentage, before a new 10-leg swing is recorded. Matches the blue dotted line on the chart."
            value={cfg.zigzagDev10}
            onChange={(v) => cfg.setField("zigzagDev10", v)}
            min={ZIGZAG_DEV_MIN} max={ZIGZAG_DEV_MAX} step={ZIGZAG_DEV_STEP}
          />
        </Panel>
      </Section>

      {/* ── run ──────────────────────────────────────────────────────────── */}
      <Button
        className="w-full bg-gradient-to-r from-violet-600 to-sky-500
                   hover:from-violet-500 hover:to-sky-400
                   text-white font-semibold shadow-lg shadow-violet-900/30"
        size="lg"
        disabled={runMutation.isPending || !rangeIsValid}
        onClick={() => runMutation.mutate()}
      >
        <span className="flex items-center justify-center gap-2">
          <Play className="h-4 w-4 fill-current" aria-hidden />
          {runMutation.isPending ? "Running…" : "Run Backtest"}
        </span>
      </Button>
      {runMutation.isError && (
        <p className="text-xs text-destructive">{(runMutation.error as Error).message}</p>
      )}

      <Separator />
      <SavedConfigsPanel />
    </div>
  )
}
