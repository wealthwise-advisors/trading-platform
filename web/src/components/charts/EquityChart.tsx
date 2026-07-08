// Port of ui/components/charts.py's equity_curve() — 2-row Plotly subplot:
// portfolio value with a fill, and drawdown % below it.

import Plot from "react-plotly.js"
import type { Data, Layout } from "plotly.js"
import type { EquityPoint } from "@/lib/types"

const BLUE = "#4f8ef7"
const RED = "#f0576b"
const BG = "#0b1120"
const GRID = "#1a2340"

interface EquityChartProps {
  points: EquityPoint[]
  initialCapital: number
}

export function EquityChart({ points, initialCapital }: EquityChartProps) {
  const t = points.map((p) => p.t)
  const equity = points.map((p) => p.equity)
  const drawdown = points.map((p) => p.drawdown_pct)

  const data: Data[] = [
    {
      type: "scatter", mode: "lines", x: t, y: equity, name: "Portfolio Value",
      line: { color: BLUE, width: 2 }, fill: "tozeroy", fillcolor: "rgba(79,142,247,0.12)",
      xaxis: "x", yaxis: "y",
    } as Data,
    {
      type: "scatter", mode: "lines", x: t, y: drawdown, name: "Drawdown %",
      line: { color: RED, width: 1.5 }, fill: "tozeroy", fillcolor: "rgba(240,87,107,0.2)",
      xaxis: "x2", yaxis: "y2",
    } as Data,
  ]

  const layout: Partial<Layout> = {
    title: { text: "Equity Curve & Drawdown", font: { size: 14, color: "#cdd6f4" } },
    paper_bgcolor: BG, plot_bgcolor: BG, font: { color: "#cdd6f4" },
    dragmode: "pan", hovermode: "x unified",
    legend: { bgcolor: "rgba(0,0,0,0.3)", borderwidth: 0 },
    margin: { l: 65, r: 30, t: 55, b: 70 },
    height: 480, autosize: true,
    shapes: [{
      type: "line", xref: "paper", yref: "y", x0: 0, x1: 1,
      y0: initialCapital, y1: initialCapital,
      line: { color: "gray", dash: "dash", width: 1 },
    }],
    xaxis: { gridcolor: GRID, showgrid: true, domain: [0, 1], anchor: "y", showticklabels: false },
    yaxis: { gridcolor: GRID, showgrid: true, title: { text: "Portfolio Value ($)" },
             domain: [0.4, 1], anchor: "x", fixedrange: false },
    xaxis2: { gridcolor: GRID, showgrid: true, matches: "x", domain: [0, 1], anchor: "y2",
              automargin: true, tickfont: { size: 11 } },
    yaxis2: { gridcolor: GRID, showgrid: true, title: { text: "Drawdown (%)" },
              domain: [0, 0.32], anchor: "x2", fixedrange: false },
  }

  return (
    <Plot
      data={data}
      layout={layout}
      config={{ scrollZoom: true, displayModeBar: true }}
      style={{ width: "100%" }}
      useResizeHandler
    />
  )
}
