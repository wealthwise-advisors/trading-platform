import { useEffect, useState } from "react"
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
import {
  ALL_CHART_TIMEFRAMES, maxRangeDaysFor, startDateForTimeframe,
} from "@/lib/chartSetup"
import { steppedEndDate, startDateForDays } from "@/lib/dayRange"
import {
  SESSION_ZONES, fromZone, loadZoneOffset, saveZoneOffset, toZone, zoneShort,
} from "@/lib/sessionZone"
import { SavedConfigsPanel } from "@/components/SavedConfigsPanel"
import { TimeField } from "@/components/ui/time-field"
import { DateField } from "@/components/ui/date-field"
import { SymbolOption } from "@/components/SymbolOption"
import { InstrumentPicker } from "@/components/InstrumentPicker"
import { IntervalPicker } from "@/components/IntervalPicker"
import { SourceMark } from "@/components/SourceMark"
import { StrategyMark } from "@/components/StrategyMark"
import {
  Section, Panel, Choice, FieldRow, SliderField, ToggleSwitch, QuickPresets,
} from "./ConfigParts"
import {
  Settings2, Database, FileSpreadsheet, LineChart, Radio, Clock,
  Wallet, Layers, Percent, Play, ChevronsLeft, ChevronsUpDown,
} from "lucide-react"

/** Icon and one-line description per data source, keyed on the API's id. */
const SOURCE_META: Record<string, { Icon: typeof Database; note: string }> = {
  synthetic:    { Icon: Database,         note: "Generated bars, no credentials" },
  external_csv: { Icon: FileSpreadsheet,  note: "Your own CSV archive" },
  schwab:       { Icon: LineChart,        note: "Live and recent history" },
  rithmic:      { Icon: Radio,            note: "Real-time streaming" },
}


/**
 * A strategy parameter's slider colour, where the name says what it is: an
 * overbought level in red and an oversold level in green, the colours the
 * chart draws those two lines in. Anything else takes the section's orange.
 */
function paramColor(name: string): string | undefined {
  if (/overbought/i.test(name)) return "#f87171"
  if (/oversold/i.test(name)) return "#34d399"
  return undefined
}

/** `onCollapse` is display-only: it hides the panel, and changes nothing about
 *  the configuration or the request. Omitted, the chevron is not rendered. */
export function ConfigForm({ onCollapse }: { onCollapse?: () => void } = {}) {
  const cfg = useConfigStore()
  const queryClient = useQueryClient()
  /**
   * Which clock the two Session Hours fields are typed and shown in.
   *
   * Display only: cfg.sessionStart / cfg.sessionEnd stay EASTERN, because that
   * is what the backend filters on and what anchors VWAP. See lib/sessionZone.
   * Read from storage once, on the initialiser, so a reload keeps the choice
   * without a second render that flashes Eastern first.
   */
  const [zoneOffset, setZoneOffset] = useState(loadZoneOffset)

  const { data: strategies } = useQuery({ queryKey: ["strategies"], queryFn: api.strategies })
  const { data: dataSources } = useQuery({ queryKey: ["data-sources"], queryFn: api.dataSources })
  // Symbols depend on the source: external_csv reports what is on disk,
  // synthetic reports what the generator can model. Re-fetched on change.
  const { data: symbols } = useQuery({
    queryKey: ["symbols", cfg.dataSource],
    queryFn: () => api.symbols(cfg.dataSource),
  })

  const [pickerOpen, setPickerOpen] = useState(false)
  const current = (symbols ?? []).find((s) => s.symbol === cfg.symbol)

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
    // cfg-scope: this panel's palette, and the same class on every popup it
    // opens -- see "Backtest Config palette" in index.css.
    <div className="cfg-scope space-y-5">
      {/* ── panel header ─────────────────────────────────────────────────── */}
      <header className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl
                         border border-blue-400/25 bg-blue-500/10">
          <Settings2 className="h-5 w-5 text-blue-300" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-bold leading-tight">Backtest Config</h2>
          <p className="text-xs text-muted-foreground">Configure your backtest parameters</p>
        </div>
        {onCollapse && (
          <button
            type="button"
            onClick={onCollapse}
            title="Hide the config panel"
            aria-label="Hide the config panel"
            className="shrink-0 rounded-lg p-1.5 text-muted-foreground transition-colors
                       hover:bg-white/[0.06] hover:text-foreground"
          >
            <ChevronsLeft className="h-5 w-5" aria-hidden />
          </button>
        )}
      </header>
      <div className="h-px bg-white/8" />

      {/* ── data source ──────────────────────────────────────────────────── */}
      <Section icon="source" label="Data Source" accent="sky">
        <Select value={cfg.dataSource} onValueChange={(v) => cfg.setField("dataSource", v)}>
          <SelectTrigger className="w-full h-auto py-2"><SelectValue /></SelectTrigger>
          <SelectContent className="cfg-scope">
            {(dataSources ?? []).map((ds) => {
              const d = SOURCE_META[ds.id] ?? { Icon: Database, note: "" }
              return (
                <SelectItem key={ds.id} value={ds.id} disabled={!ds.available}>
                  <Choice
                    icon={<SourceMark id={ds.id} size={18} />}
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
      <Section icon="symbol" label="Symbol" accent="teal">
        {/* A dropdown was fine at five symbols. Schwab offers twenty-one across
            five asset classes, which is a list you hunt rather than scan --
            hence a searchable dialog with the same row markup inside. */}
        <button
          type="button"
          onClick={() => setPickerOpen(true)}
          className="instr-trigger"
          aria-haspopup="dialog"
          title="Choose the instrument to run against"
        >
          {current
            ? <SymbolOption s={current} />
            : <span className="text-muted-foreground">Choose an instrument…</span>}
          <ChevronsUpDown size={15} strokeWidth={2} className="ml-2 shrink-0 text-slate-500" />
        </button>
        <InstrumentPicker
          open={pickerOpen}
          onOpenChange={setPickerOpen}
          symbols={symbols ?? []}
          value={cfg.symbol}
          onSelect={(v) => cfg.setField("symbol", v)}
          sourceLabel={(dataSources ?? []).find((d) => d.id === cfg.dataSource)?.label}
          className="cfg-scope"
        />
      </Section>

      {/* ── timeframe ────────────────────────────────────────────────────── */}
      <Section icon="timeframe" label="Timeframe Selector" accent="blue">
        <Select
          value={cfg.timeframe}
          onValueChange={(v) => {
            cfg.setField("timeframe", v)
            // Move the START back, keeping the end date where it is: the
            // preset is "the last N days", and the end is usually the most
            // recent session the source can serve. Moving the end instead
            // would walk the window off the live edge.
            //
            // A timeframe with no preset leaves the range untouched rather
            // than falling back to a number nobody chose -- unless the range is
            // longer than it can be served (after Daily's twenty years).
            const start = startDateForTimeframe(cfg.endDate, v, cfg.startDate)
            if (start) cfg.setField("startDate", start)
          }}
        >
          <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
          {/* position="popper" opens the list BELOW the box. The default,
              item-aligned, slides the list up so the current value sits over
              the box -- which covered this section's own heading and left the
              SYMBOL heading above it, so the timeframe list read as a symbol
              list. */}
          <SelectContent position="popper" className="cfg-scope">
            {/* Same list the Live Replay grid offers. This was five, so a backtest
                could not use the intervals a replay could -- and asking for one
                that the provider had no alias for surfaced as a 500. */}
            {/* The interval only. The day count each timeframe loads is still
                applied when one is picked (see onValueChange above) -- it is
                just no longer printed beside the option. */}
            {ALL_CHART_TIMEFRAMES.map((tf) => (
              <SelectItem key={tf} value={tf}>
                <span className="flex items-center gap-2 w-full">
                  <Clock className="h-3.5 w-3.5 text-slate-400" aria-hidden />
                  {tf}
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Section>

      {/* ── interval picker ──────────────────────────────────────────────── */}
      {/* A second control for the SAME setting as the Timeframe Selector above,
          styled after thinkorswim's interval selector: favorites, a custom
          order, and the day count beside each row. Both read cfg.timeframe, so
          they always agree, and picking in either one runs the same two steps.
          Keep this handler identical to the Selector's onValueChange -- if one
          changes and the other does not, the two controls stop being one
          setting. */}
      <Section icon="timeframe" label="Interval Picker" accent="steel">
        <IntervalPicker
          value={cfg.timeframe}
          onChange={(v) => {
            cfg.setField("timeframe", v)
            const start = startDateForTimeframe(cfg.endDate, v, cfg.startDate)
            if (start) cfg.setField("startDate", start)
          }}
        />
      </Section>

      {/* ── strategy ─────────────────────────────────────────────────────── */}
      <Section icon="strategy" label="Strategy" accent="green">
        <Select
          value={cfg.strategyId}
          onValueChange={(v) => {
            cfg.setField("strategyId", v)
            const s = strategies?.find((x) => x.id === v)
            if (s) cfg.setParams(Object.fromEntries(s.params.map((p) => [p.name, p.default])))
          }}
        >
          <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
          <SelectContent className="cfg-scope">
            {(strategies ?? []).map((s) => {
              return (
                <SelectItem key={s.id} value={s.id}>
                  <span className="flex items-center gap-2.5">
                    <StrategyMark id={s.id} size={18} />
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
        <Section icon="params" label="Strategy Parameters" accent="orange">
          <Panel>
            {currentStrategy.params.map((p) => (
              <SliderField
                key={p.name}
                label={p.label}
                color={paramColor(p.name)}
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
      <Section icon="capital" label="Capital & Risk" accent="blue">
        <Panel>
          <FieldRow icon={<Wallet className="h-4 w-4 text-[#60a5fa]" />} label="Initial Capital ($)">
            <Input type="number" step={10000} value={cfg.initialCapital}
                   onChange={(e) => cfg.setField("initialCapital", Number(e.target.value))} />
          </FieldRow>
          <FieldRow icon={<Layers className="h-4 w-4 text-[#2dd4bf]" />} label="Contracts per Trade">
            <Input type="number" min={1} max={10} value={cfg.contractsPerTrade}
                   onChange={(e) => cfg.setField("contractsPerTrade", Number(e.target.value))} />
          </FieldRow>
          <FieldRow icon={<Percent className="h-4 w-4 text-[#fb7185]" />} label="Commission / Contract ($)">
            <Input type="number" step={0.25} value={cfg.commission}
                   onChange={(e) => cfg.setField("commission", Number(e.target.value))} />
          </FieldRow>
        </Panel>
      </Section>

      {/* ── date range ───────────────────────────────────────────────────── */}
      <Section icon="dates" label="Date Range" accent="teal">
        <Panel>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-xs">Start Date</Label>
              <DateField label="Start date" value={cfg.startDate} tone="teal" popoverClassName="cfg-scope"
                         onChange={(v) => cfg.setField("startDate", v)} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">End Date</Label>
              <DateField label="End date" value={cfg.endDate} tone="teal" popoverClassName="cfg-scope"
                         onChange={(v) => cfg.setField("endDate", v)} />
            </div>
          </div>

          {/* After the dates, before Timeframe -- the same control and the same
              semantics as Live Replay. It writes the End date; the count itself
              is derived from the range, so the two cannot disagree. */}
          {/* Shortcuts over the same two fields the pickers write -- the end date
              stays where it is and the start moves back, which is what "last 5
              days" means when the end is today. */}
          <QuickPresets
            onPick={(days) => {
              const live = useConfigStore.getState()
              const start = startDateForDays(live.endDate, days)
              if (start) cfg.setField("startDate", start)
            }}
          />

          <DayCountStepper
            startDate={cfg.startDate}
            endDate={cfg.endDate}
            maxDays={maxRangeDaysFor(cfg.timeframe)}
            onStep={(delta) => {
              // getState() rather than the rendered props: zustand applies
              // each set synchronously, so a burst of clicks composes.
              const live = useConfigStore.getState()
              cfg.setField("endDate",
                steppedEndDate(live.startDate, live.endDate, delta, maxRangeDaysFor(live.timeframe)))
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
      <Section icon="session" label={`Session Hours (${zoneShort(zoneOffset)})`} accent="ember">
        <Panel>
          {/* 24-hour keeps every bar. It is not just a viewing preference: BTC
              trades continuously, so a 09:30-16:00 window silently discards 54%
              of its bars and changes the backtest, not only the chart. */}
          <ToggleSwitch
            checked={cfg.session24h}
            onChange={(v) => cfg.setField("session24h", v)}
            label="24 hours"
            hint="(keep every bar — crypto, pre/post-market)"
          />
          {/* WHICH CLOCK THE TWO FIELDS SPEAK.
              The same four pills as the Market Grid's tape, from the same list,
              so ET/CT/MT/PT mean one thing across the app. Choosing a zone
              RELABELS this window rather than moving it: the stored pair stays
              Eastern (lib/sessionZone explains why), so switching to CT cannot
              quietly change which bars the next backtest runs on. */}
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-slate-500 font-medium whitespace-nowrap">
              Times in
            </span>
            <div className="flex gap-1">
              {SESSION_ZONES.map((z) => (
                <button
                  key={z.short} type="button"
                  aria-pressed={zoneOffset === z.offset}
                  aria-label={`times in ${z.short}`}
                  title={z.label}
                  className={`tz-pill${zoneOffset === z.offset ? " tz-pill-on" : ""}`}
                  onClick={() => { setZoneOffset(z.offset); saveZoneOffset(z.offset) }}
                >
                  {z.short}
                </button>
              ))}
            </div>
          </div>
          {/* --primary here is Session Hours' restrained orange: the AM / PM
              toggle and the hover border inside TimeField draw in primary. */}
          <div className={`grid grid-cols-2 gap-2 ${cfg.session24h ? "opacity-40" : ""}`}
               style={{ "--primary": "#e9a26b" } as React.CSSProperties}>
            <div className="space-y-1">
              <Label className="text-xs">From</Label>
              <TimeField value={toZone(cfg.sessionStart, zoneOffset)} disabled={cfg.session24h}
                         label="Session start"
                         onChange={(v) => cfg.setField("sessionStart", fromZone(v, zoneOffset))} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">To</Label>
              <TimeField value={toZone(cfg.sessionEnd, zoneOffset)} disabled={cfg.session24h}
                         label="Session end"
                         onChange={(v) => cfg.setField("sessionEnd", fromZone(v, zoneOffset))} />
            </div>
          </div>
          {/* Shown only off Eastern, and it states the pair actually sent. The
              report, a saved config and the VWAP anchor all speak Eastern, so
              someone working in CT needs to see both numbers to reconcile them
              -- otherwise a report reading 09:30 looks like it ignored the
              08:30 that was typed. */}
          {zoneOffset !== 0 && !cfg.session24h && (
            <p className="text-[11px] text-muted-foreground">
              Runs as <span className="font-mono">{cfg.sessionStart}–{cfg.sessionEnd} ET</span>
              {" "}— the exchange clock the results and VWAP are anchored to.
            </p>
          )}
        </Panel>
      </Section>

      {/* ── zigzag ───────────────────────────────────────────────────────── */}
      <Section icon="zigzag" label="ZigZag Swings" accent="violet">
        <Panel>
          {/* The dots tell the two sliders apart. The 10-leg dot is the chart's
              #2196f3. The 3-leg dot is the section's purple rather than the
              chart's #f0c040 line: the config palette carries no yellow or gold
              (2026-09-15), so the help text names the line's colour instead.

              Range from a measured sweep on ES 5m (see src/analysis/zigzag.py):
              at 0.05% (~3.9pt) a session yields ~4-5 minor pivots per major
              swing; below 0.02% the filter stops discriminating and every
              fractal pivot survives. The old 0.05-5 range was calibrated
              against a units bug that made every value 100x weaker than it read. */}
          <SliderField
            label="3-Leg Deviation %"
            dot="#a78bfa"
            help="Minimum move, as a percentage, before a new 3-leg swing is recorded. Drawn on the chart as the yellow dotted line."
            value={cfg.zigzagDev3}
            onChange={(v) => cfg.setField("zigzagDev3", v)}
            min={ZIGZAG_DEV_MIN} max={ZIGZAG_DEV_MAX} step={ZIGZAG_DEV_STEP}
          />
          <SliderField
            label="10-Leg Deviation %"
            dot="#2196f3"
            color="#2196f3"
            help="Minimum move, as a percentage, before a new 10-leg swing is recorded. Matches the blue dotted line on the chart."
            value={cfg.zigzagDev10}
            onChange={(v) => cfg.setField("zigzagDev10", v)}
            min={ZIGZAG_DEV_MIN} max={ZIGZAG_DEV_MAX} step={ZIGZAG_DEV_STEP}
          />
        </Panel>
      </Section>

      {/* ── run ──────────────────────────────────────────────────────────── */}
      <Button
        // bg-none and hover:shadow-lg: the Button's default variant paints a
        // violet gradient and glow over any background colour set here.
        className="w-full h-12 rounded-xl bg-none bg-[#2563eb] hover:bg-[#1d4ed8]
                   text-white text-base font-semibold
                   shadow-lg shadow-blue-900/40 hover:shadow-lg transition-colors"
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
