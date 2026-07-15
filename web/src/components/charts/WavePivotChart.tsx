// Shared base for the Swings / Elliott Wave (impulse) / Corrective Waves
// tabs -- each is "candlesticks + a labeled pivot-to-pivot line", just with
// different pivot data, labels, and line color. Kept separate from
// ElliottWaveChart (which shows impulse+correction+invalidation+bias
// together for the combined Wave Analysis tab) since these three are each
// scoped to ONE source file's own data.

import Plot from "react-plotly.js"
import type { Data, Layout, Annotations } from "plotly.js"
import type { OHLCVRecord } from "@/lib/types"

const BG = "#0b1120"
const GRID = "#1a2340"
const GREEN = "#2dd4bf"
const RED = "#f0576b"

export interface PivotPoint {
  t: string
  price: number
  label: string
  kind?: "high" | "low"
}

interface WavePivotChartProps {
  symbol: string
  bars: OHLCVRecord[]
  pivots: PivotPoint[]
  lineColor: string
  seriesName: string
  title: string
  dash?: boolean
}

export function WavePivotChart({ symbol, bars, pivots, lineColor, seriesName, title, dash }: WavePivotChartProps) {
  const t = bars.map((b) => b.t)
  const data: Data[] = []
  const annotations: Partial<Annotations>[] = []

  data.push({
    type: "candlestick",
    x: t, open: bars.map((b) => b.o), high: bars.map((b) => b.h),
    low: bars.map((b) => b.l), close: bars.map((b) => b.c),
    name: "Price", showlegend: false,
    increasing: { line: { color: GREEN, width: 1.2 } }, decreasing: { line: { color: RED, width: 1.2 } },
  } as unknown as Data)

  if (pivots.length) {
    data.push({
      type: "scatter", mode: "lines+markers", x: pivots.map((p) => p.t), y: pivots.map((p) => p.price),
      line: { color: lineColor, width: 1.5, dash: dash ? "dot" : "solid" },
      marker: { size: 5, color: lineColor },
      name: seriesName, showlegend: true,
      hovertemplate: "%{text}<br>%{x}<br>@ %{y:.2f}<extra></extra>", text: pivots.map((p) => p.label),
    } as unknown as Data)
    pivots.forEach((p, i) => {
      if (!p.label) return
      const up = p.kind ? p.kind === "high" : i % 2 === 0
      annotations.push({
        x: p.t, y: p.price, xref: "x", yref: "y",
        text: `<b>${p.label}</b>`, showarrow: false,
        font: { color: lineColor, size: 11 },
        yshift: up ? 16 : -16,
      })
    })
  }

  const layout: Partial<Layout> = {
    title: { text: `${symbol} — ${title}`, font: { size: 13, color: "#cdd6f4" } },
    paper_bgcolor: BG, plot_bgcolor: BG,
    font: { color: "#cdd6f4" },
    dragmode: "pan", hovermode: "x unified",
    showlegend: true,
    legend: { orientation: "h", y: -0.08, bgcolor: "rgba(0,0,0,0)" },
    margin: { l: 50, r: 20, t: 45, b: 40 },
    autosize: true,
    xaxis: { gridcolor: GRID, showgrid: true, rangeslider: { visible: false } },
    yaxis: { gridcolor: GRID, showgrid: true, title: { text: "Price", font: { size: 9, color: "#8b8ba0" } } },
    annotations: annotations as Layout["annotations"],
  }

  return (
    <div style={{ width: "100%", height: 420 }}>
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
