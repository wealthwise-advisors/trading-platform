// A real price chart with Elliott Wave labels drawn on it, matching the
// style of professional Elliott Wave forecast services (candlesticks + wave
// pivot labels + an invalidation level line) instead of the old text/card
// summary. Two nested degrees from the backend ("primary", "minor") are
// distinguished the same way those services do it: the coarser degree's
// labels are plain (i, ii, iii...), the finer degree nested inside it gets
// one level of parentheses ((i), (ii)...).

import Plot from "react-plotly.js"
import type { Data, Layout, Shape, Annotations } from "plotly.js"
import type { OHLCVRecord, WaveAnalysis, WaveSwing } from "@/lib/types"

const BG = "#0b1120"
const GRID = "#1a2340"
const GREEN = "#2dd4bf"
const RED = "#f0576b"
const IMPULSE_COLOR = "#2196f3"
const CORRECTION_COLOR = "#f0c040"
const INVALIDATION_COLOR = "#F97316"

function wrap(label: string, nested: boolean) {
  return nested ? `(${label})` : label
}

const ROMAN_DIGITS: [number, string][] = [
  [1000, "m"], [900, "cm"], [500, "d"], [400, "cd"],
  [100, "c"], [90, "xc"], [50, "l"], [40, "xl"],
  [10, "x"], [9, "ix"], [5, "v"], [4, "iv"], [1, "i"],
]
// Open-ended roman numeral generator -- ROMAN used to be a fixed 7-entry
// array (i..vii) that fell back to a bare number ("8") past that, which
// looked like a broken sequence. Generating on demand means it keeps
// counting (viii, ix, x...) no matter how many waves there are.
function toRoman(n: number): string {
  let x = n, out = ""
  for (const [value, symbol] of ROMAN_DIGITS) {
    while (x >= value) { out += symbol; x -= value }
  }
  return out
}

// Open-ended letter generator (a, b, c... z, aa, ab...) -- same fix as
// toRoman() above, for the correction's a/b/c labels.
function toLetters(n: number): string {
  let x = n, out = ""
  while (x > 0) {
    const rem = (x - 1) % 26
    out = String.fromCharCode(97 + rem) + out
    x = Math.floor((x - 1) / 26)
  }
  return out
}

// pivots[0] is always the wave's own origin (not itself a numbered/lettered
// point) -- pivots[1..] are the actual wave-end points, labeled in order.
function pivotLabels(pivots: WaveSwing[], kind: "roman" | "letters", nested: boolean): string[] {
  return pivots.map((_, i) => (i === 0 ? "" : wrap(kind === "roman" ? toRoman(i) : toLetters(i), nested)))
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

  if (analysis.impulse && analysis.impulse.pivots.length > 1) {
    const pivots = analysis.impulse.pivots
    const labels = pivotLabels(pivots, "roman", nested)
    data.push({
      type: "scatter", mode: "lines+markers", x: pivots.map((p) => p.t), y: pivots.map((p) => p.price),
      line: { color: IMPULSE_COLOR, width: 1.5 }, marker: { size: 5, color: IMPULSE_COLOR },
      name: `Impulse (${analysis.impulse.direction})`, showlegend: true,
      hovertemplate: "%{text}<br>%{x}<br>@ %{y:.2f}<extra></extra>", text: labels,
    } as unknown as Data)
    pivots.forEach((p, i) => {
      if (i === 0) return
      annotations.push({
        x: p.t, y: p.price, xref: "x", yref: "y",
        text: `<b>${labels[i]}</b>`, showarrow: false,
        font: { color: IMPULSE_COLOR, size: 12 },
        yshift: p.kind === "high" ? 16 : -16,
      })
    })
  }

  if (analysis.correction && analysis.correction.pivots.length > 1) {
    const pivots = analysis.correction.pivots
    const labels = pivotLabels(pivots, "letters", nested)
    data.push({
      type: "scatter", mode: "lines+markers", x: pivots.map((p) => p.t), y: pivots.map((p) => p.price),
      line: { color: CORRECTION_COLOR, width: 1.5, dash: "dot" }, marker: { size: 5, color: CORRECTION_COLOR },
      name: `Correction (${analysis.correction.type.replace(/_/g, " ")})`, showlegend: true,
      hovertemplate: "%{text}<br>%{x}<br>@ %{y:.2f}<extra></extra>", text: labels,
    } as unknown as Data)
    pivots.forEach((p, i) => {
      if (i === 0) return
      annotations.push({
        x: p.t, y: p.price, xref: "x", yref: "y",
        text: `<b>${labels[i]}</b>`, showarrow: false,
        font: { color: CORRECTION_COLOR, size: 12 },
        yshift: p.kind === "high" ? 16 : -16,
      })
    })
  }

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
    showlegend: true,
    legend: { orientation: "h", y: -0.08, bgcolor: "rgba(0,0,0,0)" },
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
