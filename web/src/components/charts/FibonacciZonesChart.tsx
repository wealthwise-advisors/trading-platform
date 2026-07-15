// Fibonacci confluence zones drawn as shaded horizontal bands on the price
// chart, instead of the old table-of-numbers view -- each zone's low/high
// range becomes a band, with strength shown via opacity (more overlapping
// sources = more solid) and the center price labeled on the right edge.

import Plot from "react-plotly.js"
import type { Data, Layout, Shape, Annotations } from "plotly.js"
import type { OHLCVRecord, WaveTargetZone } from "@/lib/types"

const BG = "#0b1120"
const GRID = "#1a2340"
const GREEN = "#2dd4bf"
const RED = "#f0576b"
const CYAN = "#14E0D4"

interface FibonacciZonesChartProps {
  symbol: string
  bars: OHLCVRecord[]
  zones: WaveTargetZone[]
}

export function FibonacciZonesChart({ symbol, bars, zones }: FibonacciZonesChartProps) {
  const t = bars.map((b) => b.t)
  const data: Data[] = [{
    type: "candlestick",
    x: t, open: bars.map((b) => b.o), high: bars.map((b) => b.h),
    low: bars.map((b) => b.l), close: bars.map((b) => b.c),
    name: "Price", showlegend: false,
    increasing: { line: { color: GREEN, width: 1.2 } }, decreasing: { line: { color: RED, width: 1.2 } },
  } as unknown as Data]

  const shapes: Partial<Shape>[] = []
  const annotations: Partial<Annotations>[] = []
  const maxStrength = Math.max(1, ...zones.map((z) => z.strength))

  zones.forEach((z) => {
    const opacity = 0.12 + 0.28 * (z.strength / maxStrength)
    shapes.push({
      type: "rect", xref: "paper", yref: "y",
      x0: 0, x1: 1, y0: z.low, y1: z.high,
      fillcolor: `rgba(20, 224, 212, ${opacity.toFixed(2)})`,
      line: { color: CYAN, width: 1, dash: "dot" },
      layer: "below",
    })
    annotations.push({
      x: 1, y: z.center, xref: "paper", yref: "y", xanchor: "right", yanchor: "middle",
      text: `${z.center.toFixed(2)} ×${z.strength}`,
      showarrow: false, font: { color: CYAN, size: 10 },
      bgcolor: "rgba(11,17,32,0.7)",
    })
  })

  const layout: Partial<Layout> = {
    title: { text: `${symbol} — Fibonacci Confluence Zones`, font: { size: 13, color: "#cdd6f4" } },
    paper_bgcolor: BG, plot_bgcolor: BG,
    font: { color: "#cdd6f4" },
    dragmode: "pan", hovermode: "x unified",
    showlegend: false,
    margin: { l: 50, r: 70, t: 45, b: 40 },
    autosize: true,
    xaxis: { gridcolor: GRID, showgrid: true, rangeslider: { visible: false } },
    yaxis: { gridcolor: GRID, showgrid: true, title: { text: "Price", font: { size: 9, color: "#8b8ba0" } } },
    shapes: shapes as Layout["shapes"],
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
