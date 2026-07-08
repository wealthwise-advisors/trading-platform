// Port of ui/live_app.py's _build_live_chart() — candlestick + EMA9/21 + trade
// markers on row 1, volume on row 2. No swing overlay/RSI panels here (the
// live dashboard never had them either — this view is about watching bars
// and trades arrive, not the full analysis chart).

import Plot from "react-plotly.js"
import type { Data, Layout } from "plotly.js"
import type { ReplayBar, ReplayTrade } from "@/lib/types"

const GREEN = "#2dd4bf"
const RED = "#f0576b"
const BG = "#0b1120"
const GRID = "#1a2340"

function ema(values: number[], span: number): (number | null)[] {
  const k = 2 / (span + 1)
  const out: (number | null)[] = []
  let prev: number | null = null
  for (const v of values) {
    prev = prev === null ? v : v * k + prev * (1 - k)
    out.push(prev)
  }
  return out
}

interface LiveReplayChartProps {
  bars: ReplayBar[]
  completedTrades: ReplayTrade[]
  openTrade: ReplayTrade | null
  visibleBars: number
}

export function LiveReplayChart({ bars, completedTrades, openTrade, visibleBars }: LiveReplayChartProps) {
  const visible = bars.slice(-visibleBars)
  const t = visible.map((b) => b.t)
  const closes = visible.map((b) => b.c)
  const ema9 = ema(closes, 9)
  const ema21 = ema(closes, 21)

  const visSet = new Set(t)
  const longs = completedTrades.filter((tr) => tr.direction === "LONG" && visSet.has(tr.entry_time))
  const shorts = completedTrades.filter((tr) => tr.direction === "SHORT" && visSet.has(tr.entry_time))
  const exits = completedTrades.filter((tr) => tr.exit_time && visSet.has(tr.exit_time))

  const data: Data[] = [
    {
      type: "candlestick", x: t,
      open: visible.map((b) => b.o), high: visible.map((b) => b.h),
      low: visible.map((b) => b.l), close: visible.map((b) => b.c),
      name: "Price", showlegend: false,
      increasing: { line: { color: GREEN } }, decreasing: { line: { color: RED } },
      xaxis: "x", yaxis: "y",
    } as unknown as Data,
    { type: "scatter", mode: "lines", x: t, y: ema9, name: "EMA9",
      line: { color: "#ffab40", width: 1.2 }, xaxis: "x", yaxis: "y" } as unknown as Data,
    { type: "scatter", mode: "lines", x: t, y: ema21, name: "EMA21",
      line: { color: "#80cbc4", width: 1.2 }, xaxis: "x", yaxis: "y" } as unknown as Data,
    {
      type: "bar", x: t, y: visible.map((b) => b.v ?? 0), name: "Volume", showlegend: false,
      marker: { color: visible.map((b) => (b.c >= b.o ? GREEN : RED)) },
      xaxis: "x2", yaxis: "y2",
    } as unknown as Data,
  ]

  if (longs.length) {
    data.push({
      type: "scatter", mode: "markers", name: "Long",
      x: longs.map((tr) => tr.entry_time), y: longs.map((tr) => tr.entry_price * 0.9985),
      marker: { symbol: "triangle-up", size: 13, color: GREEN, line: { color: "white", width: 1 } },
      hovertemplate: "<b>LONG</b><br>%{x}<br>@ %{y:.2f}<extra></extra>",
      xaxis: "x", yaxis: "y",
    } as unknown as Data)
  }
  if (shorts.length) {
    data.push({
      type: "scatter", mode: "markers", name: "Short",
      x: shorts.map((tr) => tr.entry_time), y: shorts.map((tr) => tr.entry_price * 1.0015),
      marker: { symbol: "triangle-down", size: 13, color: RED, line: { color: "white", width: 1 } },
      hovertemplate: "<b>SHORT</b><br>%{x}<br>@ %{y:.2f}<extra></extra>",
      xaxis: "x", yaxis: "y",
    } as unknown as Data)
  }
  if (exits.length) {
    const colors = exits.map((tr) => (tr.pnl >= 0 ? GREEN : RED))
    data.push({
      type: "scatter", mode: "markers", name: "Exit",
      x: exits.map((tr) => tr.exit_time!), y: exits.map((tr) => tr.exit_price!),
      marker: { symbol: "x", size: 12, color: colors, line: { color: colors, width: 2 } },
      customdata: exits.map((tr) => [`$${tr.pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, tr.direction]),
      hovertemplate: "<b>EXIT (%{customdata[1]})</b><br>%{x}<br>@ %{y:.2f}<br>P&L: %{customdata[0]}<extra></extra>",
      xaxis: "x", yaxis: "y",
    } as unknown as Data)
  }
  if (openTrade && visSet.has(openTrade.entry_time)) {
    const color = openTrade.direction === "LONG" ? GREEN : RED
    const sym = openTrade.direction === "LONG" ? "triangle-up" : "triangle-down"
    data.push({
      type: "scatter", mode: "markers", name: `Open ${openTrade.direction}`,
      x: [openTrade.entry_time], y: [openTrade.entry_price * (openTrade.direction === "LONG" ? 0.9985 : 1.0015)],
      marker: { symbol: sym, size: 16, color, line: { color: "white", width: 2 } },
      hovertemplate: `<b>OPEN ${openTrade.direction}</b><br>Entry: ${openTrade.entry_price.toFixed(2)}<extra></extra>`,
      xaxis: "x", yaxis: "y",
    } as unknown as Data)
  }

  const spikeAxis = {
    showspikes: true, spikemode: "across" as const, spikesnap: "cursor" as const,
    spikethickness: 1, spikedash: "dot" as const, spikecolor: "#6b6b8a",
  }

  const layout: Partial<Layout> = {
    paper_bgcolor: BG, plot_bgcolor: BG, font: { color: "#cdd6f4" },
    dragmode: "pan", hovermode: "x unified",
    uirevision: "live-replay",
    // Legend sits further below the plot than the tick labels so the two
    // never overlap -- tick labels own the space right under the volume
    // panel, the legend gets its own row beneath that.
    legend: {
      orientation: "h", xanchor: "center", x: 0.5, yanchor: "top", y: -0.16,
      bgcolor: "rgba(0,0,0,0.3)", borderwidth: 0, font: { size: 10, color: "#cdd6f4" },
    },
    margin: { l: 60, r: 12, t: 12, b: 95 },
    height: 640, autosize: true,
    xaxis: { gridcolor: GRID, showgrid: true, rangeslider: { visible: false },
             domain: [0, 1], anchor: "y", showticklabels: false, ...spikeAxis },
    yaxis: { gridcolor: GRID, showgrid: true, title: { text: "Price", font: { size: 9, color: "#8b8ba0" } },
             domain: [0.28, 1], anchor: "x", fixedrange: false },
    xaxis2: { gridcolor: GRID, matches: "x", domain: [0, 1], anchor: "y2",
              automargin: true, tickfont: { size: 11 }, ...spikeAxis },
    yaxis2: { gridcolor: GRID, showgrid: true, title: { text: "Volume", font: { size: 9, color: "#8b8ba0" } },
              domain: [0, 0.22], anchor: "x2", fixedrange: true },
  }

  return (
    <Plot
      data={data}
      layout={layout}
      config={{ scrollZoom: true, displayModeBar: true, modeBarButtonsToRemove: ["lasso2d", "select2d"] }}
      style={{ width: "100%" }}
      useResizeHandler
    />
  )
}
