// A real price chart with Elliott Wave labels drawn on it, matching the
// style of professional Elliott Wave forecast services (candlesticks + wave
// pivot labels + an invalidation level line). Labels come straight from the
// backend's continuous wave_sequence (src/analysis/wave_numbering.py) -- a
// left-to-right walk of the WHOLE chart, not just one best-fit window, so
// unlike the old single impulse+correction view this can show many
// consecutive wave counts (each a "run" starting back at Wave 1) across the
// backtest. Two nested degrees from the backend ("primary", "minor") are
// distinguished the same way professional services do it: the coarser
// degree's labels are plain ("3.2"), the finer degree nested inside it gets
// one level of parentheses ("(3.2)").

import Plot from "react-plotly.js"
import type { Data, Layout, Shape, Annotations } from "plotly.js"
import type { OHLCVRecord, WaveAnalysis, WaveLabel } from "@/lib/types"

const BG = "#0b1120"
const GRID = "#1a2340"
const GREEN = "#2dd4bf"
const RED = "#f0576b"
const INVALIDATION_COLOR = "#F97316"

// Cycled per wave-count "run" (each run starts back at Wave 1) so
// consecutive counts across the chart are visually distinguishable -- same
// idea as CandlestickChart.tsx's SWING_COLORS cycling per swing group.
const RUN_COLORS = ["#2196f3", "#f0c040", "#7ee787", "#c77dff", "#4cc9f0", "#ff8a65"]

function wrap(label: string, nested: boolean) {
  return nested ? `(${label})` : label
}

function waveText(w: WaveLabel): string {
  return w.sub ? `${w.wave}.${w.sub}` : w.wave
}

// Groups the flat wave_sequence into runs: a new run starts every time the
// count resets back to Wave 1 (label "1" with no sub), matching how
// wave_numbering.py's label_wave_sequence() starts a fresh left-to-right
// attempt after a prior count closes or fails.
function groupRuns(sequence: WaveLabel[]): WaveLabel[][] {
  const runs: WaveLabel[][] = []
  for (const w of sequence) {
    if (w.wave === "1" || runs.length === 0) runs.push([w])
    else runs[runs.length - 1].push(w)
  }
  return runs
}

interface ElliottWaveChartProps {
  symbol: string
  bars: OHLCVRecord[]
  analysis: WaveAnalysis
  nested: boolean // true = finer/nested degree (parenthesized labels), false = coarser degree (plain labels)
}

export function ElliottWaveChart({ symbol, bars, analysis, nested }: ElliottWaveChartProps) {
  const t = bars.map((b) => b.t)
  const data: Data[] = []
  const shapes: Partial<Shape>[] = []
  const annotations: Partial<Annotations>[] = []

  data.push({
    type: "candlestick",
    x: t, open: bars.map((b) => b.o), high: bars.map((b) => b.h),
    low: bars.map((b) => b.l), close: bars.map((b) => b.c),
    name: "Price", showlegend: false,
    increasing: { line: { color: GREEN, width: 1.2 } }, decreasing: { line: { color: RED, width: 1.2 } },
  } as unknown as Data)

  const runs = groupRuns(analysis.wave_sequence)
  runs.forEach((run, i) => {
    const color = RUN_COLORS[i % RUN_COLORS.length]
    // sub === 2 means only the pattern condition held, not the Fibonacci
    // gate -- a real (not vestigial, see wave_numbering.py's module
    // docstring) lower-confidence signal, shown as a dimmer marker.
    const opacities = run.map((w) => (w.sub === 2 ? 0.45 : 1.0))
    data.push({
      type: "scatter", mode: "lines+markers",
      x: run.map((w) => w.t), y: run.map((w) => w.price),
      line: { color, width: 1.5 },
      marker: { size: 6, color, opacity: opacities },
      name: `Wave count ${i + 1} (${run[0].direction})`, showlegend: false,
      hovertemplate: "%{text}<br>%{x}<br>@ %{y:.2f}<extra></extra>",
      text: run.map((w) => wrap(waveText(w), nested)),
    } as unknown as Data)
    run.forEach((w) => {
      annotations.push({
        x: w.t, y: w.price, xref: "x", yref: "y",
        text: `<b>${wrap(waveText(w), nested)}</b>`, showarrow: false,
        font: { color, size: 11 },
        yshift: w.kind === "high" ? 14 : -14,
      })
    })
  })

  if (analysis.invalidation !== null) {
    shapes.push({
      type: "line", xref: "paper", yref: "y",
      x0: 0, x1: 1, y0: analysis.invalidation, y1: analysis.invalidation,
      line: { color: INVALIDATION_COLOR, dash: "dash", width: 1.2 },
    })
    annotations.push({
      x: 1, y: analysis.invalidation, xref: "paper", yref: "y",
      xanchor: "right", yanchor: "bottom",
      text: `Invalidation @ ${analysis.invalidation.toFixed(2)}`,
      showarrow: false, font: { color: INVALIDATION_COLOR, size: 10 },
    })
  }

  // Bias indicator box, top-right -- same idea as the reference's
  // "Turning Down" arrow box, driven off the same bias field the old
  // card-based summary already showed as a colored badge.
  const biasColor = analysis.bias === "long" ? GREEN : analysis.bias === "short" ? RED : "#8b93b8"
  const biasText = analysis.bias === "long" ? "Turning Up ↗" : analysis.bias === "short" ? "Turning Down ↘" : "Neutral"
  annotations.push({
    // y:0.99 (inside the plot's own 0-1 range, not above it at 1.05) --
    // that used to sit in the same margin strip as the title and modebar,
    // colliding with both. Anchored top-right INSIDE the plot instead.
    x: 0.99, y: 0.99, xref: "paper", yref: "paper", xanchor: "right", yanchor: "top",
    text: `<b>${biasText}</b>`, showarrow: false,
    font: { color: biasColor, size: 12 },
    bgcolor: "rgba(11,17,32,0.75)", bordercolor: biasColor, borderwidth: 1, borderpad: 4,
  })

  const layout: Partial<Layout> = {
    title: { text: `${symbol} — ${analysis.degree} degree Elliott Wave · ${analysis.cycle_position}`, font: { size: 13, color: "#cdd6f4" } },
    paper_bgcolor: BG, plot_bgcolor: BG,
    font: { color: "#cdd6f4" },
    dragmode: "pan", hovermode: "x unified",
    showlegend: false,
    margin: { l: 50, r: 20, t: 55, b: 40 },
    autosize: true,
    xaxis: { gridcolor: GRID, showgrid: true, rangeslider: { visible: false } },
    yaxis: { gridcolor: GRID, showgrid: true, title: { text: "Price", font: { size: 9, color: "#8b8ba0" } } },
    shapes: shapes as Layout["shapes"],
    annotations: annotations as Layout["annotations"],
  }

  return (
    <div style={{ width: "100%", height: 480 }}>
      <Plot
        data={data}
        layout={layout}
        config={{ scrollZoom: true, displayModeBar: true, modeBarButtonsToRemove: ["lasso2d", "select2d"] }}
        style={{ width: "100%", height: "100%" }}
        useResizeHandler
      />
    </div>
  )
}
