/**
 * What every line, band and marker on the price chart means -- on demand.
 *
 * WHY THIS REPLACED A BLOCK DRAWN ON THE CHART. The EMA / VWAP readout used to
 * be painted over the top-left of the plot, permanently. It cost roughly 200px
 * of width and 90px of height of the only region on the page where pixels buy
 * you anything, and it covered the candles it was describing. A reading you
 * glance at occasionally does not earn permanent space in front of the thing
 * you are actually looking at.
 *
 * So the same numbers live here, one click away, next to a key that the
 * readout never had: which colour is EMA 9, which dotted line is the 3-leg
 * ZigZag, what the circles round the swings mean, which marker is an entry and
 * which an exit.
 *
 * THE SWATCHES ARE DRAWN FROM THE SAME VALUES THE TRACES USE. Every colour,
 * dash and marker shape is passed in by the chart from the object it hands to
 * Plotly -- nothing here holds a second copy of the palette. A legend that
 * keeps its own idea of what colour EMA 9 is will eventually be wrong, and a
 * legend that is wrong is worse than none.
 */

import { useEffect, useRef, useState } from "react"
import { ChevronDown, List } from "lucide-react"

/** How a series is drawn, so the swatch can look like the thing it names. */
export type LegendKind = "line" | "dash" | "dot" | "band" | "marker"

export interface LegendEntry {
  label: string
  color: string
  kind: LegendKind
  /** Marker shape, for kind "marker". Matches the Plotly symbol names used. */
  symbol?: "triangle-up" | "x" | "circle"
  /**
   * The series' latest reading, where it has one. Omitted entirely rather
   * than zeroed when a series has no value yet -- see the em dash in the
   * chart's own formatter.
   */
  value?: string
  /** One line on what it is, for anything whose name does not say it. */
  note?: string
}

/** A 22x10 sample of the trace, drawn the way the chart draws it. */
function Swatch({ e }: { e: LegendEntry }) {
  const common = { stroke: e.color, strokeWidth: 2, fill: "none" } as const
  return (
    <svg width="22" height="10" viewBox="0 0 22 10" aria-hidden className="shrink-0">
      {e.kind === "line" && <line x1="1" y1="5" x2="21" y2="5" {...common} />}
      {e.kind === "dash" && <line x1="1" y1="5" x2="21" y2="5" {...common} strokeDasharray="5 3" />}
      {e.kind === "dot" && <line x1="1" y1="5" x2="21" y2="5" {...common} strokeDasharray="1.5 2.5" />}
      {e.kind === "band" && (
        <>
          <line x1="1" y1="2" x2="21" y2="2" {...common} strokeWidth={1.5} />
          <rect x="1" y="2" width="20" height="6" fill={e.color} opacity="0.18" />
          <line x1="1" y1="8" x2="21" y2="8" {...common} strokeWidth={1.5} />
        </>
      )}
      {e.kind === "marker" && e.symbol === "triangle-up" && (
        <polygon points="11,1 16,9 6,9" fill={e.color} />
      )}
      {e.kind === "marker" && e.symbol === "x" && (
        <>
          <line x1="7" y1="1" x2="15" y2="9" {...common} />
          <line x1="15" y1="1" x2="7" y2="9" {...common} />
        </>
      )}
      {e.kind === "marker" && e.symbol === "circle" && (
        <circle cx="11" cy="5" r="4" fill="none" stroke={e.color} strokeWidth="1.8" />
      )}
    </svg>
  )
}

export function ChartLegendMenu({
  entries, onChart, onToggleOnChart,
}: {
  entries: LegendEntry[]
  /** Whether Plotly's own legend is currently drawn beside the plot. */
  onChart: boolean
  onToggleOnChart: (v: boolean) => void
}) {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLSpanElement>(null)

  // Clicking away closes it; without this it hangs over the chart, which is
  // the exact problem this component exists to solve.
  useEffect(() => {
    if (!open) return
    const away = (ev: MouseEvent) => {
      if (box.current && !box.current.contains(ev.target as Node)) setOpen(false)
    }
    const esc = (ev: KeyboardEvent) => { if (ev.key === "Escape") setOpen(false) }
    document.addEventListener("mousedown", away)
    document.addEventListener("keydown", esc)
    return () => {
      document.removeEventListener("mousedown", away)
      document.removeEventListener("keydown", esc)
    }
  }, [open])

  return (
    <span className="relative" ref={box}>
      <button type="button"
              aria-haspopup="menu" aria-expanded={open}
              title="What each line, band and marker on the chart means"
              onClick={() => setOpen((v) => !v)}
              className="flex items-center gap-1 rounded border border-[color:var(--hairline-mid)]
                         bg-[color:var(--raise-3)] px-2 py-0.5 hover:bg-[color:var(--raise-4)]">
        <List className="h-3 w-3" aria-hidden /> Legend <ChevronDown className="h-3 w-3" aria-hidden />
      </button>
      {open && (
        <div role="menu"
             className="absolute right-0 top-7 z-30 w-72 max-h-[60vh] overflow-y-auto rounded-lg
                        border border-[color:var(--hairline-mid)] bg-[var(--surface-1)]
                        p-2 shadow-xl">
          <p className="px-1 pb-1 text-[10.5px] uppercase tracking-wide text-muted-foreground">
            On the chart now
          </p>
          <dl className="space-y-0.5">
            {entries.map((e) => (
              <div key={e.label}
                   className="flex items-center gap-2 rounded px-1 py-[3px] hover:bg-[color:var(--raise-2)]">
                <Swatch e={e} />
                <dt className="min-w-0 flex-1 truncate text-[11.5px] text-foreground">
                  {e.label}
                  {e.note && (
                    <span className="block truncate text-[10px] text-muted-foreground">{e.note}</span>
                  )}
                </dt>
                {e.value && (
                  <dd className="shrink-0 text-[11.5px] tabular-nums text-muted-foreground">{e.value}</dd>
                )}
              </div>
            ))}
          </dl>
          {entries.length === 0 && (
            <p className="px-1 py-2 text-[11.5px] text-muted-foreground">
              No studies are switched on.
            </p>
          )}
          {/* The way back to Plotly's own legend beside the plot. It is off by
              default because this panel now says the same thing without
              spending 119px of chart width on it -- but a legend you can read
              while the mouse is on the candles is worth having on a wide
              screen, so it is a toggle rather than a removal. */}
          <label className="mt-2 flex items-center gap-2 border-t border-[color:var(--hairline-soft)]
                            px-1 pt-2 text-[11.5px] text-muted-foreground cursor-pointer">
            <input type="checkbox" checked={onChart}
                   onChange={(ev) => onToggleOnChart(ev.target.checked)} />
            Also show this beside the chart
          </label>
        </div>
      )}
    </span>
  )
}
