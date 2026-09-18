// Port of ui/components/charts.py's equity_curve() — 2-row Plotly subplot:
// portfolio value with a fill, and drawdown % below it.

import Plot from "@/lib/plot"
import { chartTheme } from "@/lib/chartTheme"
import { useThemeStore } from "@/store/themeStore"
import type { Data, Layout } from "plotly.js"
import type { EquityPoint } from "@/lib/types"

const BLUE = "#7c6cf5"
const RED = "#f0576b"
// Chart chrome comes from the theme, not from a literal here. BG and GRID used
// to be module constants, which meant a light theme still painted a near-black
// rectangle in the middle of a white page -- a Plotly layout is a JavaScript
// object and no stylesheet can reach it. Series colours are NOT themed: see
// the note in lib/chartTheme.ts for why a trader's hues must not move.

interface EquityChartProps {
  points: EquityPoint[]
  initialCapital: number
}

export function EquityChart({ points, initialCapital }: EquityChartProps) {
  // Subscribing (rather than only calling chartTheme()) is what makes the
  // header toggle repaint an open chart: without it the plot keeps the
  // palette it was first built with until something else re-renders it.
  useThemeStore((st) => st.theme)
  const { paper: BG, grid: GRID, ink: INK, hover: HOVER } = chartTheme()
  const t = points.map((p) => p.t)
  const equity = points.map((p) => p.equity)
  const drawdown = points.map((p) => p.drawdown_pct)

  const data: Data[] = [
    {
      type: "scatter", mode: "lines", x: t, y: equity, name: "Portfolio Value",
      line: { color: BLUE, width: 2 }, fill: "tozeroy", fillcolor: "rgba(124,108,245,0.12)",
      xaxis: "x", yaxis: "y",
    } as Data,
    {
      type: "scatter", mode: "lines", x: t, y: drawdown, name: "Drawdown %",
      line: { color: RED, width: 1.5 }, fill: "tozeroy", fillcolor: "rgba(240,87,107,0.2)",
      xaxis: "x2", yaxis: "y2",
    } as Data,
  ]

  const layout: Partial<Layout> = {
    title: { text: "Equity Curve & Drawdown", font: { size: 14, color: INK } },
    paper_bgcolor: BG, plot_bgcolor: BG, font: { color: INK },
    dragmode: "pan", hovermode: "x unified",
    legend: { bgcolor: HOVER, borderwidth: 0 },
    margin: { l: 55, r: 20, t: 45, b: 55 },
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
      config={{ scrollZoom: true, displayModeBar: true, displaylogo: false }}
      style={{ width: "100%" }}
      useResizeHandler
    />
  )
}
