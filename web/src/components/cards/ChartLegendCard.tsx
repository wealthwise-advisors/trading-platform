// Standalone legend for CandlestickChart -- Plotly's own legend used to render
// inside the chart canvas (a floating box docked to its right edge); it's been
// turned off there (layout.showlegend = false) and rebuilt here instead, in
// the sidebar, using the exact same colors as the chart's traces. Purely a
// container-styling change -- nothing about the chart's indicators changed.

const GREEN = "#2dd4bf"
const RED = "#f0576b"

interface LegendItem {
  label: string
  color: string
  dash?: boolean
  marker?: "line" | "circle" | "triangle-up" | "triangle-down" | "x"
}

const ITEMS: LegendItem[] = [
  { label: "EMA9", color: "#ffab40", marker: "line" },
  { label: "EMA21", color: "#80cbc4", marker: "line" },
  { label: "ZigZag (3L)", color: "#f0c040", dash: true, marker: "line" },
  { label: "ZigZag (10L)", color: "#2196f3", dash: true, marker: "line" },
  { label: "Swing High", color: RED, marker: "circle" },
  { label: "Swing Low", color: GREEN, marker: "circle" },
  { label: "Long Entry", color: GREEN, marker: "triangle-up" },
  { label: "Short Entry", color: RED, marker: "triangle-down" },
  { label: "Exit", color: GREEN, marker: "x" },
  { label: "RSI(2)", color: "#ce93d8", marker: "line" },
  { label: "%K", color: "#4fc3f7", marker: "line" },
  { label: "%D", color: "#f48fb1", dash: true, marker: "line" },
  { label: "RSI(13)", color: "#ffcc80", marker: "line" },
]

function Swatch({ item }: { item: LegendItem }) {
  const { color, marker, dash } = item
  if (marker === "circle") {
    return <span className="inline-block w-2 h-2 rounded-full shrink-0" style={{ border: `1.2px solid ${color}`, background: "transparent" }} />
  }
  if (marker === "triangle-up" || marker === "triangle-down") {
    return (
      <span className="shrink-0" style={{
        width: 0, height: 0,
        borderLeft: "4px solid transparent", borderRight: "4px solid transparent",
        borderBottom: marker === "triangle-up" ? `6px solid ${color}` : undefined,
        borderTop: marker === "triangle-down" ? `6px solid ${color}` : undefined,
      }} />
    )
  }
  if (marker === "x") {
    return <span className="shrink-0 font-bold text-[0.6rem] leading-none" style={{ color }}>✕</span>
  }
  return (
    <span className="inline-block w-3 h-0 shrink-0" style={{ borderTop: `1.5px ${dash ? "dashed" : "solid"} ${color}` }} />
  )
}

// Only used as a small overlay floated inside the candlestick chart itself
// (see CandlestickChart.tsx) -- 13 items in a single column was always going
// to be tall no matter how small the font got, which is why it covered so
// much of the chart. A 2-column grid roughly halves that height, which is
// what actually makes this read as a compact corner badge instead of a
// banner running down the price panel.
export function ChartLegendCard() {
  return (
    <div className="info-card" style={{ ["--info-accent" as string]: "#2f80ff" }}>
      <div className="info-title text-[0.55rem] mb-1">Legend</div>
      <div className="grid grid-cols-2 gap-x-2 gap-y-0.5">
        {ITEMS.map((item) => (
          <div key={item.label} className="flex items-center gap-0.5 text-[0.48rem] leading-tight text-muted-foreground">
            <Swatch item={item} />
            <span className="truncate">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
