// Dedicated Elliott Wave chart. Standalone by design: it does NOT import,
// extend, or parameterise CandlestickChart.tsx (SRS FE-2.2) -- Price & Trades
// stays a plain Price & Trades chart with no Elliott traces.
//
// Single panel: candlesticks + wave paths + labels only. No RSI/Stoch/trade
// markers/Swing overlay -- those belong to Price & Trades (FE-2.3).
//
// FE-3 is the reason this component looks the way it does. An UNDECIDABLE
// structure -- one that passed every gate the engine can evaluate, but whose
// acceptance depends on a rule blocked by an open question -- must never be
// rendered as though it were confirmed. Confirmed structures draw solid;
// undecidable ones draw dashed and dimmed, are labelled "(undecidable)" in the
// legend, and carry their blocked_by reasons in the hover text. The blocked
// rule registry is surfaced in a panel beside the chart, not left in raw API
// data.

import { useMemo, useState } from "react"
import Plot from "react-plotly.js"
import type { Data, Layout } from "plotly.js"
import type { ElliottWaveResponse, EWWave, OHLCVRecord } from "@/lib/types"

const BG = "#0b1120"
const GRID = "#1a2340"
const UP = "#2dd4bf"
const DOWN = "#f0576b"

// Deliberately distinct from the Swing/3-Leg palette used on Price & Trades
// (gold/purple/cyan/green) so the two systems are never confused (FE-2.6).
const STRUCTURE_COLORS: Record<string, string> = {
  impulse: "#ff8c42",
  leading_diagonal: "#c084fc",
  ending_diagonal: "#f472b6",
  zigzag: "#38bdf8",
  flat: "#a3e635",
  flat_running: "#fbbf24",
}
const UNKNOWN_COLOR = "#94a3b8"

const PRETTY: Record<string, string> = {
  impulse: "Impulse",
  leading_diagonal: "Leading Diagonal",
  ending_diagonal: "Ending Diagonal",
  zigzag: "Zigzag",
  flat: "Flat",
  flat_running: "Running Flat",
}

interface Props {
  symbol: string
  strategyName: string
  bars: OHLCVRecord[]
  data: ElliottWaveResponse | undefined
  isLoading: boolean
  error?: unknown
  scaleFilter: number | "all"
  onScaleFilter: (s: number | "all") => void
}

export function ElliottWaveChart({
  symbol, strategyName, bars, data, isLoading, error,
  scaleFilter, onScaleFilter,
}: Props) {
  const [showUndecidable, setShowUndecidable] = useState(true)

  const { traces, structures, scales } = useMemo(() => {
    if (!data || !bars.length) return { traces: [] as Data[], structures: [] as EWWave[], scales: [] as number[] }

    const byId = new Map(data.waves.map((w) => [w.id, w]))
    const allStructures = data.waves.filter((w) => w.structure_type !== null)
    const scaleList = [...new Set(allStructures.map((s) => s.scale))].sort((a, b) => a - b)

    const visible = allStructures.filter(
      (s) => (scaleFilter === "all" || s.scale === scaleFilter) &&
             (showUndecidable || s.state !== "undecidable"),
    )

    const out: Data[] = [
      {
        type: "candlestick",
        x: bars.map((b) => b.t),
        open: bars.map((b) => b.o),
        high: bars.map((b) => b.h),
        low: bars.map((b) => b.l),
        close: bars.map((b) => b.c),
        increasing: { line: { color: UP } },
        decreasing: { line: { color: DOWN } },
        name: "Price",
        showlegend: false,
        hoverinfo: "x+y",
      } as unknown as Data,
    ]

    // One connected path per structure: start -> each labelled leg end, in
    // order. Drawing the path (rather than scattered markers) is what makes
    // the wave sequence legible as a sequence (SRS FE-2.5).
    const legendSeen = new Set<string>()
    for (const s of visible) {
      const legs = s.child_ids.map((id) => byId.get(id)).filter(Boolean) as EWWave[]
      if (!legs.length) continue

      const xs = [s.start_t, ...legs.map((l) => l.end_t)]
      const ys = [s.start_price, ...legs.map((l) => l.end_price)]
      const labels = ["", ...legs.map((l) => l.label ?? "")]

      const undecided = s.state === "undecidable"
      const color = STRUCTURE_COLORS[s.structure_type ?? ""] ?? UNKNOWN_COLOR
      const pretty = PRETTY[s.structure_type ?? ""] ?? s.structure_type ?? "?"
      const legendName = undecided ? `${pretty} (undecidable)` : pretty
      const legendKey = `${legendName}`

      const blockedNote = s.blocked_by.length
        ? `<br><b>Blocked by:</b> ${s.blocked_by.join(", ")}`
        : ""
      const measures = Object.entries(s.measurements)
        .map(([k, v]) => `<br>${k}: ${typeof v === "number" ? v.toFixed(3) : String(v)}`)
        .join("")

      out.push({
        type: "scatter",
        mode: "lines+markers+text",
        x: xs,
        y: ys,
        text: labels,
        textposition: "top center",
        textfont: { color, size: 10, family: "Arial" },
        line: {
          color,
          width: undecided ? 1.2 : 2.2,
          dash: undecided ? "dot" : "solid",
        },
        marker: {
          symbol: undecided ? "circle-open" : "diamond",
          size: undecided ? 7 : 9,
          color: undecided ? color : BG,
          line: { color, width: 1.6 },
        },
        opacity: undecided ? 0.55 : 1,
        name: legendName,
        legendgroup: legendKey,
        showlegend: !legendSeen.has(legendKey) && (legendSeen.add(legendKey), true),
        hovertemplate:
          `<b>${pretty}</b> — scale ${s.scale}` +
          `<br>state: <b>${s.state}</b>${blockedNote}${measures}` +
          `<br>%{x}<br>%{y:.2f}<extra></extra>`,
      } as unknown as Data)
    }

    return { traces: out, structures: visible, scales: scaleList }
  }, [data, bars, scaleFilter, showUndecidable])

  if (isLoading) {
    return <div className="flex items-center justify-center h-full text-muted-foreground">
      Running Elliott Wave analysis…
    </div>
  }
  if (error) {
    return <div className="p-6 text-destructive">Elliott Wave analysis failed: {String(error)}</div>
  }
  if (!data) return null

  const gated = data.counts.structures_by_state?.gated ?? 0
  const undecidable = data.counts.structures_by_state?.undecidable ?? 0

  const layout: Partial<Layout> = {
    title: {
      text: `${symbol} — ${strategyName} · Elliott Wave (engine ${data.engine_version})`,
      font: { size: 14, color: "#cdd6f4" },
    },
    paper_bgcolor: BG,
    plot_bgcolor: BG,
    font: { color: "#cdd6f4", size: 11 },
    dragmode: "pan",
    hovermode: "closest",
    margin: { l: 58, r: 12, t: 44, b: 40 },
    xaxis: {
      gridcolor: GRID, rangeslider: { visible: false }, type: "date",
      showspikes: true, spikemode: "across", spikesnap: "cursor",
      spikethickness: 1, spikedash: "dot", spikecolor: "#6b6b8a",
      rangeselector: {
        buttons: [
          { count: 1, label: "1D", step: "day", stepmode: "backward" },
          { count: 5, label: "5D", step: "day", stepmode: "backward" },
          { count: 1, label: "1M", step: "month", stepmode: "backward" },
          { step: "all", label: "All" },
        ],
        bgcolor: BG, activecolor: "#3d3d5c",
        font: { color: "#cdd6f4", size: 11 }, x: 0, y: 1.02, xanchor: "left",
      },
    },
    yaxis: { gridcolor: GRID, title: { text: "Price" }, autorange: true },
    legend: { bgcolor: "rgba(0,0,0,0)", borderwidth: 0, orientation: "h", y: -0.14 },
    autosize: true,
  }

  return (
    <div className="flex flex-col xl:flex-row gap-3 h-full min-h-0">
      <div className="flex-1 min-w-0 min-h-0 flex flex-col">
        {/* ── Controls. Every one is backed by a real API query parameter or
             a pure display filter -- no decorative knobs. ── */}
        <div className="shrink-0 flex flex-wrap items-center gap-3 pb-2 text-xs">
          <label className="flex items-center gap-1.5">
            <span className="text-muted-foreground">Scale</span>
            <select
              className="bg-white/5 border border-white/10 rounded px-2 py-1"
              value={String(scaleFilter)}
              onChange={(e) => onScaleFilter(e.target.value === "all" ? "all" : Number(e.target.value))}
            >
              <option value="all">All</option>
              {scales.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={showUndecidable}
              onChange={(e) => setShowUndecidable(e.target.checked)}
            />
            <span>Show undecidable</span>
          </label>
          <span className="text-muted-foreground">
            showing <b className="text-foreground">{structures.length}</b> of {data.counts.structures} structures
          </span>
          <span className="ml-auto flex items-center gap-3">
            <span className="inline-flex items-center gap-1">
              <span style={{ width: 18, height: 0, borderTop: "2.2px solid #ff8c42" }} />
              confirmed {gated}
            </span>
            <span className="inline-flex items-center gap-1 opacity-60">
              <span style={{ width: 18, height: 0, borderTop: "1.5px dotted #ff8c42" }} />
              undecidable {undecidable}
            </span>
          </span>
        </div>

        <div className="flex-1 min-h-0">
          <Plot
            data={traces}
            layout={layout}
            config={{
              scrollZoom: true, displaylogo: false, displayModeBar: true,
              modeBarButtonsToRemove: ["lasso2d", "select2d"],
            }}
            style={{ width: "100%", height: "100%" }}
            useResizeHandler
          />
        </div>
      </div>

      {/* ── FE-3.2: what was NOT evaluated, visible beside the chart rather
           than buried in the API payload. ── */}
      <aside className="xl:w-80 shrink-0 overflow-y-auto text-xs space-y-3 border-t xl:border-t-0 xl:border-l border-white/6 pt-3 xl:pt-0 xl:pl-3">
        <div>
          <h3 className="font-semibold mb-1 text-sm">Analysis completeness</h3>
          <p className="text-muted-foreground leading-relaxed">
            This analysis is <b className="text-foreground">partial by design</b>.{" "}
            <b className="text-foreground">{data.counts.blocked_rule_ids}</b> reference rules could
            not be evaluated because the source material does not define them precisely enough.
            Structures shown dashed are <b>undecidable</b>: they passed every gate the engine can
            evaluate, but acceptance depends on a blocked rule.
          </p>
        </div>

        {data.notes.length > 0 && (
          <div>
            <h4 className="font-semibold mb-1">Scope notes</h4>
            <ul className="list-disc pl-4 space-y-1 text-muted-foreground">
              {data.notes.map((n, i) => <li key={i}>{n}</li>)}
            </ul>
          </div>
        )}

        <div>
          <h4 className="font-semibold mb-1">
            Unevaluated rules ({data.blocked_rules.length} groups)
          </h4>
          <ul className="space-y-1.5">
            {data.blocked_rules.map((b, i) => (
              <li key={i} className="border border-white/6 rounded p-1.5">
                <div className="font-mono text-[11px] text-amber-300">{b.oq}</div>
                <div className="text-muted-foreground">{b.rules.join(", ")}</div>
                <div className="text-muted-foreground/80 mt-0.5">{b.reason}</div>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  )
}
