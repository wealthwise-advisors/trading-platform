// The Style menu's panel: chart type, candle colours, background, extended
// hours, space after the last bar and Compare. Every change applies at once
// and is remembered (lib/chartStyle.ts).

import { useEffect, useRef } from "react"
import { CHART_TYPES, DEFAULT_CHART_STYLE, type ChartStyle, type ChartType } from "@/lib/chartStyle"
import { cn } from "@/lib/utils"

const FIELD = "rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-2 py-1 text-foreground"

export function ChartStylePanel({
  style, onChange, onClose, symbols, currentSymbol, className,
}: {
  style: ChartStyle
  onChange: (s: ChartStyle) => void
  onClose: () => void
  /** Symbols Compare can offer. */
  symbols: string[]
  currentSymbol: string
  className?: string
}) {
  const closeRef = useRef<HTMLButtonElement>(null)
  useEffect(() => { closeRef.current?.focus() }, [])
  const set = <K extends keyof ChartStyle>(key: K, value: ChartStyle[K]) => onChange({ ...style, [key]: value })

  return (
    <div role="dialog" aria-label="Chart style"
         onKeyDown={(e) => { if (e.key === "Escape") onClose() }}
         className={cn("w-72 rounded-lg border border-[color:var(--hairline-mid)] bg-[var(--surface-1)] p-3 shadow-xl space-y-3 text-xs", className)}>
      <div className="flex items-center justify-between">
        <span className="font-semibold text-sm">Chart style</span>
        <button ref={closeRef} type="button" onClick={onClose} aria-label="Close"
                className="text-muted-foreground hover:text-foreground">✕</button>
      </div>

      <label className="flex items-center justify-between gap-3">
        <span className="text-muted-foreground">chart type</span>
        <select aria-label="Chart type" value={style.type} className={FIELD}
                onChange={(e) => set("type", e.target.value as ChartType)}>
          {CHART_TYPES.map((c) => <option key={c.id} value={c.id} className="bg-[var(--surface-1)]">{c.label}</option>)}
        </select>
      </label>

      {style.type === "renko" && (
        <label className="flex items-center justify-between gap-3">
          <span className="text-muted-foreground">brick size (blank = auto)</span>
          <input type="number" min={0.25} step={0.25} aria-label="Renko brick size" className={cn(FIELD, "w-20 text-right")}
                 value={style.renkoBrick ?? ""}
                 onChange={(e) => set("renkoBrick", e.target.value === "" ? null : Math.max(0.25, e.target.valueAsNumber || 0.25))} />
        </label>
      )}

      <div className="flex items-center justify-between gap-3">
        <span className="text-muted-foreground">candle colours</span>
        <span className="flex items-center gap-2">
          <input type="color" aria-label="Up colour" value={style.up} onChange={(e) => set("up", e.target.value)} />
          <input type="color" aria-label="Down colour" value={style.down} onChange={(e) => set("down", e.target.value)} />
        </span>
      </div>

      <label className="flex items-center justify-between gap-3 cursor-pointer">
        <span className="text-muted-foreground">thinkorswim maroon background</span>
        <input type="checkbox" aria-label="Maroon background" checked={style.maroon}
               onChange={(e) => set("maroon", e.target.checked)} />
      </label>

      <label className="flex items-center justify-between gap-3 cursor-pointer">
        <span className="text-muted-foreground">shade extended hours</span>
        <input type="checkbox" aria-label="Shade extended hours" checked={style.shadeExtended}
               onChange={(e) => set("shadeExtended", e.target.checked)} />
      </label>

      <label className="flex items-center justify-between gap-3">
        <span className="text-muted-foreground">space after last bar (bars)</span>
        <input type="number" min={0} max={200} aria-label="Space after last bar" className={cn(FIELD, "w-20 text-right")}
               value={style.rightSpace}
               onChange={(e) => set("rightSpace", Math.min(200, Math.max(0, Math.round(e.target.valueAsNumber || 0))))} />
      </label>

      <label className="flex items-center justify-between gap-3">
        <span className="text-muted-foreground">compare with</span>
        <select aria-label="Compare with" value={style.compare ?? ""} className={FIELD}
                onChange={(e) => set("compare", e.target.value || null)}>
          <option value="" className="bg-[var(--surface-1)]">None</option>
          {symbols.filter((s) => s !== currentSymbol).map((s) => (
            <option key={s} value={s} className="bg-[var(--surface-1)]">{s}</option>
          ))}
        </select>
      </label>

      <button type="button" onClick={() => onChange({ ...DEFAULT_CHART_STYLE })}
              className="w-full rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] py-1 hover:bg-[color:var(--raise-4)]">
        Reset to default
      </button>
    </div>
  )
}
