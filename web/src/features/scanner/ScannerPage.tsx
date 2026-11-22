/**
 * The futures scanner (upgrade plan, Feature 7): build conditions, run them over the
 * futures list on one timeframe, see which symbols match on their newest bar, and open a
 * match on the chart. Scans can be saved (they travel with the account's settings) and
 * re-run on a timer.
 */
import { useEffect, useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { useConfigStore } from "@/store/configStore"
import { describe, loadScans, saveScans, type SavedScan, type ScanCondition } from "./scanText"

const TIMEFRAMES = ["1m", "3m", "5m", "10m", "15m", "30m", "1h", "4h", "1d"]
const DEFAULT: ScanCondition = { kind: "indicator", name: "rsi2", op: "below", value: 10 }
const sel = "h-8 rounded-lg border border-input bg-transparent px-2 text-sm"

function ConditionEditor({ value, onChange }: { value: ScanCondition; onChange: (c: ScanCondition) => void }) {
  const c = value as Record<string, unknown> & ScanCondition
  const set = (patch: Record<string, unknown>) => onChange({ ...c, ...patch } as ScanCondition)
  const kind = (k: ScanCondition["kind"]) => onChange(({
    indicator: DEFAULT,
    change_pct: { kind: "change_pct", bars: 12, op: "above", value: 0.5 },
    volume_vs_avg: { kind: "volume_vs_avg", op: "above", value: 2 },
    breakout: { kind: "breakout", bars: 20, direction: "high" },
    vwap: { kind: "vwap", position: "above_upper" },
  } as Record<string, ScanCondition>)[k])
  const num = (k: string, w = "w-20") => (
    <Input className={w} type="number" step="any" value={String(c[k])} aria-label={k}
           onChange={(e) => set({ [k]: Number(e.target.value) })} />
  )
  return (
    <div className="flex flex-wrap items-center gap-2">
      <select className={sel} value={c.kind} aria-label="Condition type" onChange={(e) => kind(e.target.value as ScanCondition["kind"])}>
        <option value="indicator">Indicator</option><option value="change_pct">Price change</option>
        <option value="volume_vs_avg">Unusual volume</option><option value="breakout">Breakout</option>
        <option value="vwap">VWAP position</option>
      </select>
      {c.kind === "indicator" && <>
        <select className={sel} value={c.name} aria-label="Indicator" onChange={(e) => set({ name: e.target.value })}>
          <option value="rsi2">RSI(2)</option><option value="rsi13">RSI(13)</option>
          <option value="stochrsi">StochRSI %K</option><option value="mfi">MFI</option></select>
        <select className={sel} value={c.op} aria-label="Comparison" onChange={(e) => set({ op: e.target.value })}>
          <option value="above">above</option><option value="below">below</option>
          <option value="crosses_above">crosses above</option><option value="crosses_below">crosses below</option></select>
        {num("value")}
      </>}
      {c.kind === "change_pct" && <>over {num("bars")} bars
        <select className={sel} value={c.op} aria-label="Comparison" onChange={(e) => set({ op: e.target.value })}>
          <option value="above">above</option><option value="below">below</option></select>{num("value")}%</>}
      {c.kind === "volume_vs_avg" && <>
        <select className={sel} value={c.op} aria-label="Comparison" onChange={(e) => set({ op: e.target.value })}>
          <option value="above">above</option><option value="below">below</option></select>{num("value")}x the 20-bar average</>}
      {c.kind === "breakout" && <>close breaks the {num("bars")}-bar
        <select className={sel} value={c.direction} aria-label="Direction" onChange={(e) => set({ direction: e.target.value })}>
          <option value="high">high</option><option value="low">low</option></select></>}
      {c.kind === "vwap" && (
        <select className={sel} value={c.position} aria-label="VWAP position" onChange={(e) => set({ position: e.target.value })}>
          <option value="above_upper">close above the upper band</option><option value="above_vwap">close above VWAP</option>
          <option value="below_vwap">close below VWAP</option><option value="below_lower">close below the lower band</option></select>)}
    </div>
  )
}

export function ScannerPage() {
  const dataSource = useConfigStore((s) => s.dataSource)
  const setField = useConfigStore((s) => s.setField)
  const goTo = useConfigStore((s) => s.goTo)
  const symbolsQ = useQuery({ queryKey: ["symbols", dataSource], queryFn: () => api.symbols(dataSource) })
  const all = useMemo(() => (symbolsQ.data ?? []).map((s) => s.symbol), [symbolsQ.data])
  const [symbols, setSymbols] = useState<string[]>([])
  useEffect(() => { if (all.length && !symbols.length) setSymbols(all.slice(0, 25)) }, [all, symbols.length])
  const [timeframe, setTimeframe] = useState("5m")
  const [combine, setCombine] = useState<"all" | "any">("all")
  const [conditions, setConditions] = useState<ScanCondition[]>([DEFAULT])
  const [every, setEvery] = useState(0)
  const [saved, setSaved] = useState<SavedScan[]>(loadScans)
  const [name, setName] = useState("")

  const scan = useMutation({
    mutationFn: () => api.runScan({ data_source: dataSource, timeframe, symbols, conditions, combine }),
  })
  useEffect(() => {
    if (!every) return
    const t = setInterval(() => { if (!scan.isPending && !document.hidden) scan.mutate() }, every * 60_000)
    return () => clearInterval(t)
  }, [every, scan])

  const keep = (list: SavedScan[]) => { setSaved(list); saveScans(list) }
  const open = (s: SavedScan) => { setTimeframe(s.timeframe); setCombine(s.combine); setSymbols(s.symbols); setConditions(s.conditions); setName(s.name) }
  const rows = scan.data?.rows ?? []
  const matches = rows.filter((r) => r.matched).length

  return (
    <div className="mx-auto max-w-6xl space-y-3 p-3">
      <Card className="p-3 border border-[color:var(--hairline-soft)]">
        <div className="mb-2 flex flex-wrap items-center gap-3">
          <h1 className="text-base font-semibold">Futures scanner</h1>
          <span className="text-xs text-muted-foreground">Data: {dataSource}. Checked on each symbol's newest bar, which is still forming during market hours.</span>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">Timeframe
            <select className={sel} value={timeframe} onChange={(e) => setTimeframe(e.target.value)} aria-label="Timeframe">
              {TIMEFRAMES.map((t) => <option key={t}>{t}</option>)}</select></label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">Match
            <select className={sel} value={combine} onChange={(e) => setCombine(e.target.value as "all" | "any")} aria-label="Match">
              <option value="all">all conditions</option><option value="any">any condition</option></select></label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">Re-run
            <select className={sel} value={every} onChange={(e) => setEvery(Number(e.target.value))} aria-label="Re-run">
              <option value={0}>by hand</option><option value={1}>every minute</option><option value={5}>every 5 minutes</option>
              <option value={15}>every 15 minutes</option></select></label>
          <Button onClick={() => scan.mutate()} disabled={scan.isPending || !symbols.length || !conditions.length}>
            {scan.isPending ? "Scanning..." : "Run scan"}</Button>
        </div>
        <div className="mt-3 space-y-2">
          {conditions.map((c, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="w-10 text-xs text-muted-foreground">{i === 0 ? "If" : combine === "all" ? "and" : "or"}</span>
              <ConditionEditor value={c} onChange={(n) => setConditions((l) => l.map((x, j) => (j === i ? n : x)))} />
              <button type="button" aria-label={`Remove condition ${i + 1}`} className="text-xs text-muted-foreground hover:text-foreground"
                      onClick={() => setConditions((l) => l.filter((_, j) => j !== i))}>Remove</button>
            </div>
          ))}
          {conditions.length < 10 && <button type="button" className="text-xs underline underline-offset-2"
                                              onClick={() => setConditions((l) => [...l, DEFAULT])}>Add a condition</button>}
        </div>
        <details className="mt-3 text-xs">
          <summary className="cursor-pointer text-muted-foreground">Symbols: {symbols.length} of {all.length} (25 at most a scan)</summary>
          <div className="mt-2 flex flex-wrap gap-2">
            {all.map((s) => (
              <label key={s} className="flex items-center gap-1">
                <input type="checkbox" checked={symbols.includes(s)} disabled={!symbols.includes(s) && symbols.length >= 25}
                       onChange={() => setSymbols((l) => (l.includes(s) ? l.filter((x) => x !== s) : [...l, s]))} />{s}
              </label>))}
          </div>
        </details>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <Input className="w-48" value={name} onChange={(e) => setName(e.target.value)} placeholder="Name this scan" aria-label="Scan name" />
          <Button size="sm" variant="secondary" disabled={!name.trim()} onClick={() => keep([
            ...saved.filter((s) => s.name !== name.trim()),
            { name: name.trim(), timeframe, combine, symbols, conditions }])}>Save scan</Button>
          {saved.map((s) => (
            <span key={s.name} className="flex items-center gap-1 rounded border border-[color:var(--hairline-mid)] px-2 py-0.5">
              <button type="button" className="hover:underline" title={s.conditions.map(describe).join(s.combine === "all" ? " and " : " or ")}
                      onClick={() => open(s)}>{s.name}</button>
              <button type="button" aria-label={`Delete scan ${s.name}`} className="text-muted-foreground hover:text-foreground"
                      onClick={() => keep(saved.filter((x) => x.name !== s.name))}>x</button>
            </span>))}
        </div>
      </Card>

      {scan.error && <p role="alert" className="text-sm text-[var(--loss)]">{(scan.error as Error).message}</p>}
      {scan.data && (
        <Card className="p-3 border border-[color:var(--hairline-soft)] overflow-x-auto">
          <div className="mb-2 text-sm" data-testid="scan-summary">
            <b>{matches}</b> of {rows.length} match{matches === 1 ? "es" : ""}: {conditions.map(describe).join(combine === "all" ? " and " : " or ")}.
            <span className="text-muted-foreground"> Scanned {scan.data.scanned_at.slice(11, 16)}.</span>
          </div>
          <table className="w-full text-xs tabular-nums" aria-label="Scan results">
            <thead><tr className="text-left text-muted-foreground"><th className="py-1">Symbol</th><th>Match</th>
              <th className="text-right">Last</th><th className="pl-4">Bar</th>{conditions.map((c, i) => <th key={i} className="text-right">{describe(c)}</th>)}<th /></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.symbol} className="border-t border-[color:var(--hairline-soft)]">
                <td className="py-1 font-semibold">{r.symbol}</td>
                <td className={r.matched ? "font-bold text-[var(--gain)]" : "text-muted-foreground"}>{r.matched ? "Match" : r.error ? "No data" : "No"}</td>
                <td className="text-right">{r.last?.toFixed(2) ?? ""}</td>
                <td className="pl-4 text-muted-foreground">{r.bar_time?.slice(5, 16).replace("T", " ") ?? r.error}</td>
                {conditions.map((_, i) => { const v = r.values[i]; return (
                  <td key={i} className="text-right" style={{ color: v ? (v.met ? "var(--gain)" : undefined) : undefined }}>
                    {v ? (v.value == null ? "n/a" : v.value.toFixed(2)) + (v.met ? " met" : "") : ""}</td>) })}
                <td className="text-right">{!r.error && <button type="button" className="underline underline-offset-2"
                  onClick={() => { setField("symbol", r.symbol); setField("timeframe", timeframe); goTo("backtest", "price") }}>Chart</button>}</td>
              </tr>))}</tbody>
          </table>
        </Card>
      )}
    </div>
  )
}
