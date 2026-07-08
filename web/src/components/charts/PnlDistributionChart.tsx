// Port of ui/components/charts.py's pnl_distribution() — histogram of trade
// P&L, colored green/red per bin so losing vs winning trades read at a glance.

import Plot from "react-plotly.js"
import type { Data, Layout } from "plotly.js"
import type { TradeRecord } from "@/lib/types"
import { GOOD, CRITICAL } from "@/components/cards/StatCard"

const BG = "#0b1120"
const GRID = "#1a2340"
const NBINS = 30

export function PnlDistributionChart({ trades }: { trades: TradeRecord[] }) {
  if (!trades.length) {
    return <p className="text-muted-foreground p-4">No completed trades to analyze.</p>
  }

  const pnls = trades.map((t) => t.pnl)
  const min = Math.min(...pnls, 0)
  const max = Math.max(...pnls, 0)
  const span = max - min || 1
  const binWidth = span / NBINS
  const counts = new Array(NBINS).fill(0)
  for (const p of pnls) {
    const idx = Math.min(NBINS - 1, Math.max(0, Math.floor((p - min) / binWidth)))
    counts[idx]++
  }
  const centers = counts.map((_, i) => min + (i + 0.5) * binWidth)
  const colors = centers.map((c) => (c >= 0 ? GOOD : CRITICAL))

  const data: Data[] = [
    {
      type: "bar", x: centers, y: counts, marker: { color: colors },
      width: binWidth * 0.95, name: "Trade P&L",
      hovertemplate: "P&L: $%{x:.0f}<br>Count: %{y}<extra></extra>",
    } as unknown as Data,
  ]

  const layout: Partial<Layout> = {
    title: { text: "Trade P&L Distribution", font: { size: 14, color: "#cdd6f4" } },
    paper_bgcolor: BG, plot_bgcolor: BG, font: { color: "#cdd6f4" },
    dragmode: "zoom", showlegend: false,
    margin: { l: 55, r: 20, t: 55, b: 45 },
    height: 380, autosize: true,
    shapes: [{ type: "line", xref: "x", yref: "paper", x0: 0, x1: 0, y0: 0, y1: 1,
               line: { color: "white", dash: "dash", width: 1 } }],
    xaxis: { title: { text: "P&L ($)" }, gridcolor: GRID, showgrid: true },
    yaxis: { title: { text: "Count" }, gridcolor: GRID, showgrid: true, fixedrange: false },
  }

  return (
    <Plot data={data} layout={layout} config={{ scrollZoom: true, displayModeBar: true }}
          style={{ width: "100%" }} useResizeHandler />
  )
}
