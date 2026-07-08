// Full-fidelity port of ui/components/charts.py's candlestick_with_trades().
// Indicator math (EMA/RSI/Stoch) is computed server-side (api/serializers.py)
// and delivered as arrays — this component only handles the plotting/shape/
// annotation logic, mirroring the Python trace-by-trace.

import Plot from "react-plotly.js"
import type { Data, Layout, Shape, Annotations } from "plotly.js"
import type { OHLCVRecord, IndicatorSeries, ZigZagResponse, TradeRecord, ZigZagPoint } from "@/lib/types"

const GREEN = "#2dd4bf"
const RED = "#f0576b"
const BG = "#0b1120"
const GRID = "#1a2340"
const SWING_COLORS = ["#ffd23f", "#c77dff", "#4cc9f0", "#7ee787"]

interface CandlestickChartProps {
  symbol: string
  strategyName: string
  bars: OHLCVRecord[]
  indicators: IndicatorSeries
  zigzag: ZigZagResponse
  trades: TradeRecord[]
  showZigzag?: boolean
}

// Mirrors Plotly's make_subplots(row_heights=[...], vertical_spacing=v)
// domain math — returns [[y0,y1], ...] top-to-bottom for each row.
function rowDomains(heights: number[], spacing: number): [number, number][] {
  const total = heights.reduce((a, b) => a + b, 0)
  const available = 1 - (heights.length - 1) * spacing
  const domains: [number, number][] = []
  let yTop = 1
  for (const h of heights) {
    const rowHeight = (h / total) * available
    const y0 = yTop - rowHeight
    domains.push([y0, yTop])
    yTop = y0 - spacing
  }
  return domains
}

export function CandlestickChart({
  symbol, strategyName, bars, indicators, zigzag, trades, showZigzag = true,
}: CandlestickChartProps) {
  const t = bars.map((b) => b.t)
  const domains = rowDomains([0.55, 0.15, 0.15, 0.15], 0.035)

  // The x-axis only shows a date label where the visible range crosses a day
  // boundary (Plotly's default date-axis behavior) -- when zoomed into a
  // single day there'd be no date visible anywhere, so put it in the title
  // instead, where it stays visible at any zoom/pan level.
  const dateLabel = (() => {
    if (!bars.length) return ""
    const fmt = (iso: string) =>
      new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "2-digit" })
    const first = fmt(bars[0].t)
    const last = fmt(bars[bars.length - 1].t)
    return first === last ? first : `${first} – ${last}`
  })()
  const axisSuffix = ["", "2", "3", "4"] // row1 -> x/y, row2 -> x2/y2, ...

  const data: Data[] = []
  const shapes: Partial<Shape>[] = []
  const annotations: Partial<Annotations>[] = []

  // ── Row 1: Candlestick + EMA9/21 ──────────────────────────────────────
  data.push({
    type: "candlestick",
    x: t, open: bars.map((b) => b.o), high: bars.map((b) => b.h),
    low: bars.map((b) => b.l), close: bars.map((b) => b.c),
    name: "Price", showlegend: false,
    increasing: { line: { color: GREEN } }, decreasing: { line: { color: RED } },
    xaxis: "x", yaxis: "y",
  } as unknown as Data)

  data.push(
    { type: "scatter", mode: "lines", x: t, y: indicators.ema9, name: "EMA9",
      line: { color: "#ffab40", width: 1.2 }, xaxis: "x", yaxis: "y" } as unknown as Data,
    { type: "scatter", mode: "lines", x: t, y: indicators.ema21, name: "EMA21",
      line: { color: "#80cbc4", width: 1.2 }, xaxis: "x", yaxis: "y" } as unknown as Data,
  )

  // ── ZigZag overlay with per-swing numbering ───────────────────────────
  const zz10 = showZigzag ? zigzag.zigzag_10 : []
  const zz3 = showZigzag ? zigzag.zigzag_3 : []

  if (zz3.length) {
    data.push({
      type: "scatter", mode: "lines", x: zz3.map((p) => p.t), y: zz3.map((p) => p.price),
      name: "ZigZag (3L)", line: { color: "#f0c040", width: 1.2, dash: "dot" },
      hoverinfo: "skip", xaxis: "x", yaxis: "y",
    } as unknown as Data)
    for (const [ptype, color] of [["H", "#ff6b6b"], ["L", "#69f0ae"]] as const) {
      const pts = zz3.filter((p) => p.type === ptype)
      if (pts.length) {
        data.push({
          type: "scatter", mode: "markers", x: pts.map((p) => p.t), y: pts.map((p) => p.price),
          marker: { symbol: "circle", size: 6, color, line: { color: "white", width: 1 } },
          showlegend: false,
          hovertemplate: `<b>${ptype === "H" ? "High" : "Low"} (3L)</b><br>%{x}<br>@ %{y:.2f}<extra></extra>`,
          xaxis: "x", yaxis: "y",
        } as unknown as Data)
      }
    }
  }

  if (zz10.length) {
    data.push({
      type: "scatter", mode: "lines", x: zz10.map((p) => p.t), y: zz10.map((p) => p.price),
      name: "ZigZag (10L)", line: { color: "#2196f3", width: 1.5, dash: "dot" },
      hoverinfo: "skip", xaxis: "x", yaxis: "y",
    } as unknown as Data)

    // ── Swing boundary rectangles + headers (span all 4 panels via yref="paper") ──
    const bySwing = new Map<number, ZigZagPoint[]>()
    for (const p of zz10) {
      if (!bySwing.has(p.swing)) bySwing.set(p.swing, [])
      bySwing.get(p.swing)!.push(p)
    }
    const swingGroups = [...bySwing.entries()].sort((a, b) => a[0] - b[0])

    swingGroups.forEach(([swingNum, grp], i) => {
      const x0 = grp[0].t
      const x1 = i + 1 < swingGroups.length ? swingGroups[i + 1][1][0].t : t[t.length - 1]
      const color = SWING_COLORS[(swingNum - 1) % SWING_COLORS.length]

      shapes.push({
        type: "rect", xref: "x", yref: "paper",
        x0, x1, y0: 0, y1: 1,
        fillcolor: "rgba(0,0,0,0)",
        line: { color, width: 1.5, dash: "dot" },
        layer: "below",
      })
      const firstLabel = grp[0].label
      const lastLabel = grp[grp.length - 1].label
      const xMid = grp[Math.floor(grp.length / 2)].t
      annotations.push({
        x: xMid, y: 1.005, xref: "x", yref: "paper", yanchor: "bottom",
        text: `<b>Swing ${swingNum}</b><br>(${firstLabel} to ${lastLabel})`,
        showarrow: false, font: { color, size: 11 }, align: "center",
      })
      data.push({
        type: "scatter", mode: "markers", x: [x0], y: [grp[0].price],
        marker: { symbol: "star", size: 10, color, line: { color: "white", width: 0.5 } },
        showlegend: false, hoverinfo: "skip", xaxis: "x", yaxis: "y",
      } as unknown as Data)
    })

    // ── Decimal-labeled circles on the price chart ──
    for (const [ptype, color] of [["H", RED], ["L", GREEN]] as const) {
      const pts = zz10.filter((p) => p.type === ptype)
      if (!pts.length) continue
      data.push({
        type: "scatter", mode: "text+markers",
        x: pts.map((p) => p.t), y: pts.map((p) => p.price),
        name: ptype === "H" ? "Swing High" : "Swing Low",
        marker: { symbol: "circle", size: 30, color: BG, line: { color, width: 1.8 } },
        text: pts.map((p) => p.label), textposition: "middle center",
        textfont: { color: "white", size: 9, family: "Arial" },
        hovertemplate: "<b>Swing %{text}</b><br>%{x}<br>@ %{y:.2f}<extra></extra>",
        xaxis: "x", yaxis: "y",
      } as unknown as Data)
    }

    // ── Same decimal labels mirrored on RSI(2), Stoch, RSI(13) ──
    const byTime = new Map(t.map((ts, i) => [ts, i]))
    const nearestIdx = (ts: string) => byTime.get(ts) ?? 0
    const borderColors = zz10.map((p) => (p.type === "H" ? RED : GREEN))
    const panels: [number, (number | null)[]][] = [
      [2, indicators.rsi2], [3, indicators.stoch_k], [4, indicators.rsi13],
    ]
    for (const [rowN, vals] of panels) {
      const suffix = axisSuffix[rowN - 1]
      data.push({
        type: "scatter", mode: "text+markers",
        x: zz10.map((p) => p.t), y: zz10.map((p) => vals[nearestIdx(p.t)]),
        marker: { size: 26, color: BG, line: { color: borderColors, width: 1.8 } },
        text: zz10.map((p) => p.label), textposition: "middle center",
        textfont: { size: 8, color: "white", family: "Arial" },
        showlegend: false, cliponaxis: false,
        hovertemplate: "<b>Swing %{text}</b><br>%{y:.1f}<extra></extra>",
        xaxis: `x${suffix}`, yaxis: `y${suffix}`,
      } as unknown as Data)
    }
  }

  // ── Trade entry / exit markers ─────────────────────────────────────────
  const barTimes = new Set(t)
  const longs = trades.filter((tr) => tr.direction === "LONG" && barTimes.has(tr.entry_time))
  const shorts = trades.filter((tr) => tr.direction === "SHORT" && barTimes.has(tr.entry_time))
  const exits = trades.filter((tr) => tr.exit_time && barTimes.has(tr.exit_time))

  if (longs.length) {
    data.push({
      type: "scatter", mode: "markers",
      x: longs.map((tr) => tr.entry_time), y: longs.map((tr) => tr.entry_price * 0.9985),
      name: "Long Entry",
      marker: { symbol: "triangle-up", size: 13, color: GREEN, line: { color: "white", width: 1 } },
      hovertemplate: "<b>LONG ENTRY</b><br>%{x}<br>@ %{y:.2f}<extra></extra>",
      xaxis: "x", yaxis: "y",
    } as unknown as Data)
  }
  if (shorts.length) {
    data.push({
      type: "scatter", mode: "markers",
      x: shorts.map((tr) => tr.entry_time), y: shorts.map((tr) => tr.entry_price * 1.0015),
      name: "Short Entry",
      marker: { symbol: "triangle-down", size: 13, color: RED, line: { color: "white", width: 1 } },
      hovertemplate: "<b>SHORT ENTRY</b><br>%{x}<br>@ %{y:.2f}<extra></extra>",
      xaxis: "x", yaxis: "y",
    } as unknown as Data)
  }
  if (exits.length) {
    const exitColors = exits.map((tr) => (tr.pnl >= 0 ? GREEN : RED))
    data.push({
      type: "scatter", mode: "markers",
      x: exits.map((tr) => tr.exit_time!), y: exits.map((tr) => tr.exit_price!),
      name: "Exit",
      marker: { symbol: "x", size: 12, color: exitColors, line: { color: exitColors, width: 2 } },
      customdata: exits.map((tr) => [`$${tr.pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, tr.direction]),
      hovertemplate: "<b>EXIT (%{customdata[1]})</b><br>%{x}<br>@ %{y:.2f}<br>P&L: %{customdata[0]}<extra></extra>",
      xaxis: "x", yaxis: "y",
    } as unknown as Data)
  }
  for (const tr of trades) {
    if (!tr.exit_time || !barTimes.has(tr.entry_time) || !barTimes.has(tr.exit_time)) continue
    const color = tr.pnl >= 0 ? GREEN : RED
    data.push({
      type: "scatter", mode: "lines", x: [tr.entry_time, tr.exit_time], y: [tr.entry_price, tr.exit_price],
      line: { color, width: 1, dash: "dot" }, showlegend: false, hoverinfo: "skip",
      xaxis: "x", yaxis: "y",
    } as unknown as Data)
  }

  // ── Rows 2-4: RSI(2) / Stoch K&D / RSI(13) ─────────────────────────────
  data.push({
    type: "scatter", mode: "lines", x: t, y: indicators.rsi2, name: "RSI(2)",
    line: { color: "#ce93d8", width: 1.4 }, hovertemplate: "RSI(2): %{y:.1f}<extra></extra>",
    xaxis: "x2", yaxis: "y2",
  } as unknown as Data)
  data.push(
    { type: "scatter", mode: "lines", x: t, y: indicators.stoch_k, name: "%K",
      line: { color: "#4fc3f7", width: 1.4 }, hovertemplate: "%%K: %{y:.1f}<extra></extra>",
      xaxis: "x3", yaxis: "y3" } as unknown as Data,
    { type: "scatter", mode: "lines", x: t, y: indicators.stoch_d, name: "%D",
      line: { color: "#f48fb1", width: 1.2, dash: "dot" }, hovertemplate: "%%D: %{y:.1f}<extra></extra>",
      xaxis: "x3", yaxis: "y3" } as unknown as Data,
  )
  data.push({
    type: "scatter", mode: "lines", x: t, y: indicators.rsi13, name: "RSI(13)",
    line: { color: "#ffcc80", width: 1.4 }, hovertemplate: "RSI(13): %{y:.1f}<extra></extra>",
    xaxis: "x4", yaxis: "y4",
  } as unknown as Data)

  // Overbought/oversold reference lines (hline equivalents) per row
  const hlines: [number, number, string][] = [
    [2, 94, RED], [2, 2, GREEN], [3, 80, RED], [3, 20, GREEN], [4, 70, RED], [4, 30, GREEN],
  ]
  for (const [rowN, level, color] of hlines) {
    const suffix = axisSuffix[rowN - 1]
    shapes.push({
      type: "line", xref: "paper", yref: `y${suffix}` as Shape["yref"],
      x0: 0, x1: 1, y0: level, y1: level,
      line: { color, dash: "dash", width: 0.8 },
    })
  }

  const hasSwingHeaders = showZigzag && zz10.length > 0
  const rangeSelectorY = hasSwingHeaders ? 1.15 : 1.02

  // Pad the x-axis range a few bars beyond the first/last candle so the
  // edge tick labels (e.g. the last time on the right) aren't clipped by
  // sitting exactly on the plot boundary. Bar timestamps are naive
  // "wall clock" strings with no timezone marker -- new Date(...) parses
  // them as local time, so the padded boundary must be re-serialized with
  // local getters too (never toISOString(), which forces UTC and would
  // shift the range by the browser's UTC offset relative to the bars).
  const xRange = (() => {
    if (t.length < 2) return undefined
    const toNaiveString = (ms: number) => {
      const d = new Date(ms)
      const pad2 = (n: number) => String(n).padStart(2, "0")
      return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}` +
             `T${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`
    }
    const first = new Date(t[0]).getTime()
    const last = new Date(t[t.length - 1]).getTime()
    const barMs = (last - first) / (t.length - 1)
    const pad = barMs * 3
    return [toNaiveString(first - pad), toNaiveString(last + pad)]
  })()

  const spikeAxis = {
    showspikes: true, spikemode: "across" as const, spikesnap: "cursor" as const,
    spikethickness: 1, spikedash: "dot" as const, spikecolor: "#6b6b8a",
  }

  const layout: Partial<Layout> = {
    title: { text: `${symbol} — ${strategyName} · ${dateLabel}`, font: { size: 14, color: "#cdd6f4" } },
    paper_bgcolor: BG, plot_bgcolor: BG,
    font: { color: "#cdd6f4" },
    dragmode: "pan", hovermode: "x unified",
    // Legend docks to the right of the plot (vertical list) — outside the
    // plotting area so it never overlaps or shrinks the chart itself. Extra
    // right margin makes room for it.
    legend: {
      orientation: "v", xanchor: "left", x: 1.01, yanchor: "top", y: 1,
      bgcolor: "rgba(0,0,0,0.3)", borderwidth: 0, font: { size: 10, color: "#cdd6f4" },
    },
    // Bottom margin must be large enough to fit the x-axis tick text (date +
    // time) at any screen size -- automargin on the visible axis (xaxis4)
    // also lets Plotly grow this further on its own if it ever needs to.
    margin: hasSwingHeaders ? { l: 60, r: 110, t: 145, b: 70 } : { l: 60, r: 110, t: 55, b: 70 },
    height: 820,
    autosize: true,
    xaxis: {
      gridcolor: GRID, showgrid: true, rangeslider: { visible: false },
      rangeselector: {
        buttons: [
          { count: 1, label: "1D", step: "day", stepmode: "backward" },
          { count: 5, label: "5D", step: "day", stepmode: "backward" },
          { count: 1, label: "1M", step: "month", stepmode: "backward" },
          { count: 3, label: "3M", step: "month", stepmode: "backward" },
          { count: 6, label: "6M", step: "month", stepmode: "backward" },
          { step: "all", label: "All" },
        ],
        bgcolor: BG, activecolor: "#3d3d5c", font: { color: "#cdd6f4", size: 11 },
        x: 0, y: rangeSelectorY, xanchor: "left",
      },
      domain: [0, 1] as [number, number],
      anchor: "y",
      showticklabels: false,
      range: xRange,
      ...spikeAxis,
    },
    yaxis: { gridcolor: GRID, showgrid: true, title: { text: "Price", font: { size: 9, color: "#8b8ba0" } },
             domain: domains[0], anchor: "x", fixedrange: false },
    xaxis2: { gridcolor: GRID, matches: "x", domain: [0, 1] as [number, number],
              anchor: "y2", showticklabels: false, ...spikeAxis },
    yaxis2: { gridcolor: GRID, showgrid: true, title: { text: "RSI(2)", font: { size: 9, color: "#8b8ba0" } },
              domain: domains[1], anchor: "x2", fixedrange: true, range: [0, 100] },
    xaxis3: { gridcolor: GRID, matches: "x", domain: [0, 1] as [number, number],
              anchor: "y3", showticklabels: false, ...spikeAxis },
    yaxis3: { gridcolor: GRID, showgrid: true, title: { text: "Stoch", font: { size: 9, color: "#8b8ba0" } },
              domain: domains[2], anchor: "x3", fixedrange: true, range: [0, 100] },
    xaxis4: { gridcolor: GRID, matches: "x", domain: [0, 1] as [number, number],
              anchor: "y4", automargin: true, tickfont: { size: 11 }, ...spikeAxis },
    yaxis4: { gridcolor: GRID, showgrid: true, title: { text: "RSI(13)", font: { size: 9, color: "#8b8ba0" } },
              domain: domains[3], anchor: "x4", fixedrange: true, range: [0, 100] },
    shapes: shapes as Layout["shapes"],
    annotations: annotations as Layout["annotations"],
  }

  return (
    <Plot
      data={data}
      layout={layout}
      config={{
        scrollZoom: true, displayModeBar: true,
        modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
      }}
      style={{ width: "100%" }}
      useResizeHandler
    />
  )
}
