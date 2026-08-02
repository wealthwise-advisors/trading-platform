// A real price chart with Elliott Wave labels drawn on it. Labels come
// straight from the backend's continuous wave_sequence
// (src/analysis/wave_numbering.py) -- a left-to-right walk of the WHOLE
// chart, not just one best-fit window, so every detected structure across
// the backtest gets drawn, first candle to last, not just the most recent
// one. Every label the engine emits displays AS-IS: plain digits "1".."11"
// for motive (impulse/diagonal) waves, uppercase letters (A-B-C, A-B-C-D-E,
// W-X-Y, W-X-Y-X-Z) for corrective structures -- real Elliott Wave notation,
// matching the elliottwave-forecast.com reference. `splitIntoSegments`
// breaks the flat per-run sequence into segments at every genuine
// structural boundary (a fresh corrective structure starting, or a
// numeric-to-letter phase change) -- no renumbering, no relabeling.
//
// (Previously, 2026-07-18 through 2026-07-21, per an explicit request now
// reversed: every point displayed as a plain renumbered digit regardless of
// its real label, via `classicalElliottMode.ts`'s `toSimpleSegments`. That
// made corrective structures -- which are ALWAYS lettered in real Elliott
// notation -- show as digit-filled "Correction #N (1-M)" boxes, which is
// exactly what read as wrong against the reference material. That module is
// now retired; see `displayWave` below for the only remaining text
// transform, which just uppercases letters and passes digits through.)
//
// Each segment renders as an independent region, matching
// CandlestickChart.tsx's "Swing N" boxes: a full paper-height dashed
// rectangle (tiling the timeline so one box's right edge is the next box's
// left edge), a header pinned to a single fixed height, and circle markers
// with the label drawn inside the circle. A genuine gap between two
// structures (swings with no valid structure) is left unlabeled, not
// invented.

import { useMemo, useRef, useState, useCallback } from "react"
import Plot from "react-plotly.js"
import type { Data, Layout, Shape, Annotations, PlotRelayoutEvent } from "plotly.js"
import type { OHLCVRecord, WaveAnalysis, WaveLabel } from "@/lib/types"

// The first label of a corrective structure ("a" for zigzag/flat/triangle,
// "w" for double/triple three) -- an impulse/diagonal's own "1" only ever
// appears as the first element of a `groupRuns` run (see that function), so
// it doesn't need to be listed here as a mid-run segment boundary.
const FRESH_STRUCTURE_TOKENS = new Set(["a", "w"])

function isNumericWave(wave: string): boolean {
  return /^\d+$/.test(wave)
}

// The only text transform applied to a real engine label for display:
// corrective letters ("a".."z") uppercase to match standard Elliott
// notation (A, B, C, ... W, X, Y, Z); numeric labels ("1".."11") pass
// through unchanged.
function displayWave(wave: string): string {
  return /^[a-z]$/.test(wave) ? wave.toUpperCase() : wave
}

// Splits ONE run (as produced by `groupRuns` below) into segments at every
// genuine structural boundary: a fresh corrective structure starting
// (`FRESH_STRUCTURE_TOKENS`), or the label kind changing from numeric to
// letter or back (e.g. an impulse's "5" into its closing correction's "a").
// No renumbering -- every WaveLabel keeps its real `wave` field verbatim.
export function splitIntoSegments(run: WaveLabel[]): WaveLabel[][] {
  const segments: WaveLabel[][] = []
  let prevKind: "numeric" | "letter" | null = null

  for (const w of run) {
    const kind: "numeric" | "letter" = isNumericWave(w.wave) ? "numeric" : "letter"
    const isFreshStructureStart = FRESH_STRUCTURE_TOKENS.has(w.wave)
    const kindChanged = prevKind !== null && kind !== prevKind

    if (isFreshStructureStart || kindChanged || segments.length === 0) {
      segments.push([])
    }
    segments[segments.length - 1].push(w)
    prevKind = kind
  }
  return segments
}

const BG = "#0b1120"
const GRID = "#1a2340"
const GREEN = "#2dd4bf"
const RED = "#f0576b"

// Cycled per detected structure (segment) so consecutive ones across the
// chart are visually distinguishable -- same idea as CandlestickChart.tsx's
// SWING_COLORS cycling per swing group.
const SEGMENT_COLORS = ["#2196f3", "#f0c040", "#7ee787", "#c77dff", "#4cc9f0", "#ff8a65"]

// SWING-STYLE VISUALIZATION, 2026-07-20 (required behavior, replacing the
// price-fit-box + floating-annotation design after explicit follow-up
// feedback that it still didn't read as an independent region the way
// CandlestickChart.tsx's ZigZag "Swing N" boxes do): every detected
// structure now uses THE SAME THREE PRIMITIVES as a swing region --
// (1) a yref:"paper" rect spanning the full plot height (not fit to the
// structure's own price range -- a price-fit box shrinks to nothing for a
// tight, low-volatility wave and reads as "weak"), (2) a header pinned to
// one fixed paper y for every structure (not stacked/pushed around by price
// crowding -- that's what caused headers to drift high above the chart),
// and (3) large circle markers with the wave number drawn INSIDE the
// circle (dark fill, colored border) instead of floating text next to a
// small dot. This also retires the old declutter()/waveLabelLayout.ts
// collision-avoidance machinery entirely for this chart -- it existed to
// solve floating-text collisions, and that problem doesn't exist once the
// number lives inside its own marker at its own data point.
const MARKER_SIZE = 24
const HEADER_Y = 1.015

// MERGED GLOBAL+NESTED VISUALIZATION, 2026-07-21: when a degree has both an
// independent whole-chart reading (e.g. "minor_global") and a reading nested
// inside its parent's own wave legs (e.g. "minor"), both render on the SAME
// chart instead of two separate cards -- see ElliottWavePanel.tsx for the
// generic name-based pairing that decides this, not hardcoded to "minor".
// Three redundant visual cues (never just one) separate the two systems so
// they stay legible even where their colors land close together:
//   1. Box vertical extent -- Global tiles the FULL plot height (unchanged
//      from the solo style); Nested uses a narrower inset band, the
//      cheapest way to visually read "contained inside" without computing
//      real geometric containment.
//   2. Color temperature -- Global keeps the existing cool palette; Nested
//      uses a separate warm palette that never collides with it.
//   3. Weight -- Global's markers/lines/header text are larger and fully
//      opaque; Nested's are smaller and slightly translucent.
// Header text also switches from "Wave N" (1-indexed) to "Global Wave N"/
// "Nested Wave N" (0-indexed, per explicit requirement) with the
// structure's own internal point sequence appended, e.g. "Global Wave 0
// (1-2-3-4-5)" -- the "1-2-3-4-5" is each point's EXISTING label, unchanged;
// only the structure's own ordinal and the two prefixes are new.
interface WaveStyle {
  colors: string[]
  markerSize: number
  opacityMult: number
  boxY: [number, number]
  headerY: number
  headerAnchor: "top" | "bottom"
  lineDash: "dot" | "dashdot"
  lineWidth: number
  headerFontSize: number
  markerFontSize: number
}

const GLOBAL_STYLE: WaveStyle = {
  colors: SEGMENT_COLORS,
  markerSize: MARKER_SIZE,
  opacityMult: 1.0,
  boxY: [0, 1],
  headerY: HEADER_Y, headerAnchor: "bottom",
  lineDash: "dot", lineWidth: 1.3,
  headerFontSize: 11, markerFontSize: 10,
}
const NESTED_STYLE: WaveStyle = {
  colors: ["#f0c040", "#ff8a65", "#f472b6", "#fbbf24", "#e879f9", "#fb923c"],
  markerSize: 15,
  opacityMult: 0.75,
  boxY: [0.14, 0.86],
  headerY: 0.945, headerAnchor: "top",
  lineDash: "dashdot", lineWidth: 1.0,
  headerFontSize: 9, markerFontSize: 8,
}
// The single-degree (unpaired) look stays byte-identical to the pre-merge
// design -- 1-indexed "Wave N", no prefix, no appended sequence -- so
// degrees without a Global/Nested pair (e.g. "primary") don't change at all.
const SOLO_STYLE: WaveStyle = { ...GLOBAL_STYLE }

// Human-readable structure-type name derived from a segment's real label
// sequence (segment[i].wave -- never renumbered now). Matches the exact
// four verbatim label sequences wave_numbering.py/complex_corrections.py
// ever produce for a corrective structure. Returns null for numeric
// segments (impulses/diagonals), which keep the existing plain "Wave N"
// header -- those were never the bug this fixes. Also null for anything
// that doesn't exactly match one of the four corrective shapes (e.g. a
// structure truncated at the edge of the available data) -- falls back to
// "Wave N" rather than showing nothing.
export function describeStructureType(segment: WaveLabel[]): string | null {
  const seq = segment.map((w) => w.wave).join(",")
  switch (seq) {
    case "a,b,c": return "ABC Correction"
    case "a,b,c,d,e": return "Triangle"
    case "w,x,y": return "WXY Correction"
    case "w,x,y,x,z": return "Triple Three"
    default: return null
  }
}

// Groups the flat wave_sequence into the engine's own coarser "runs" first
// (a new run starts every time the count resets back to Wave 1) -- this is
// still needed as an input to splitIntoSegments, which then splits each run
// further at any numeric/letter phase change or fresh corrective start.
export function groupRuns(sequence: WaveLabel[]): WaveLabel[][] {
  const runs: WaveLabel[][] = []
  for (const w of sequence) {
    if (w.wave === "1" || runs.length === 0) runs.push([w])
    else runs[runs.length - 1].push(w)
  }
  return runs
}

export interface SegmentLabel {
  // What's actually shown on screen (chart header AND ElliottWavePanel.tsx's
  // "Detected: ..." line) -- e.g. "Wave 1 (1-5)" for an impulse/diagonal, or
  // "ABC Correction (A–C)" / "Triangle (A–E)" / "WXY Correction
  // (W–Y)" / "Triple Three (W–Z)" for a corrective structure, using
  // its own real letter span (real Elliott notation -- see module comment
  // for why the earlier plain-"Correction"-with-a-numeric-range design was
  // reversed). An ordinal "#N" suffix only appears when the SAME technical
  // type occurs more than once in this structure-set, to keep two same-kind
  // boxes distinguishable in the "Detected: ..." text list.
  display: string
  // The real Elliott type name (describeStructureType's output) for a
  // corrective segment -- also surfaced in the hover tooltip. Null for
  // numeric (impulse/diagonal) segments, which have no separate "technical"
  // name beyond "Wave N" itself.
  technical: string | null
}

// One label per segment -- single source of truth used both by
// renderStructureSet (for the on-chart header text and hover tooltip) and
// ElliottWavePanel.tsx (for the "Detected: ..." summary line below each
// chart) -- extracted here specifically so those two callers can't drift
// out of sync with each other. Numeric (impulse/diagonal) segments count
// independently ("Wave 1", "Wave 2", ... regardless of what's between
// them); corrective segments are named by their real technical type, with
// a per-type ordinal only when that specific type repeats.
export function labelSegments(segments: WaveLabel[][], zeroIndexed: boolean): SegmentLabel[] {
  const structureTypes = segments.map(describeStructureType)
  const totalByType = new Map<string, number>()
  for (const t of structureTypes) if (t) totalByType.set(t, (totalByType.get(t) ?? 0) + 1)
  const seenByType = new Map<string, number>()
  let waveSeen = zeroIndexed ? 0 : 1

  return segments.map((segment, i) => {
    const technical = structureTypes[i]
    if (technical) {
      const seen = (seenByType.get(technical) ?? 0) + 1
      seenByType.set(technical, seen)
      const suffix = (totalByType.get(technical) ?? 0) > 1 ? ` #${seen}` : ""
      const from = displayWave(segment[0].wave)
      const to = displayWave(segment[segment.length - 1].wave)
      return { display: `${technical}${suffix} (${from}–${to})`, technical }
    }
    const display = `Wave ${waveSeen} (1-${segment.length})`
    waveSeen += 1
    return { display, technical: null }
  })
}

// Plotly's date-axis relayout range comes through as an ISO-ish string, not
// the numeric type the .d.ts declares -- parse defensively either way.
function toEpoch(v: string | number): number {
  return typeof v === "number" ? v : new Date(v).getTime()
}

// ZOOM/PAN BUG FIX, 2026-07-19: scroll-zoom and drag-pan visibly moved the
// axis for ~100ms, then snapped back to the full range every time -- traced
// (not assumed) to a real race: handleRelayout's debounced setVisibleRange
// triggers a re-render ~120ms later, which rebuilds `layout` from scratch;
// since that layout never specified an explicit xaxis.range, Plotly.react()
// read the missing key as "revert to autorange" and undid the user's zoom
// a beat after it happened. Confirmed by sampling the live axis range every
// 25ms after a wheel event: it visibly narrowed at t=25ms, then reverted to
// the exact original bounds by t=150ms. CandlestickChart.tsx never hits
// this because it already feeds its tracked window back into xaxis.range on
// every render -- same fix, ported here. Serialized as a naive local-time
// string, not a raw ms number: bar timestamps are naive "wall clock"
// strings with no timezone marker, so a raw UTC ms number here would shift
// the axis by the browser's UTC offset relative to the bars (same
// footgun CandlestickChart.tsx's own toNaiveString warns about).
function toNaiveString(ms: number): string {
  const d = new Date(ms)
  const pad2 = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}` +
         `T${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`
}

interface ElliottWaveChartProps {
  symbol: string
  bars: OHLCVRecord[]
  // The visually DOMINANT reading -- when this degree has a Global/Nested
  // pair, ElliottWavePanel.tsx passes the GLOBAL analysis here (full-height
  // boxes, larger markers); when it doesn't, this is simply the only
  // reading there is, rendered exactly as before the merge.
  analysis: WaveAnalysis
  // The visually SECONDARY reading (the nested-inside-parent-legs one),
  // only present when this degree actually has a pair. Its presence alone
  // is what switches the chart into merged mode -- no separate boolean flag
  // needed, and no pairing logic lives in this component (see
  // ElliottWavePanel.tsx's generic name-based pairing). As of 2026-07-20,
  // ElliottWavePanel.tsx no longer passes this (reverted to separate
  // cards per explicit user request) -- merged-mode rendering stays intact
  // here in case it's wanted again, just currently unused.
  secondaryAnalysis?: WaveAnalysis
  // Title-only disambiguator for the separate-cards case: a degree ending
  // in "_global" is "Global", a degree with a "_global" sibling elsewhere
  // in the response is "Nested" -- computed by ElliottWavePanel.tsx (which
  // can see the whole response dict) since this component only receives
  // its own single `analysis` and can't tell the two cases apart from
  // `analysis.degree` alone. Ignored when secondaryAnalysis is present.
  variantLabel?: "Global" | "Nested"
}

// Pushes one structure-set's shapes/traces/annotations onto the shared
// accumulators, styled per `style` -- called once for Global, once for
// Nested when both are present, or once for the solo case. `labelPrefix`
// ("Global "/"Nested "/"") and `zeroIndexed` (0-indexed ordinal + appended
// point sequence, vs. the original 1-indexed "Wave N") are the only two
// things that differ between the merged-mode and solo-mode header text.
function renderStructureSet(
  segments: WaveLabel[][],
  style: WaveStyle,
  labelPrefix: string,
  zeroIndexed: boolean,
  data: Data[], shapes: Partial<Shape>[], annotations: Partial<Annotations>[],
) {
  const DENSITY_THRESHOLD = 10

  // One label per segment (display text + real technical name for hover) --
  // shared with ElliottWavePanel.tsx's "Detected: ..." summary line so the
  // two never drift out of sync (see labelSegments' own docstring). The
  // range/letter-span is already baked into `.display`, so header text is
  // uniform across solo and merged mode -- only the Global/Nested prefix
  // differs.
  const segmentLabels = labelSegments(segments, zeroIndexed)

  segments.forEach((segment, i) => {
    const color = style.colors[i % style.colors.length]
    const segStart = segment[0].t
    const ownEnd = segment[segment.length - 1].t
    const segEnd = i + 1 < segments.length ? segments[i + 1][0].t : ownEnd
    const xMid = segment[Math.floor(segment.length / 2)].t

    const { display: headerLabel, technical } = segmentLabels[i]
    const headerText = `<b>${labelPrefix}${headerLabel}</b>`

    shapes.push({
      type: "rect", xref: "x", yref: "paper",
      x0: segStart, x1: segEnd, y0: style.boxY[0], y1: style.boxY[1],
      fillcolor: "rgba(0,0,0,0)",
      line: { color, width: 1.2, dash: style.lineDash },
      layer: "below",
    })

    const skipHeader = segments.length > DENSITY_THRESHOLD && i % 2 === 1
    if (!skipHeader) {
      annotations.push({
        x: xMid, y: style.headerY, xref: "x", yref: "paper", yanchor: style.headerAnchor,
        text: headerText,
        showarrow: false, font: { color, size: style.headerFontSize }, align: "center",
      })
    }

    // Extend THIS segment's own line to also touch the very first point of
    // the NEXT segment (if any) -- confirmed design: the connector between
    // two structures should read as a continuous colored path in the
    // OUTGOING segment's own color, not a separate neutral line, so e.g.
    // Wave 1's connector into whatever follows it stays blue right up to
    // the handoff point, where the next segment's own trace takes over in
    // its own color from that same shared point.
    const nextFirstPoint = i + 1 < segments.length ? segments[i + 1][0] : null
    const lineT = segment.map((e) => e.t)
    const linePrice = segment.map((e) => e.price)
    if (nextFirstPoint) {
      lineT.push(nextFirstPoint.t)
      linePrice.push(nextFirstPoint.price)
    }
    data.push({
      type: "scatter", mode: "lines",
      x: lineT, y: linePrice,
      line: { color, width: style.lineWidth },
      showlegend: false, hoverinfo: "skip",
    } as unknown as Data)

    // sub === 2 means only the pattern condition held, not the Fibonacci
    // gate -- a real (not vestigial, see wave_numbering.py's module
    // docstring) lower-confidence signal, folded into this set's own base
    // opacity multiplier so Nested's already-reduced opacity compounds with
    // it rather than overriding it.
    const opacities = segment.map((e) => (e.sub === 2 ? 0.45 : 1.0) * style.opacityMult)
    data.push({
      type: "scatter", mode: "markers+text",
      x: segment.map((e) => e.t), y: segment.map((e) => e.price),
      marker: { symbol: "circle", size: style.markerSize, color: BG, opacity: opacities, line: { color, width: 1.8 } },
      text: segment.map((e) => displayWave(e.wave)), textposition: "middle center",
      textfont: { color: "white", size: style.markerFontSize, family: "Arial" },
      showlegend: false,
      // The real Elliott type name (e.g. "Triple Three"), not shown on the
      // header anymore per the simplified naming above, surfaces here on
      // hover instead -- available on demand, not deleted. Numeric
      // segments (technical === null) keep the original "Wave N" phrasing.
      hovertemplate: technical
        ? `${labelPrefix}${technical} — point %{text}<br>%{x}<br>@ %{y:.2f}<extra></extra>`
        : `${labelPrefix}Wave %{text}<br>%{x}<br>@ %{y:.2f}<extra></extra>`,
    } as unknown as Data)
  })
}

export function ElliottWaveChart({ symbol, bars, analysis, secondaryAnalysis, variantLabel }: ElliottWaveChartProps) {
  const t = bars.map((b) => b.t)
  const fullRange = useMemo<[number, number]>(() => {
    if (!bars.length) return [0, 1]
    return [toEpoch(bars[0].t), toEpoch(bars[bars.length - 1].t)]
  }, [bars])

  // null = fully zoomed out (no user interaction yet) -- treated as the
  // whole chart being visible.
  const [visibleRange, setVisibleRange] = useState<[number, number] | null>(null)
  const relayoutTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Debounced so a click-drag pan (which fires onRelayout continuously,
  // dragmode is "pan" below) doesn't re-render dozens of times a second --
  // settle for ~120ms after the user stops moving.
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

  // Flat list of every detected structure across the WHOLE chart, first
  // candle to last -- groupRuns' coarser boundaries first, then each run
  // split further into its own genuinely-restarted segments. Computed
  // independently for the secondary (Nested) reading when present -- two
  // completely separate passes over two separate wave_sequences, no shared
  // state, matching the "don't touch the engine" requirement (this is pure
  // presentation-side splitting of two already-independent results).
  const segments = useMemo(
    () => groupRuns(analysis.wave_sequence).flatMap(splitIntoSegments),
    [analysis.wave_sequence]
  )
  const secondarySegments = useMemo(
    () => secondaryAnalysis ? groupRuns(secondaryAnalysis.wave_sequence).flatMap(splitIntoSegments) : [],
    [secondaryAnalysis]
  )

  const range = visibleRange ?? fullRange

  // Plotly's y-axis autoranges to whatever's on screen, so the price range a
  // user actually SEES is the high/low of the bars within the current
  // x-window, not the whole dataset's range -- used below to pad the
  // explicit y-axis range so circle markers don't clip the plot edge.
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

  // Connecting line + markers per detected structure -- full detail, every
  // point, always, for EVERY structure across the whole chart (see the
  // module comment above). Boxes TILE the timeline (each one's right edge
  // is the next one's left edge) so the shared edge itself reads as the
  // separator between consecutive waves -- a real gap before the first
  // structure or after the last is left unlabeled, not invented.
  //
  // Solo mode (no secondaryAnalysis): renders exactly as before the merge,
  // 1-indexed "Wave N". Merged mode: Global renders first (full-height,
  // larger, opaque) then Nested on top (inset band, smaller, translucent,
  // warm palette) -- see GLOBAL_STYLE/NESTED_STYLE for the full cue list.
  if (secondaryAnalysis) {
    renderStructureSet(segments, GLOBAL_STYLE, "Global ", true, data, shapes, annotations)
    renderStructureSet(secondarySegments, NESTED_STYLE, "Nested ", true, data, shapes, annotations)
    // Global/Nested legend now lives in the HTML header row above the plot
    // (see the returned JSX below), not as in-plot annotations -- the
    // plotting area stays completely clean, per explicit requirement.
  } else {
    renderStructureSet(segments, SOLO_STYLE, "", false, data, shapes, annotations)
  }

  // Small padding above/below the raw price extremes so the topmost/
  // bottommost circle markers don't clip flush against the plot edge. The
  // header strip lives in paper space now (HEADER_Y), entirely outside
  // this price-mapped range, so it never needs to factor in here.
  const yPad = (visiblePriceRange[1] - visiblePriceRange[0]) * 0.08

  // Base degree name with any "_global" suffix stripped for display (e.g.
  // "minor_global" -> "Minor"). Merged mode (secondaryAnalysis present)
  // names the title after the degree alone, since the header-row legend +
  // per-header "Global"/"Nested" prefixes already carry that distinction.
  // Separate-cards mode (the default as of 2026-07-20) has no such legend,
  // so `variantLabel` (computed by ElliottWavePanel.tsx) disambiguates
  // "Minor (Global)" from "Minor (Nested)" directly in the title instead.
  const baseDegree = analysis.degree.replace(/_global$/, "")
  const capitalizedDegree = `${baseDegree.charAt(0).toUpperCase()}${baseDegree.slice(1)}`
  const degreeLabel = secondaryAnalysis
    ? `${capitalizedDegree} (Global + Nested)`
    : variantLabel
      ? `${capitalizedDegree} (${variantLabel})`
      : capitalizedDegree
  const titleText = `${symbol} — ${degreeLabel} degree Elliott Wave`

  // Title moved OUT of the Plotly canvas entirely (see the returned JSX) --
  // plain HTML header row above the plot, title left / legend right, so
  // the plotting area stays clean. margin.t only needs to clear the
  // in-plot "Wave N" structure headers now (still paper-space annotations
  // above the candles), not a title row too, so it's smaller than before.
  const layout: Partial<Layout> = {
    paper_bgcolor: BG, plot_bgcolor: BG,
    font: { color: "#cdd6f4" },
    dragmode: "pan", hovermode: "x unified",
    showlegend: false,
    margin: { l: 50, r: 20, t: 46, b: 40 },
    autosize: true,
    // Explicit range on both axes, fed from the same `range`/
    // `visiblePriceRange` state used for zoom/pan tracking -- required so
    // a re-render doesn't undo the user's own zoom/pan (see toNaiveString's
    // module comment for the full root-cause writeup).
    xaxis: {
      gridcolor: GRID, showgrid: true, rangeslider: { visible: false },
      range: [toNaiveString(range[0]), toNaiveString(range[1])],
    },
    yaxis: {
      gridcolor: GRID, showgrid: true, title: { text: "Price", font: { size: 9, color: "#8b8ba0" } },
      range: [visiblePriceRange[0] - yPad, visiblePriceRange[1] + yPad],
    },
    shapes: shapes as Layout["shapes"],
    annotations: annotations as Layout["annotations"],
  }

  return (
    <div style={{ width: "100%" }}>
      {/* Title + legend header row, OUTSIDE the Plotly canvas -- title left,
          Global/Nested legend right (only shown in merged mode), same row.
          Plain HTML/CSS, not Plotly annotations, per explicit requirement
          that the plotting area stay completely clean. */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        gap: 12, padding: "2px 4px 8px", flexWrap: "wrap",
      }}>
        <span style={{ color: "#cdd6f4", fontSize: 13, fontWeight: 600 }}>{titleText}</span>
        {secondaryAnalysis && (
          <div style={{ display: "flex", gap: 14, fontSize: 10.5, color: "#cdd6f4", flexWrap: "wrap" }}>
            <span>
              <span style={{ color: GLOBAL_STYLE.colors[0] }}>●</span> Global — Higher-level Minor Structure
            </span>
            <span>
              <span style={{ color: NESTED_STYLE.colors[0] }}>●</span> Nested — Internal Minor Structure
            </span>
          </div>
        )}
      </div>
      <div style={{ width: "100%", height: 580 }}>
        <Plot
          data={data}
          layout={layout}
          config={{ scrollZoom: true, displayModeBar: true, modeBarButtonsToRemove: ["lasso2d", "select2d"] }}
          style={{ width: "100%", height: "100%" }}
          useResizeHandler
          onRelayout={handleRelayout}
        />
      </div>
    </div>
  )
}
