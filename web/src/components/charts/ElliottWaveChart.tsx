// A real price chart with Elliott Wave labels drawn on it. Labels come
// straight from the backend's continuous wave_sequence
// (src/analysis/wave_numbering.py, the logic extracted from
// github.com/wealthwise-advisors/Wealthwise) -- a left-to-right walk of the
// WHOLE chart, not just one best-fit window, so this can show many
// consecutive wave counts (each a "run" starting back at Wave 1) across the
// backtest. Deliberately shows ONLY what that numbering logic produces --
// no bias box, invalidation line, or correction-type summary, since those
// come from unrelated pre-existing code, not the GitHub reference. Two
// nested degrees from the backend ("primary", "minor") are distinguished
// the same way professional services do it: the coarser degree's labels
// are plain ("3.2"), the finer degree nested inside it gets one level of
// parentheses ("(3.2)").
//
// PROGRESSIVE DETAIL (2026-07-17, revised same day after a real-data QA
// pass): a dense minor-degree chart can carry hundreds of points across many
// runs -- drawing all of them at once is unreadable, especially zoomed out.
// web/src/lib/waveLabelLayout.ts handles this entirely on the presentation
// side (zero changes to the wave-counting algorithm), on TWO levels:
//   - Text labels: which points get an on-chart TEXT label is decided by a
//     priority tier (impulse/corrective backbone 1-3-5-a-c > retracements
//     2-4-b > continuation 6..11) crossed with zoom level, then a genuine 2D
//     (time AND price) same-lane collision pass so labels never sit on top
//     of each other.
//   - Line/markers: the first version always drew every point on the
//     connecting line regardless of zoom, reasoning the "shape" should stay
//     constant -- but on real data that just meant a busy chart LOOKED busy
//     even with text stripped off (verified: 77 points drawn for 27 shown
//     labels on one real minor-degree run). Now the line/marker trace itself
//     is tier-filtered the same way -- zoomed out shows a clean simplified
//     backbone, zooming in progressively reveals the full-resolution path.
// Both recompute live as the user zooms/pans via Plotly's onRelayout.

import { useMemo, useRef, useState, useCallback } from "react"
import Plot from "react-plotly.js"
import type { Data, Layout, Shape, Annotations, PlotRelayoutEvent } from "plotly.js"
import type { OHLCVRecord, WaveAnalysis, WaveLabel } from "@/lib/types"
import { toLabelPoints, declutter, tierOf, tierFilterRun, zoomFractionOf, WaveTier } from "@/lib/waveLabelLayout"

const BG = "#0b1120"
const GRID = "#1a2340"
const GREEN = "#2dd4bf"
const RED = "#f0576b"

// Cycled per wave-count "run" (each run starts back at Wave 1) so
// consecutive counts across the chart are visually distinguishable -- same
// idea as CandlestickChart.tsx's SWING_COLORS cycling per swing group.
const RUN_COLORS = ["#2196f3", "#f0c040", "#7ee787", "#c77dff", "#4cc9f0", "#ff8a65"]

// Per-tier visual weight -- the impulse/corrective backbone reads as bold
// and bright, retracements a step down, continuation waves smallest and
// dimmest. Independent of per-run hue (RUN_COLORS) so a run stays
// identifiable by color while tier still reads by size/weight/opacity.
const TIER_STYLE: Record<WaveTier, { fontSize: number; markerSize: number; opacity: number; bold: boolean }> = {
  [WaveTier.Core]: { fontSize: 13, markerSize: 7, opacity: 1.0, bold: true },
  [WaveTier.Secondary]: { fontSize: 10.5, markerSize: 5.5, opacity: 0.8, bold: false },
  [WaveTier.Tertiary]: { fontSize: 9, markerSize: 4.5, opacity: 0.55, bold: false },
}

function wrap(label: string, nested: boolean) {
  return nested ? `(${label})` : label
}

// Plain wave name only -- `sub` (1 = Fibonacci+pattern confirmed, 2 =
// pattern-only) is a confidence score, not genuine Elliott sub-wave
// notation, so it's kept out of the primary label text (it reads exactly
// like "wave 3, sub-wave 2" otherwise, which is a different concept
// entirely). Confidence is still conveyed visually via marker/text opacity
// (see the `sub === 2` dimming below), just not baked into the number.
function waveText(w: WaveLabel): string {
  return w.wave
}

// Groups the flat wave_sequence into runs: a new run starts every time the
// count resets back to Wave 1. wave_numbering.py's label_wave_sequence()
// (2026-07-18 rewrite) selects the highest-scoring non-overlapping set of
// counts across the whole chart and returns them sorted by position -- each
// selected count still starts at its own Wave 1, so this grouping still
// holds, it's just no longer "whichever count was found first walking
// left-to-right."
function groupRuns(sequence: WaveLabel[]): WaveLabel[][] {
  const runs: WaveLabel[][] = []
  for (const w of sequence) {
    if (w.wave === "1" || runs.length === 0) runs.push([w])
    else runs[runs.length - 1].push(w)
  }
  return runs
}

// Plotly's date-axis relayout range comes through as an ISO-ish string, not
// the numeric type the .d.ts declares -- parse defensively either way.
function toEpoch(v: string | number): number {
  return typeof v === "number" ? v : new Date(v).getTime()
}

interface ElliottWaveChartProps {
  symbol: string
  bars: OHLCVRecord[]
  analysis: WaveAnalysis
  nested: boolean // true = finer/nested degree (parenthesized labels), false = coarser degree (plain labels)
}

export function ElliottWaveChart({ symbol, bars, analysis, nested }: ElliottWaveChartProps) {
  const t = bars.map((b) => b.t)
  const fullRange = useMemo<[number, number]>(() => {
    if (!bars.length) return [0, 1]
    return [toEpoch(bars[0].t), toEpoch(bars[bars.length - 1].t)]
  }, [bars])

  // null = fully zoomed out (no user interaction yet) -- treated as the
  // whole chart being visible, so decluttering starts at "backbone only".
  const [visibleRange, setVisibleRange] = useState<[number, number] | null>(null)
  const relayoutTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Debounced so a click-drag pan (which fires onRelayout continuously,
  // dragmode is "pan" below) doesn't re-run decluttering dozens of times a
  // second -- settle for ~120ms after the user stops moving.
  const handleRelayout = useCallback((ev: Readonly<PlotRelayoutEvent>) => {
    if (relayoutTimer.current) clearTimeout(relayoutTimer.current)
    relayoutTimer.current = setTimeout(() => {
      if (ev["xaxis.autorange"]) {
        setVisibleRange(null)
        return
      }
      const lo = ev["xaxis.range[0]"]
      const hi = ev["xaxis.range[1]"]
      if (lo !== undefined && hi !== undefined) {
        setVisibleRange([toEpoch(lo), toEpoch(hi)])
      }
    }, 120)
  }, [])

  const runs = useMemo(() => groupRuns(analysis.wave_sequence), [analysis.wave_sequence])

  const colorOf = useMemo(() => {
    // Keyed by object identity -- `runs` is `analysis.wave_sequence`'s own
    // entries regrouped, not cloned, so this always matches.
    const byRef = new Map<WaveLabel, string>()
    runs.forEach((run, i) => {
      const color = RUN_COLORS[i % RUN_COLORS.length]
      run.forEach((w) => byRef.set(w, color))
    })
    return (w: WaveLabel) => byRef.get(w) ?? RUN_COLORS[0]
  }, [runs])

  const range = visibleRange ?? fullRange
  const zoomFraction = zoomFractionOf(range, fullRange)

  // Plotly's y-axis autoranges to whatever's on screen, so the price range a
  // user actually SEES is the high/low of the bars within the current
  // x-window, not the whole dataset's range -- used both to gate the line's
  // tier-filtering feel consistent and, more importantly, as the price-axis
  // denominator for declutter()'s 2D collision check.
  const visiblePriceRange = useMemo<[number, number]>(() => {
    const inWindow = bars.filter((b) => {
      const bt = toEpoch(b.t)
      return bt >= range[0] && bt <= range[1]
    })
    const pool = inWindow.length ? inWindow : bars
    if (!pool.length) return [0, 1]
    let lo = Infinity, hi = -Infinity
    for (const b of pool) { if (b.l < lo) lo = b.l; if (b.h > hi) hi = b.h }
    return [lo, hi]
  }, [bars, range])

  const { shown, hiddenCount } = useMemo(() => {
    const points = toLabelPoints(analysis.wave_sequence, colorOf)
    return declutter(points, range, fullRange, visiblePriceRange)
  }, [analysis.wave_sequence, colorOf, range, fullRange, visiblePriceRange])

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

  // Connecting line + markers per run, tier-filtered to the SAME zoom-based
  // visibility as the text labels -- zoomed out, this draws a clean
  // simplified backbone (e.g. just 1-3-5-a-c) instead of every micro-pivot
  // with only the labels stripped off. The run's own points are still the
  // ground truth (the wave COUNT never changes) -- only how much of its
  // path is currently drawn responds to zoom, same as the text.
  runs.forEach((run, i) => {
    const color = RUN_COLORS[i % RUN_COLORS.length]
    const visiblePoints = tierFilterRun(run, zoomFraction)
    const markerSizes = visiblePoints.map((w) => TIER_STYLE[tierOf(w.wave)].markerSize)
    // sub === 2 means only the pattern condition held, not the Fibonacci
    // gate -- a real (not vestigial, see wave_numbering.py's module
    // docstring) lower-confidence signal, shown as a dimmer marker.
    const opacities = visiblePoints.map((w) => (w.sub === 2 ? 0.45 : 1.0))
    data.push({
      type: "scatter", mode: "lines+markers",
      x: visiblePoints.map((w) => w.t), y: visiblePoints.map((w) => w.price),
      line: { color, width: 1.4 },
      marker: { size: markerSizes, color, opacity: opacities, line: { color: BG, width: 0.5 } },
      name: `Wave count ${i + 1} (${run[0].direction})`, showlegend: false,
      hovertemplate: "%{text}<br>%{x}<br>@ %{y:.2f}<extra></extra>",
      text: visiblePoints.map((w) => wrap(waveText(w), nested)),
    } as unknown as Data)
  })

  // Text annotations ONLY for the decluttered subset -- this is the part
  // that actually responds to zoom/priority, per waveLabelLayout.ts.
  shown.forEach((p) => {
    const style = TIER_STYLE[p.tier]
    annotations.push({
      x: p.w.t, y: p.w.price, xref: "x", yref: "y",
      text: style.bold ? `<b>${wrap(waveText(p.w), nested)}</b>` : wrap(waveText(p.w), nested),
      showarrow: false,
      font: { color: p.color, size: style.fontSize },
      opacity: style.opacity,
      yshift: p.w.kind === "high" ? (10 + style.fontSize) : -(10 + style.fontSize),
    })
  })

  // Quiet corner hint -- tells the user more detail exists without
  // cluttering the chart itself. Fixed to the viewport (paper-referenced),
  // so it doesn't move with pan/zoom.
  if (hiddenCount > 0) {
    annotations.push({
      x: 1, y: 0, xref: "paper", yref: "paper", xanchor: "right", yanchor: "bottom",
      text: `+${hiddenCount} label${hiddenCount === 1 ? "" : "s"} hidden — zoom in for full detail`,
      showarrow: false,
      font: { color: "#5b6485", size: 10 },
      xshift: -6, yshift: 6,
    })
  }

  const layout: Partial<Layout> = {
    title: { text: `${symbol} — ${analysis.degree} degree Elliott Wave`, font: { size: 13, color: "#cdd6f4" } },
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
        onRelayout={handleRelayout}
      />
    </div>
  )
}
