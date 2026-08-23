// Full-fidelity port of ui/components/charts.py's candlestick_with_trades().
// Indicator math (EMA/RSI/Stoch) is computed server-side (api/serializers.py)
// and delivered as arrays — this component only handles the plotting/shape/
// annotation logic, mirroring the Python trace-by-trace.

import { useEffect, useMemo, useRef, useState } from "react"
import Plot from "react-plotly.js"
import type { Data, Layout, Shape, Annotations, PlotRelayoutEvent } from "plotly.js"
import type { OHLCVRecord, IndicatorSeries, ZigZagResponse, TradeRecord, ZigZagPoint } from "@/lib/types"
import { computeRangebreaks } from "@/lib/rangebreaks"
import { toNaiveString } from "@/lib/isoTime"
import { resampleOHLC, displayBucketMinutes } from "@/lib/resample"
import { buildSessionProfileShapes } from "@/lib/volumeProfileShapes"
import { computeVolumeProfiles } from "@/lib/volumeProfile"
import type { TimePerProfile, RowHeightMode } from "@/lib/volumeProfile"

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
  // Stochastic is off by default -- TradingView-style layouts give the
  // price panel the bulk of the vertical space and keep only RSI as the
  // default secondary panel; Stochastic stays fully wired up (data,
  // hlines, swing-label mirroring) and can be turned back on via this prop
  // without any of that logic needing to be rebuilt.
  showStochastic?: boolean
  // Session VWAP with ±2σ bands, overlaid on the price panel. Same
  // opt-out shape as showStochastic. Draws nothing when the dataset has no
  // volume, regardless of this flag.
  showVwap?: boolean
  /** Initial state of the Volume Profile toggle. The profile itself is
   *  computed in-component from `bars` so its settings can redraw without a
   *  refetch — see lib/volumeProfile.ts. */
  showVolumeProfile?: boolean
}


// Default view opens on the last ~2 hours rather than the whole session.
// Hoisted to module scope because swing-header collision detection (which
// runs earlier in the render) needs the same window to reason about how far
// apart two headers actually appear on screen.
const DEFAULT_WINDOW_MS = 2 * 60 * 60 * 1000

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
  showStochastic = true, showVwap = true, showVolumeProfile = true,
}: CandlestickChartProps) {
  // react-plotly.js's useResizeHandler only listens for window "resize"
  // events -- it never fires when the CONTAINER grows/shrinks from a pure
  // CSS/flex change (KPI row shrinking, footer removal, etc., all of which
  // happened repeatedly this session). That's why "unused space below the
  // indicator panels" kept recurring even as the surrounding layout genuinely
  // got taller: the Card grew, but the already-mounted Plot never learned
  // its container had more room.
  //
  // A ResizeObserver on the wrapping div catches every resize source (flex,
  // grid, KPI/footer changes), not just the browser window -- but calling
  // Plotly.Plots.resize() directly requires importing the full "plotly.js"
  // package a second time (separately from whatever react-plotly.js already
  // resolves internally), which broke the whole page (blank screen) when
  // tried. Dispatching a synthetic window "resize" event instead piggybacks
  // on react-plotly.js's own existing, already-working resize handling --
  // same practical effect, no second Plotly import, no risk.
  // ── VWAP settings (session-only, deliberately not persisted) ───────────
  // The server delivers VWAP at a fixed ±2σ. Rather than refetch when the
  // user changes a deviation, sigma is recovered from that payload --
  // sigma = (upper − vwap) / 2 -- and the bands are rebuilt for any
  // multiplier. Verified exact against a server-side recomputation at 3σ:
  // maximum difference 0.0000000000. So the redraw is instant, needs no round
  // trip, and does not fork the VWAP maths into TypeScript.
  const [vwapOn, setVwapOn] = useState(showVwap)
  const [vwapPanelOpen, setVwapPanelOpen] = useState(false)
  const [devUp, setDevUp] = useState(2)
  const [devDn, setDevDn] = useState(-2)
  // "DAY" is the only timeframe the engine implements -- VWAP resets on the
  // calendar date. It is surfaced as a labelled control anyway so the reset
  // behaviour is visible rather than an unstated assumption.
  const [vwapTimeframe] = useState("DAY")
  const [vwapStyle, setVwapStyle] = useState({
    vwap: { color: "#e879f9", width: 1.8, dash: "solid" },
    upper: { color: "#fde047", width: 1.5, dash: "solid" },
    lower: { color: "#f472b6", width: 1.5, dash: "solid" },
  })

  // ── Volume Profile settings (session-only) ─────────────────────────────
  // Computed locally rather than refetched: bins re-bucket from raw bars, which
  // the delivered histogram cannot reconstruct. See lib/volumeProfile.ts.
  const [vpOn, setVpOn] = useState(showVolumeProfile)
  const [vpPanelOpen, setVpPanelOpen] = useState(false)
  const [vpBins, setVpBins] = useState(48)
  const [vpValueArea, setVpValueArea] = useState(70)
  const [vpOpacity, setVpOpacity] = useState(50)
  const [vpShow, setVpShow] = useState({
    poc: true, vah: true, val: true, profileHigh: false, profileLow: false,
  })
  const [vpRowMode, setVpRowMode] = useState<RowHeightMode>("AUTOMATIC")
  const [vpRowHeight, setVpRowHeight] = useState(1)
  const [vpTimePer, setVpTimePer] = useState<TimePerProfile>("CHART")
  const [vpMultiplier, setVpMultiplier] = useState(1)
  const [vpMaxProfiles, setVpMaxProfiles] = useState(1000)
  const [vpOnExpansion, setVpOnExpansion] = useState(true)
  // Options column of the reference dialog.
  const [vpShowStudy, setVpShowStudy] = useState(true)
  const [vpShowPlotNames, setVpShowPlotNames] = useState(false)
  const [vpShowInputNames, setVpShowInputNames] = useState(false)
  const [vpLeftAxis, setVpLeftAxis] = useState(true)
  const [vpSavedNote, setVpSavedNote] = useState("")

  // ── Save as default / Reset to factory default ─────────────────────────
  // Factory values live here so "reset" has something authoritative to return
  // to; "save as default" writes the current set to localStorage and it is
  // restored on the next mount.
  const VP_FACTORY = {
    bins: 48, valueArea: 70, opacity: 50, rowMode: "AUTOMATIC" as RowHeightMode,
    rowHeight: 1, timePer: "CHART" as TimePerProfile, multiplier: 1,
    maxProfiles: 1000, onExpansion: true,
    show: { poc: true, vah: true, val: true, profileHigh: false, profileLow: false },
    showStudy: true, showPlotNames: false, showInputNames: false, leftAxis: true,
  }
  const VP_STORE_KEY = "autotrader.volumeProfile.defaults"

  const applyVpSettings = (v: typeof VP_FACTORY) => {
    setVpBins(v.bins); setVpValueArea(v.valueArea); setVpOpacity(v.opacity)
    setVpRowMode(v.rowMode); setVpRowHeight(v.rowHeight); setVpTimePer(v.timePer)
    setVpMultiplier(v.multiplier); setVpMaxProfiles(v.maxProfiles)
    setVpOnExpansion(v.onExpansion); setVpShow(v.show)
    setVpShowStudy(v.showStudy); setVpShowPlotNames(v.showPlotNames)
    setVpShowInputNames(v.showInputNames); setVpLeftAxis(v.leftAxis)
  }

  useEffect(() => {
    try {
      const raw = localStorage.getItem(VP_STORE_KEY)
      if (raw) applyVpSettings({ ...VP_FACTORY, ...JSON.parse(raw) })
    } catch {
      /* corrupt or unavailable storage just means factory defaults */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const saveVpDefaults = () => {
    const payload = {
      bins: vpBins, valueArea: vpValueArea, opacity: vpOpacity,
      rowMode: vpRowMode, rowHeight: vpRowHeight, timePer: vpTimePer,
      multiplier: vpMultiplier, maxProfiles: vpMaxProfiles,
      onExpansion: vpOnExpansion, show: vpShow, showStudy: vpShowStudy,
      showPlotNames: vpShowPlotNames, showInputNames: vpShowInputNames,
      leftAxis: vpLeftAxis,
    }
    try {
      localStorage.setItem(VP_STORE_KEY, JSON.stringify(payload))
      setVpSavedNote("Saved — these settings will load next time.")
    } catch {
      setVpSavedNote("Could not save (browser storage unavailable).")
    }
    setTimeout(() => setVpSavedNote(""), 3000)
  }

  const resetVpFactory = () => {
    try { localStorage.removeItem(VP_STORE_KEY) } catch { /* nothing to clear */ }
    applyVpSettings(VP_FACTORY)
    setVpSavedNote("Reset to factory defaults.")
    setTimeout(() => setVpSavedNote(""), 3000)
  }

  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      window.dispatchEvent(new Event("resize"))
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Tracks the user's current x-axis zoom (range-selector button, scroll
  // zoom, or pan), null meaning "no interaction yet, use the default 2-hour
  // window". Needed because the price y-axis range below must be computed
  // from whatever's actually visible on screen -- without this, the y-range
  // stayed permanently locked to the initial 2-hour window's price band, so
  // zooming/panning out (e.g. clicking "All") revealed candles priced
  // outside that band only as blank space: their x/y data was correct, they
  // were just plotted above/below the fixed, now-stale y-axis bounds.
  const [visibleRange, setVisibleRange] = useState<{ start: number; end: number } | null>(null)
  useEffect(() => setVisibleRange(null), [bars])

  const handleRelayout = (ev: PlotRelayoutEvent) => {
    const e = ev as unknown as Record<string, unknown>
    if (e["xaxis.autorange"]) {
      if (!bars.length) return
      setVisibleRange({ start: new Date(bars[0].t).getTime(), end: new Date(bars[bars.length - 1].t).getTime() })
      return
    }
    const r0 = e["xaxis.range[0]"]
    const r1 = e["xaxis.range[1]"]
    if (typeof r0 === "string" && typeof r1 === "string") {
      setVisibleRange({ start: new Date(r0).getTime(), end: new Date(r1).getTime() })
    }
  }

  const t = bars.map((b) => b.t)
  // Display candles are aggregated to suit the VISIBLE window, not to a fixed
  // bucket. This used to be resampleOHLC(bars, 9), which is comfortable in the
  // default 2-hour window but collapses when zoomed out: a 37-hour Globex
  // range put 217 candles in the panel at 2.48px each, so they read as
  // hairlines under the 12px trade markers. The window used here must match
  // the one xRange applies below, or the aggregation and the axis disagree
  // about what is on screen.
  const displayWindowMs = (() => {
    if (bars.length < 2) return DEFAULT_WINDOW_MS
    const first = new Date(bars[0].t).getTime()
    const last = new Date(bars[bars.length - 1].t).getTime()
    if (visibleRange) {
      return Math.max(1, Math.min(last, visibleRange.end) - Math.max(first, visibleRange.start))
    }
    return Math.min(DEFAULT_WINDOW_MS, last - first || DEFAULT_WINDOW_MS)
  })()
  const candleBars = resampleOHLC(bars, displayBucketMinutes(bars, displayWindowMs))

  // Row layout is built dynamically: price is always row 1; RSI(2) and
  // RSI(13) are always the secondary rows; Stochastic is spliced in between
  // them (back on by default -- it was switched off for one round and that
  // turned out to be wrong, it's expected to always be visible). Axis
  // suffixes ("", "2", "3", "4") are assigned by position, so RSI(13)
  // automatically shifts down a slot if Stochastic is ever turned off again.
  const indicatorRows = ["rsi2", ...(showStochastic ? ["stoch"] : []), "rsi13"] as const
  const totalRows = 1 + indicatorRows.length
  const axisSuffix = ["", "2", "3", "4"].slice(0, totalRows)
  const rowIndexOf = (name: (typeof indicatorRows)[number]) => 1 + indicatorRows.indexOf(name)
  const suffixOf = (name: (typeof indicatorRows)[number]) => axisSuffix[rowIndexOf(name)]

  // Price panel stays the dominant focus; the rest splits evenly across the
  // active indicator rows.
  //
  // Raised 0.55 -> 0.62 (candles read as too compact against the three
  // indicator rows). These are SHARES of the plotting area, so on their own a
  // bigger price share can only shrink the indicator rows. Their absolute
  // height is clawed back from three places that all freed real estate:
  // tighter inter-row spacing (0.05 -> 0.035), the range-selector no longer
  // occupying a margin row of its own, and swing headers capped at two
  // stacked rows instead of climbing to five.
  //
  // Raised again 0.62 -> 0.68 on a follow-up pass, with row spacing tightened
  // 0.035 -> 0.028 to keep the indicator rows off the floor. Measured at a
  // 683px container across the three passes:
  //
  //   price panel      221px -> 312px -> 350px   (+58% overall)
  //   each indicator    60px ->  64px ->  55px
  //
  // 55px still shows an RSI trace against its 0/50/100 gridlines, which is
  // what those rows are for. Going further starts costing legibility rather
  // than whitespace, so this is the last increase without a taller container.
  //
  // Total height is deliberately NOT increased -- see the minHeight note on
  // the wrapper div; forcing this taller than the parent Card clips the
  // bottom rows off entirely rather than shrinking them.
  const PRICE_WEIGHT = 0.68
  const ROW_SPACING = 0.028
  const indicatorWeight = (1 - PRICE_WEIGHT) / indicatorRows.length
  const domains = rowDomains(
    [PRICE_WEIGHT, ...indicatorRows.map(() => indicatorWeight)], ROW_SPACING,
  )

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

  const data: Data[] = []
  const shapes: Partial<Shape>[] = []
  const annotations: Partial<Annotations>[] = []

  // ── Row 1: Candlestick (9-min display bars) + EMA9/21 (still per-minute) ──
  data.push({
    type: "candlestick",
    x: candleBars.map((b) => b.t), open: candleBars.map((b) => b.o), high: candleBars.map((b) => b.h),
    low: candleBars.map((b) => b.l), close: candleBars.map((b) => b.c),
    name: "Price", showlegend: false,
    increasing: { line: { color: GREEN, width: 1.3 } }, decreasing: { line: { color: RED, width: 1.3 } },
    xaxis: "x", yaxis: "y",
  } as unknown as Data)

  // EMA lines kept thinner than the candles (1.0 vs 1.7) so candlesticks
  // stay the primary price representation, but clearly visible in their
  // own right rather than faded out.
  data.push(
    { type: "scatter", mode: "lines", x: t, y: indicators.ema9, name: "EMA9",
      line: { color: "#ffab40", width: 1.0 }, opacity: 0.85, xaxis: "x", yaxis: "y" } as unknown as Data,
    { type: "scatter", mode: "lines", x: t, y: indicators.ema21, name: "EMA21",
      line: { color: "#80cbc4", width: 1.0 }, opacity: 0.85, xaxis: "x", yaxis: "y" } as unknown as Data,
  )

  // ── Session VWAP ±2σ ──────────────────────────────────────────────────
  // Magenta: distinct from EMA9 orange, EMA21 teal, both ZigZags (yellow /
  // sky blue) and every SWING_COLORS entry.
  //
  // The bands are drawn first so the VWAP line sits on top of them, and the
  // upper band fills down to the lower one via fill:"tonexty" -- which
  // requires the two to be adjacent traces in this order.
  //
  // A dataset with no volume serialises these as all-null, so the guard is on
  // the DATA, not just the prop: an explicit showVwap can't force a line that
  // has nothing behind it.
  const vwapHasData = (indicators.vwap ?? []).some((v) => v != null)
  if (vwapOn && vwapHasData) {
    // Rebuild each band at the user's multiplier. devDn is stored negative,
    // matching the reference dialog's "num dev dn = -2.0" convention, so it is
    // added rather than subtracted.
    const base = indicators.vwap ?? []
    const shipped = indicators.vwap_upper ?? []
    const atDev = (mult: number) =>
      base.map((v, i) => {
        const u = shipped[i]
        if (v == null || u == null) return null
        return v + mult * ((u - v) / 2)
      })

    const upper = atDev(devUp)
    const lower = atDev(devDn)
    const hover = (label: string) => `<b>${label}</b>: %{y:.2f}<extra></extra>`
    data.push(
      { type: "scatter", mode: "lines", x: t, y: upper, name: "UpperBand",
        line: { color: vwapStyle.upper.color, width: vwapStyle.upper.width,
                dash: vwapStyle.upper.dash },
        hovertemplate: hover("UpperBand"),
        legendgroup: "vwap", xaxis: "x", yaxis: "y" } as unknown as Data,
      { type: "scatter", mode: "lines", x: t, y: lower, name: "LowerBand",
        line: { color: vwapStyle.lower.color, width: vwapStyle.lower.width,
                dash: vwapStyle.lower.dash },
        hovertemplate: hover("LowerBand"),
        legendgroup: "vwap", xaxis: "x", yaxis: "y" } as unknown as Data,
      { type: "scatter", mode: "lines", x: t, y: indicators.vwap, name: "VWAP",
        line: { color: vwapStyle.vwap.color, width: vwapStyle.vwap.width,
                dash: vwapStyle.vwap.dash },
        hovertemplate: hover("VWAP"),
        legendgroup: "vwap", xaxis: "x", yaxis: "y" } as unknown as Data,
    )
  }

  // ── Volume Profile ────────────────────────────────────────────────────
  // Drawn on its own x-axis (xaxis5) that OVERLAYS the price row rather than
  // taking a subplot column of its own. A column would cost ~15% of the chart
  // width permanently and force the three indicator rows to shrink to match,
  // or they would misalign with the candles above them. Overlaying keeps the
  // full price width and is what TradingView and thinkorswim do.
  //
  // The overlay axis is reversed, so bars grow leftward from the right edge
  // and stay out of the way of recent price action. It is capped at a third of
  // a quarter of the plot so the histogram cannot swamp the candles behind it.
  // Local recomputation, so bins / value-area% / opacity all redraw instantly.
  // Falls back to the server's profile only to decide whether volume exists at
  // all; with no volume both produce nothing.
  const vpSlices = useMemo(
    () => computeVolumeProfiles(bars, {
      timePer: vpTimePer, multiplier: vpMultiplier, maxProfiles: vpMaxProfiles,
      rowMode: vpRowMode, customRowHeight: vpRowHeight,
      bins: vpBins, valueAreaPct: vpValueArea / 100,
    }),
    [bars, vpTimePer, vpMultiplier, vpMaxProfiles, vpRowMode, vpRowHeight,
     vpBins, vpValueArea],
  )
  // The right-hand overlay only makes sense for a single whole-chart profile.
  // Per-session profiles are anchored in time instead, each inside its own
  // session's x-range, which is the only way several of them can coexist.
  const vpSingle = vpTimePer === "CHART" && vpSlices.length === 1
  const vpLocal = vpSlices.length ? vpSlices[vpSlices.length - 1].profile
                                  : { prices: [], volumes: [], poc: null, val: null,
                                      vah: null, binSize: null }
  const vpVisible = vpOn && vpShowStudy && vpSingle && vpOnExpansion && vpLocal.prices.length > 0
  if (vpVisible) {
    const vp = { ...vpLocal, bin_size: vpLocal.binSize }
    const inValueArea = (p: number) =>
      vp.val != null && vp.vah != null && p >= vp.val && p <= vp.vah
    data.push({
      type: "bar", orientation: "h",
      x: vp.volumes, y: vp.prices,
      width: vp.bin_size ?? undefined,
      // Value-area buckets are brighter; the rest recede. Same hue so the
      // profile still reads as one object.
      marker: {
        // One opacity control drives both tiers; outside-the-area buckets keep
        // a fixed fraction of it so the value area stays distinguishable at
        // any setting.
        color: vp.prices.map((p) => {
          const a = vpOpacity / 100
          return inValueArea(p)
            ? `rgba(56,189,248,${(a * 0.68).toFixed(3)})`
            : `rgba(56,189,248,${(a * 0.26).toFixed(3)})`
        }),
      },
      name: "Volume Profile",
      hovertemplate: "<b>Volume Profile</b><br>%{y:.2f}: %{x:,.0f}<extra></extra>",
      xaxis: "x5", yaxis: "y", showlegend: true,
    } as unknown as Data)
  }


  // Session-anchored profiles (time per profile = DAY / WEEK). Geometry lives
  // in lib/volumeProfileShapes.ts so its x-boundary handling can be tested.
  if (vpOn && vpShowStudy && !vpSingle && vpSlices.length) {
    shapes.push(...buildSessionProfileShapes(vpSlices, vpOpacity, vpShow))
  }

  // ── ZigZag overlay with per-swing numbering ───────────────────────────
  const zz10 = showZigzag ? zigzag.zigzag_10 : []
  const zz3 = showZigzag ? zigzag.zigzag_3 : []

  // 10-leg swing group boundaries, computed once up front -- used to draw
  // the swing rectangles further below. The 3-leg zigzag's own `swing` field
  // is its TRUE parent major swing -- computed server-side by
  // calc_nested_zigzag() (api/serializers.py), which runs the minor zigzag
  // independently within each major swing's own bar window, so containment
  // (never bleeding into the next swing) and the letter reset are already
  // guaranteed by construction. No client-side time-boundary lookup needed.
  const bySwing10 = new Map<number, ZigZagPoint[]>()
  for (const p of zz10) {
    if (!bySwing10.has(p.swing)) bySwing10.set(p.swing, [])
    bySwing10.get(p.swing)!.push(p)
  }
  const swingGroups = [...bySwing10.entries()].sort((a, b) => a[0] - b[0])

  // Every 10-leg point is ALSO a 3-leg point at the exact same price/time
  // (a major swing extreme is always also a minor one) -- that shared point
  // is already labeled by the 10-leg overlay's own circle, so it's excluded
  // here entirely (no letter, no circle) rather than drawn a second time.
  const zz10TimeSet = new Set(zz10.map((p) => p.t))
  const zz3Labelable = zz3.filter((p) => !zz10TimeSet.has(p.t))
  // Per parent swing, the ordered list of 3-leg letters inside it -- lets
  // the swing header show "3 Leg Dev (A to H)" alongside the existing
  // "(1.1 to 1.5)" range.
  const regionLettersBySwing = new Map<number, string[]>()
  for (const p of zz3Labelable) {
    if (!regionLettersBySwing.has(p.swing)) regionLettersBySwing.set(p.swing, [])
    regionLettersBySwing.get(p.swing)!.push(p.label)
  }
  const regionLetters: string[][] = swingGroups.map(([swingNum]) => regionLettersBySwing.get(swingNum) ?? [])

  if (zz3.length) {
    data.push({
      type: "scatter", mode: "lines", x: zz3.map((p) => p.t), y: zz3.map((p) => p.price),
      name: "ZigZag (3L)", line: { color: "#f0c040", width: 1.0, dash: "dot" },
      hoverinfo: "skip", xaxis: "x", yaxis: "y",
    } as unknown as Data)
    for (const [ptype, color] of [["H", "#ff6b6b"], ["L", "#69f0ae"]] as const) {
      const pts = zz3Labelable.filter((p) => p.type === ptype)
      if (pts.length) {
        data.push({
          type: "scatter", mode: "text+markers", x: pts.map((p) => p.t), y: pts.map((p) => p.price),
          marker: { symbol: "circle", size: 23, color: BG, line: { color, width: 1.6 } },
          text: pts.map((p) => p.label), textposition: "middle center",
          textfont: { color: "white", size: 10, family: "Arial" },
          showlegend: false,
          hovertemplate: `<b>${ptype === "H" ? "High" : "Low"} (3L) %{text}</b><br>%{x}<br>@ %{y:.2f}<extra></extra>`,
          xaxis: "x", yaxis: "y",
        } as unknown as Data)
      }
    }
  }

  // Hoisted out of the `if` block below so the layout/margin/title code
  // further down (which needs to reserve enough vertical room for however
  // many swing-header rows collision avoidance actually produced) can read
  // the final value. HEADER_LEVEL_HEIGHT is hoisted alongside it so the
  // title/range-selector's own upward scaling grows at the EXACT same rate
  // as the header rows themselves -- two independent literals here drifting
  // apart is exactly what caused the title-collides-with-tallest-header bug
  // this was fixed for (2026-08-02).
  let maxHeaderLevel = 0
  const HEADER_LEVEL_HEIGHT = 0.036

  if (zz10.length) {
    data.push({
      type: "scatter", mode: "lines", x: zz10.map((p) => p.t), y: zz10.map((p) => p.price),
      name: "ZigZag (10L)", line: { color: "#2196f3", width: 1.2, dash: "dot" },
      hoverinfo: "skip", xaxis: "x", yaxis: "y",
    } as unknown as Data)

    // ── Swing boundary rectangles + headers (span all 4 panels via yref="paper") ──

    const totalSpanMs = t.length > 1 ? new Date(t[t.length - 1]).getTime() - new Date(t[0]).getTime() : 0
    // Two headers overlap or not according to how far apart they are ON
    // SCREEN, which is governed by the visible window -- not by the full
    // session. Measuring against totalSpanMs was the real cause of the
    // climbing-staircase labels: the chart opens on a 2-hour window, so on a
    // full trading session 8% of the TOTAL span is wider than everything
    // actually on screen, every header "collided" with every other, and each
    // one was pushed a row higher than the last.
    const visibleSpanMs = visibleRange
      ? visibleRange.end - visibleRange.start
      : Math.min(DEFAULT_WINDOW_MS, totalSpanMs || DEFAULT_WINDOW_MS)

    // ── Collision avoidance for swing headers ──────────────────────────
    // Every swing gets a header (never omitted), placed at the base row by
    // default. A header only moves to a HIGHER row when it's genuinely
    // close enough in time to an already-placed header to collide with it
    // -- never as a blanket "every other swing" rule (tried and reverted:
    // that changed swing 2's treatment for no reason tied to swing 2
    // itself). This is the same proximity-based stacking pattern used
    // elsewhere in this codebase for decluttering point labels, applied
    // here to header annotations instead.
    // How close two headers' xMid positions can be (as a fraction of the
    // whole chart's visible time range) before they're considered a real
    // collision needing a row bump -- text content/format never changes,
    // only which row a header lands on. 0.03 (tuned back when short swings
    // got an abbreviated, narrower header) was too small once EVERY header
    // became full-length text (2026-08-02, full-audit): dense clusters of
    // full "Swing N (X to Y) | 3 Leg Dev (...)" headers still overlapped
    // on the same row because the threshold didn't reflect how much wider
    // full-length text actually needs. Widened to a value that keeps
    // typical full-header text clear of its neighbor at realistic chart
    // widths -- an approximation (no live text-width measurement is
    // available before Plotly renders), not a pixel-exact bound.
    // As a fraction of the VISIBLE window. A full header is roughly
    // "(9.0 to 9.1) | 3 Leg Dev (A to H)" -- about a seventh of the plot
    // width at this font size, so headers closer than that genuinely need
    // separating and anything further apart can share row 0.
    const MIN_HEADER_SPACING_FRACTION = 0.14
    const placedHeaderXs: { xMs: number; level: number }[] = []
    function placeHeaderLevel(xMs: number): number {
      const thresholdMs = visibleSpanMs * MIN_HEADER_SPACING_FRACTION
      const colliders = placedHeaderXs.filter((p) => Math.abs(p.xMs - xMs) < thresholdMs)
      // Take the LOWEST row this header can occupy without hitting a
      // neighbour -- not one above the highest collider.
      //
      // `max(collider levels) + 1` made a run of evenly-spaced swings climb
      // monotonically: swing 5 at row 0, 6 at row 1, 7 at row 2, and so on,
      // because each new header collided with the one before it and stepped
      // above it. Visually that reads as swing labels drifting further and
      // further from the chart as the number goes up -- reported as
      // inconsistent label spacing, and the reason swing 5 looked "right"
      // while 6 through 9 did not.
      //
      // A header only actually needs to clear the rows its OWN colliders sit
      // on. Once a header is far enough from row 0's occupant, row 0 is free
      // again, so a dense run settles into 0,1,0,1 instead of 0,1,2,3.
      // ...but never more than two rows deep. An unbounded search still
      // produced a staircase wherever three or more headers fell inside one
      // threshold width (swings 5, 6 and 7 landed on rows 2, 3 and 4), which
      // is the drift being reported. Two alternating rows read as a regular
      // pattern; a five-step climb reads as a bug. When every row is already
      // occupied by a collider, take the one whose nearest neighbour is
      // furthest away -- the least-bad slot rather than a brand new row.
      const MAX_HEADER_LEVELS = 2
      const taken = new Set(colliders.map((p) => p.level))
      let level = 0
      while (level < MAX_HEADER_LEVELS && taken.has(level)) level++
      if (level >= MAX_HEADER_LEVELS) {
        let bestLevel = 0
        let bestGap = -1
        for (let l = 0; l < MAX_HEADER_LEVELS; l++) {
          const onRow = colliders.filter((p) => p.level === l)
          const gap = onRow.length
            ? Math.min(...onRow.map((p) => Math.abs(p.xMs - xMs)))
            : Number.POSITIVE_INFINITY
          if (gap > bestGap) { bestGap = gap; bestLevel = l }
        }
        level = bestLevel
      }
      placedHeaderXs.push({ xMs, level })
      maxHeaderLevel = Math.max(maxHeaderLevel, level)
      return level
    }

    swingGroups.forEach(([swingNum, grp], i) => {
      const x0 = grp[0].t
      const x1 = i + 1 < swingGroups.length ? swingGroups[i + 1][1][0].t : t[t.length - 1]
      const color = SWING_COLORS[(swingNum - 1) % SWING_COLORS.length]

      shapes.push({
        type: "rect", xref: "x", yref: "paper",
        x0, x1, y0: 0, y1: 1,
        fillcolor: "rgba(0,0,0,0)",
        line: { color, width: 1.1, dash: "dot" },
        layer: "below",
      })
      const firstLabel = grp[0].label
      const lastLabel = grp[grp.length - 1].label
      const xMid = grp[Math.floor(grp.length / 2)].t
      // Every swing header uses the IDENTICAL format, font, color, and
      // alignment -- full text always, no abbreviation. The only thing that
      // ever varies is which row it sits on, when a real neighbor is too
      // close (placeHeaderLevel(), below).
      //
      // A 2-way vertical stagger was tried and reverted (made alternating
      // swings float inconsistently into the toolbar row) because it
      // staggered EVERY swing by parity, not just the ones that actually
      // collided. An arbitrary "every other swing" skip/abbreviate rule was
      // also tried and reverted, as was a proportional width-based
      // abbreviation rule (2026-08-02): both made SOME swings render a
      // shorter header than others (including swing 1 itself, once it was
      // narrow enough) -- inconsistent formatting read as a bug regardless
      // of how principled the underlying rule was. Collision avoidance is
      // now handled ENTIRELY by row placement instead: text format is never
      // the variable, so every header is always identical to swing 1's.
      const letters = regionLetters[i]
      const legPart = letters.length
        ? ` | 3 Leg Dev (${letters[0]} to ${letters[letters.length - 1]})`
        : ""
      const headerText = `<b>Swing ${swingNum}</b><br>(${firstLabel} to ${lastLabel})${legPart}`
      const headerLevel = placeHeaderLevel(new Date(xMid).getTime())
      annotations.push({
        x: xMid, y: 1.015 + headerLevel * HEADER_LEVEL_HEIGHT, xref: "x", yref: "paper", yanchor: "bottom",
        text: headerText,
        showarrow: false, font: { color, size: 10 }, align: "center",
      })
      data.push({
        type: "scatter", mode: "markers", x: [x0], y: [grp[0].price],
        marker: { symbol: "star", size: 10, color, line: { color: "white", width: 0.6 } },
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
        marker: { symbol: "circle", size: 24, color: BG, line: { color, width: 1.8 } },
        text: pts.map((p) => p.label), textposition: "middle center",
        textfont: { color: "white", size: 10, family: "Arial" },
        hovertemplate: "<b>Swing %{text}</b><br>%{x}<br>@ %{y:.2f}<extra></extra>",
        xaxis: "x", yaxis: "y",
      } as unknown as Data)
    }

    // ── Same decimal labels mirrored on whichever indicator rows are active ──
    const byTime = new Map(t.map((ts, i) => [ts, i]))
    const nearestIdx = (ts: string) => byTime.get(ts) ?? 0
    const borderColors = zz10.map((p) => (p.type === "H" ? RED : GREEN))
    const panelValues: Record<(typeof indicatorRows)[number], (number | null)[]> = {
      rsi2: indicators.rsi2, stoch: indicators.stoch_k, rsi13: indicators.rsi13,
    }
    for (const name of indicatorRows) {
      const suffix = suffixOf(name)
      const vals = panelValues[name]
      data.push({
        type: "scatter", mode: "text+markers",
        x: zz10.map((p) => p.t), y: zz10.map((p) => vals[nearestIdx(p.t)]),
        marker: { size: 20, color: BG, line: { color: borderColors, width: 1.6 } },
        text: zz10.map((p) => p.label), textposition: "middle center",
        textfont: { size: 9, color: "white", family: "Arial" },
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

  // ── RSI(2) / [Stoch K&D] / RSI(13) -- axes assigned dynamically ────────
  const rsi2Suffix = suffixOf("rsi2")
  data.push({
    type: "scatter", mode: "lines", x: t, y: indicators.rsi2, name: "RSI(2)",
    line: { color: "#ce93d8", width: 1.1 }, hovertemplate: "RSI(2): %{y:.1f}<extra></extra>",
    xaxis: `x${rsi2Suffix}`, yaxis: `y${rsi2Suffix}`,
  } as unknown as Data)
  if (showStochastic) {
    const stochSuffix = suffixOf("stoch")
    data.push(
      { type: "scatter", mode: "lines", x: t, y: indicators.stoch_k, name: "%K",
        line: { color: "#4fc3f7", width: 1.1 }, hovertemplate: "%%K: %{y:.1f}<extra></extra>",
        xaxis: `x${stochSuffix}`, yaxis: `y${stochSuffix}` } as unknown as Data,
      { type: "scatter", mode: "lines", x: t, y: indicators.stoch_d, name: "%D",
        line: { color: "#f48fb1", width: 1.0, dash: "dot" }, hovertemplate: "%%D: %{y:.1f}<extra></extra>",
        xaxis: `x${stochSuffix}`, yaxis: `y${stochSuffix}` } as unknown as Data,
    )
  }
  const rsi13Suffix = suffixOf("rsi13")
  data.push({
    type: "scatter", mode: "lines", x: t, y: indicators.rsi13, name: "RSI(13)",
    line: { color: "#ffcc80", width: 1.1 }, hovertemplate: "RSI(13): %{y:.1f}<extra></extra>",
    xaxis: `x${rsi13Suffix}`, yaxis: `y${rsi13Suffix}`,
  } as unknown as Data)

  // Overbought/oversold reference lines (hline equivalents) per active row
  const hlines: [string, number, string][] = [
    [rsi2Suffix, 94, RED], [rsi2Suffix, 2, GREEN],
    ...(showStochastic ? ([[suffixOf("stoch"), 80, RED], [suffixOf("stoch"), 20, GREEN]] as [string, number, string][]) : []),
    [rsi13Suffix, 70, RED], [rsi13Suffix, 30, GREEN],
  ]
  for (const [suffix, level, color] of hlines) {
    shapes.push({
      type: "line", xref: "paper", yref: `y${suffix}` as Shape["yref"],
      x0: 0, x1: 1, y0: level, y1: level,
      line: { color, dash: "dash", width: 0.8 },
    })
  }

  const hasSwingHeaders = showZigzag && zz10.length > 0
  // maxHeaderLevel (set above by placeHeaderLevel() while building swing
  // headers) is how many EXTRA rows collision avoidance actually needed --
  // 0 when no two headers were ever close enough to collide. Everything
  // below that used to assume swing headers always occupy exactly one row
  // now needs to reserve room for however many rows were really used, or a
  // stacked header would just collide with the range-selector/title instead
  // of a neighboring swing.
  const extraHeaderRows = hasSwingHeaders ? maxHeaderLevel : 0
  // The range-selector's y is relative to the price axis's own (smaller)
  // domain, while the title's y=1.05 is relative to the whole plot area --
  // so this needs a bigger raw number than the title to land at roughly the
  // same physical height (hand-tuned, not exact). Nudged up from 1.09 to
  // 1.13 to sit closer to where Plotly's native modebar (camera/zoom/pan/
  // home icons, top-right) naturally renders. Swing headers sit lower still
  // (y=1.015 + stacked rows -- see placeHeaderLevel() above) so nothing in
  // this compact top strip overlaps, even when headers stack.
  // The range-selector's y is measured against the PRICE ROW's own domain,
  // while everything else up here (title, swing headers) is measured against
  // the whole paper. Those are different units, so the old code adding a
  // paper-sized `extraHeaderRows * HEADER_LEVEL_HEIGHT` straight onto a
  // price-row y was mixing them -- the buttons drifted by the wrong amount
  // whenever headers stacked. Converting through the price row's share of
  // the paper makes one paper unit mean one paper unit for both.
  const priceRowFraction = domains[0][1] - domains[0][0]
  const paperToPriceRow = (d: number) => d / priceRowFraction
  // Target: sit on the same strip as Plotly's native modebar (camera / zoom /
  // pan / home, top-right), which renders in the top margin rather than on
  // the paper. 0.115 of the paper above the top edge lands in that strip at
  // the container heights this chart actually gets; it is an approximation,
  // since the modebar's offset is in device pixels and not queryable here.
  const RANGE_SELECTOR_PAPER_OFFSET = hasSwingHeaders ? 0.115 : 0.03
  const rangeSelectorY =
    1 + paperToPriceRow(RANGE_SELECTOR_PAPER_OFFSET + extraHeaderRows * HEADER_LEVEL_HEIGHT)

  // DEFAULT_WINDOW_MS is defined at module scope -- aggregation alone
  // couldn't make candles look wide on a full-day view, because "wide" is a
  // function of how many bars are visible at once, not just how much time
  // each one covers. "All" (and the other range-selector buttons) still
  // show/restore the complete range.

  // Price panel's Y-range must be computed from the bars actually inside
  // the CURRENTLY VISIBLE x-window (the user's zoom/pan via visibleRange,
  // falling back to the default 2-hour window before any interaction), NOT
  // the whole day -- using the full day's high/low here was the real reason
  // candles looked short/flat by default: the axis was scaled to fit a much
  // bigger price range than what's actually visible, so the visible candles
  // only filled a fraction of the panel's height. Tight 1.5% padding on top
  // of the CORRECT (windowed) range is what actually makes them read as
  // tall. Recomputing this per visibleRange (rather than hardcoding the
  // 2-hour window every render) is what keeps candles from being plotted
  // outside the y-axis bounds -- and therefore invisible -- once the user
  // zooms/pans to a window with a different price band.
  const priceYRange: [number, number] | undefined = bars.length
    ? (() => {
        const lastMs = new Date(bars[bars.length - 1].t).getTime()
        const windowStartMs = visibleRange ? visibleRange.start : lastMs - DEFAULT_WINDOW_MS
        const windowEndMs = visibleRange ? visibleRange.end : lastMs
        const visible = bars.filter((b) => {
          const ms = new Date(b.t).getTime()
          return ms >= windowStartMs && ms <= windowEndMs
        })
        const scope = visible.length ? visible : bars
        let lo = Math.min(...scope.map((b) => b.l))
        let hi = Math.max(...scope.map((b) => b.h))
        const barLo = lo, barHi = hi

        // Overlays drawn on this panel have to be inside its range or they
        // are silently invisible -- Plotly clips rather than complains.
        //
        // Session VWAP accumulates from the session OPEN while this range is
        // built from the visible window (the last two hours by default), so
        // on a trending day the VWAP legitimately sits well outside the
        // window's high/low. That is exactly what happened when VWAP shipped:
        // all three traces were present and legended, and every one of them
        // was drawn below the floor of the axis -- range [4540.3, 4591.7] for
        // a VWAP spanning 4499.1 to 4538.2.
        const idxInWindow: number[] = []
        bars.forEach((b, i) => {
          const ms = new Date(b.t).getTime()
          if (ms >= windowStartMs && ms <= windowEndMs) idxInWindow.push(i)
        })
        const finite = (xs: (number | null | undefined)[]) =>
          xs.filter((v): v is number => typeof v === "number" && Number.isFinite(v))
        const pick = (arr?: (number | null)[]) =>
          arr ? finite((idxInWindow.length ? idxInWindow : bars.map((_, i) => i)).map((i) => arr[i])) : []

        if (vwapOn && vwapHasData) {
          // All three series count, with no cap on how far they widen the
          // axis. A capped version was tried first (bands admitted only while
          // they stayed inside twice the bars' span) and it silently dropped
          // the one that mattered: on the default synthetic ES view the three
          // series need 119.1 points against a 51-point bar span -- 2.33x --
          // so −2σ sat entirely below the floor and only two of the three
          // lines ever appeared.
          //
          // The trade-off is real: on a wide-band session the candles
          // compress to make room. That is what the reference platform does
          // too, and a band you cannot see is not worth protecting candle
          // height for. Turning VWAP off restores the tight bars-only scale.
          // Scale the shipped ±2σ envelope to whatever the user selected, or
          // widening the bands would push them straight back outside the axis.
          const baseV = pick(indicators.vwap)
          const shippedU = pick(indicators.vwap_upper)
          const sigma = baseV.map((v, i) =>
            shippedU[i] != null ? (shippedU[i] - v) / 2 : 0)
          const all = [
            ...baseV,
            ...baseV.map((v, i) => v + devUp * sigma[i]),
            ...baseV.map((v, i) => v + devDn * sigma[i]),
          ]
          if (all.length) {
            lo = Math.min(lo, ...all)
            hi = Math.max(hi, ...all)
          }
        }

        // Whatever the overlays did, the candles themselves must still fit.
        lo = Math.min(lo, barLo)
        hi = Math.max(hi, barHi)
        const pad = (hi - lo) * 0.004
        return [lo - pad, hi + pad]
      })()
    : undefined

  // Pad the x-axis range a few bars beyond the first/last candle so the
  // edge tick labels (e.g. the last time on the right) aren't clipped by
  // sitting exactly on the plot boundary. Bar timestamps are naive
  // "wall clock" strings with no timezone marker -- new Date(...) parses
  // them as local time, so the padded boundary must be re-serialized with
  // local getters too (never toISOString(), which forces UTC and would
  // shift the range by the browser's UTC offset relative to the bars).
  const xRange = (() => {
    if (t.length < 2) return undefined
    const first = new Date(t[0]).getTime()
    const last = new Date(t[t.length - 1]).getTime()
    const barMs = (last - first) / (t.length - 1)
    const pad = barMs * 3
    // Mirrors priceYRange's fallback: default 2-hour window until the user
    // zooms/pans, then follow that same visibleRange so x and y never
    // disagree about which window is showing (a later re-render -- new
    // trade data, a resize -- would otherwise snap x back to the 2-hour
    // default while y stayed at the user's wider window, stretching a still
    // 2-hour-wide slice of candles across a much taller price axis).
    const windowStart = visibleRange ? Math.max(first, visibleRange.start) : Math.max(first, last - DEFAULT_WINDOW_MS)
    const windowEnd = visibleRange ? Math.min(last, visibleRange.end) : last
    return [toNaiveString(windowStart), toNaiveString(windowEnd + pad)]
  })()

  const spikeAxis = {
    showspikes: true, spikemode: "across" as const, spikesnap: "cursor" as const,
    spikethickness: 1, spikedash: "dot" as const, spikecolor: "#6b6b8a",
  }

  // Axis definitions are built per active row (price + whichever indicator
  // rows are on) instead of 4 hardcoded blocks, so RSI(13) correctly takes
  // over the bottom-axis role (tick labels, automargin) whenever Stochastic
  // is off and it becomes the last row.
  const rowTitles: Record<string, string> = { price: "Price", rsi2: "RSI(2)", stoch: "Stoch", rsi13: "RSI(13)" }
  // Keyed on `bars`, not on `t` -- `t` is rebuilt every render, so memoising
  // against it would recompute every time and defeat the point.
  const rangebreaks = useMemo(() => computeRangebreaks(bars.map((b) => b.t)), [bars])

  // POC / VAH / VAL as horizontal levels across the price panel, matching the
  // reference platform. Solid for the point of control, dashed for the value
  // area bounds -- one is a single price, the others are a band's edges.
  const vpLevels: { value: number; label: string; color: string; dash: string }[] = []
  if (vpVisible) {
    const { poc, vah, val } = vpLocal
    if (vpShow.poc && poc != null) vpLevels.push({ value: poc, label: "POC", color: "#38bdf8", dash: "solid" })
    if (vpShow.vah && vah != null) vpLevels.push({ value: vah, label: "VAHigh", color: "#7dd3fc", dash: "dash" })
    if (vpShow.val && val != null) vpLevels.push({ value: val, label: "VALow", color: "#7dd3fc", dash: "dash" })
    // ProfileHigh / ProfileLow are the outer edges of the profile's own price
    // range -- the top of the highest bucket and the bottom of the lowest.
    const half = (vpLocal.binSize ?? 0) / 2
    const hi = vpLocal.prices.length ? vpLocal.prices[vpLocal.prices.length - 1] + half : null
    const lo = vpLocal.prices.length ? vpLocal.prices[0] - half : null
    if (vpShow.profileHigh && hi != null)
      vpLevels.push({ value: hi, label: "ProfileHigh", color: "#94a3b8", dash: "dot" })
    if (vpShow.profileLow && lo != null)
      vpLevels.push({ value: lo, label: "ProfileLow", color: "#94a3b8", dash: "dot" })
  }
  // "Show plot names": Plotly has no per-trace on-chart label, so each level
  // gets a small annotation pinned at its right-hand end -- the same thing the
  // reference platform draws beside its plots.
  if (vpShowPlotNames) {
    for (const lv of vpLevels) {
      annotations.push({
        x: 1, xref: "paper", xanchor: "right",
        y: lv.value, yref: "y", yanchor: "middle",
        text: lv.label, showarrow: false,
        font: { size: 9, color: lv.color },
        bgcolor: "rgba(11,17,32,0.75)", borderpad: 2,
      } as Partial<Annotations>)
    }
  }

  for (const lv of vpLevels) {
    // Zero-length scatter carrying the hover text, so POC/VAHigh/VALow appear
    // in the unified tooltip the way the reference panel lists them.
    data.push({
      type: "scatter", mode: "lines", x: t, y: t.map(() => lv.value),
      name: lv.label, line: { color: lv.color, width: 1.2, dash: lv.dash },
      hovertemplate: `<b>${lv.label}</b>: %{y:.2f}<extra></extra>`,
      legendgroup: "vp", xaxis: "x", yaxis: "y",
    } as unknown as Data)
  }

  const rowOrder = ["price", ...indicatorRows]
  const dynamicAxes: Record<string, unknown> = {}
  rowOrder.forEach((name, idx) => {
    const suffix = axisSuffix[idx]
    const isPrice = idx === 0
    const isBottom = idx === rowOrder.length - 1
    dynamicAxes[`xaxis${suffix}`] = {
      gridcolor: GRID,
      // Every row shares the price row's x, but rangebreaks are not inherited
      // through `matches` -- each axis needs its own copy or the indicator
      // panels stay stretched over the skipped periods and drift out of
      // alignment with the candles above them.
      rangebreaks,
      ...(isPrice
        ? {
            showgrid: true,
            rangeslider: { visible: false },
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
            range: xRange,
          }
        : { matches: "x" }),
      domain: [0, 1] as [number, number],
      anchor: `y${suffix}`,
      showticklabels: isBottom,
      // tickformat forced to time-only -- Plotly's default date-axis
      // behavior auto-inserts a one-off date label (e.g. "Jul 8, 2026") at
      // the start of the axis when ticks span less than a day, which is
      // redundant with the date already in the chart title. An explicit
      // format with no date component suppresses that bookend entirely.
      ...(isBottom ? { automargin: true, tickfont: { size: 11 }, tickformat: "%H:%M" } : {}),
      ...spikeAxis,
    }
    dynamicAxes[`yaxis${suffix}`] = {
      gridcolor: GRID, showgrid: true,
      // "Left axis" from the reference dialog. Left is Plotly's default, so
      // unticking it moves the price scale to the right-hand side.
      ...(isPrice ? { side: (vpLeftAxis ? "left" : "right") as "left" | "right" } : {}),
      title: { text: rowTitles[name], font: { size: 9, color: "#8b8ba0" } },
      domain: domains[idx], anchor: `x${suffix}`,
      fixedrange: !isPrice,
      range: isPrice ? priceYRange : [0, 100],
    }
  })

  // Overlay axis for the profile. Reversed so bars extend leftward from the
  // right edge; capped so the histogram occupies at most a third of the width.
  if (vpVisible) {
    const maxVol = Math.max(...vpLocal.volumes, 1)
    dynamicAxes["xaxis5"] = {
      overlaying: "x", side: "top", anchor: "y",
      range: [maxVol * 4, 0],       // reversed; 4x cap => bars use <= 1/4 width
      showgrid: false, zeroline: false, showticklabels: false,
      fixedrange: true,
    }
  }

  const layout: Partial<Layout> = {
    // Plotly's title defaults to yref:"container" (positioned against the
    // WHOLE figure, margins included) while the range-selector buttons
    // position against the price axis's own "paper" (just that row's
    // domain) -- two different coordinate systems, which is why matching
    // y-numbers didn't land them on the same visual row last time (title
    // ended up higher, buttons lower/colliding with the swing labels).
    // Forcing the title onto yref:"paper" too makes both reference the same
    // anchor point (top of the price row), so the same y now means the same
    // row for both.
    // title's yref:"paper" scales against the whole plotting area (all 4
    // rows combined); the range-selector's y scales against just the price
    // row's own (smaller) domain -- so the same raw y number isn't the same
    // physical offset for both. y:1.02 here vs. rangeSelectorY (1.06) for
    // the buttons is a hand-tuned attempt to land them in the same visual
    // strip; nudge these two numbers together if a screenshot shows they're
    // still offset.
    // "Show input names": the reference platform appends the study's inputs to
    // its on-chart label, e.g. VolumeProfile(AUTOMATIC, 1.0, CHART, 1, ...).
    title: { text: `${symbol} — ${strategyName} · ${dateLabel}` + (
      vpOn && vpShowStudy && vpShowInputNames
        ? `<br><span style="font-size:10px;color:#7dd3fc">VolumeProfile(${vpRowMode}, ${vpRowHeight}, ${vpTimePer}, ${vpMultiplier}, ${vpOnExpansion ? "Yes" : "No"}, ${vpMaxProfiles}, ${vpShow.poc ? "Yes" : "No"}, ${(vpShow.vah || vpShow.val) ? "Yes" : "No"}, ${vpValueArea}, ${vpOpacity})</span>`
        : ""), font: { size: 14, color: "#cdd6f4" },
             xref: "paper", yref: "paper", x: 0.5, xanchor: "center",
             // Gap above the header base (1.015) widened 0.06 -> 0.11
             // (2026-08-02, full-audit): both title and headers scale by the
             // same extraHeaderRows*HEADER_LEVEL_HEIGHT amount, so the GAP
             // between them stays constant at any stack depth -- 0.06 was
             // only ever enough clearance for a single-line header; a 2-line
             // header (the common case) needs more room at the same gap, or
             // the title visually collides with the tallest stacked row.
             y: (hasSwingHeaders ? 1.125 : 1.05) + extraHeaderRows * HEADER_LEVEL_HEIGHT, yanchor: "bottom" },
    paper_bgcolor: BG, plot_bgcolor: BG,
    font: { color: "#cdd6f4" },
    dragmode: "pan", hovermode: "x unified",
    // Plotly's own NATIVE legend, on -- matches api/report/charts.py's
    // _base_layout exactly (same bgcolor/borderwidth, default position, no
    // custom overlay component). Custom-built alternatives (a floating
    // ChartLegendCard overlay, a tab-row toggle button) were both tried and
    // didn't work as well as just using what the static HTML report
    // already does successfully.
    showlegend: true,
    legend: { bgcolor: "rgba(0,0,0,0.3)", borderwidth: 0 },
    // t trimmed from 95 -> 88 -- less unnecessary top padding above the
    // range-selector/title strip, closer to the top edge of the chart. b
    // trimmed 32 -> 24 too -- the bottom axis now shows time-only labels
    // (no more redundant date), which need less reserved height.
    // t trimmed 94 -> 74: the range-selector no longer occupies a band of its
    // own between the modebar and the title, so that row's worth of reserved
    // space is returned to the plotting area -- which is where the indicator
    // rows get back most of the height the larger PRICE_WEIGHT took from them.
    // t trimmed again 74 -> 62 (and 23 -> 21 per stacked header row): that
    // strip is reserved space above the plot, so every pixel taken off it is
    // a pixel the candles get. Kept a modest step on purpose -- the title and
    // the swing headers are positioned as PAPER fractions, so a taller paper
    // shrinks the gap between them in real pixels, and cutting too hard here
    // is what re-creates the title-collides-with-header bug this block has
    // already been through twice.
    margin: hasSwingHeaders
      ? { l: 50, r: 20, t: 62 + extraHeaderRows * 21, b: 22 }
      : { l: 50, r: 20, t: 38, b: 22 },
    // No fixed height here on purpose -- the wrapping container stretches to
    // fill the available vertical space (matching the taller right-panel
    // column), and autosize + the Plot's own height:100% style pick that up.
    autosize: true,
    ...(dynamicAxes as Partial<Layout>),
    shapes: shapes as Layout["shapes"],
    annotations: annotations as Layout["annotations"],
  }

  return (
    // Real height comes from ResultsPage's flex-1 min-h-0 chain (hero row ->
    // Tabs -> App.tsx's viewport-bound scroll div). minHeight must stay a
    // true floor, not a target -- raising it to 620 broke RSI(2)/RSI(13)
    // entirely: whenever the real flex-computed height came in under 620px,
    // this div was forced taller than its parent Card's actual box, and
    // since Card clips overflow, everything past the bottom of that box
    // (i.e. the two indicator rows, which render last) got sliced off
    // instead of just being small. 420 is low enough to only kick in on
    // genuinely tiny viewports.
    <div ref={containerRef}
         style={{ width: "100%", height: "100%", minHeight: 420,
                  display: "flex", flexDirection: "column" }}>
      {/* VWAP controls. The gear sits beside the toggle so the settings are
          discoverable from the thing they configure, rather than buried in a
          global preferences screen. */}
      <div className="shrink-0 flex items-center gap-2 pb-1.5 text-xs relative">
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input type="checkbox" checked={vwapOn}
                 onChange={(e) => setVwapOn(e.target.checked)} />
          <span>VWAP</span>
        </label>
        {/* Deliberately NOT disabled when the indicator is off.
            A gear greyed to 40% next to a bright one reads as missing rather
            than as unavailable, and clicking it did nothing at all -- which is
            exactly how the Volume Profile gear below came to be reported as
            absent. Clicking now switches the indicator on and opens its panel,
            which is what someone reaching for the settings wanted anyway. */}
        <button
          type="button"
          aria-label="VWAP settings"
          title={vwapOn ? "VWAP settings" : "Turn VWAP on and open its settings"}
          onClick={() => { if (!vwapOn) setVwapOn(true); setVwapPanelOpen(true) }}
          className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5
                     hover:bg-white/10"
        >⚙</button>
        {vwapOn && (
          <span className="text-muted-foreground">
            dev {devDn.toFixed(1)} / +{devUp.toFixed(1)}
          </span>
        )}

        <span className="mx-1 text-white/15">|</span>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input type="checkbox" checked={vpOn}
                 onChange={(e) => setVpOn(e.target.checked)} />
          <span>Volume Profile</span>
        </label>
        <button
          type="button"
          aria-label="Volume Profile settings"
          title={vpOn ? "Volume Profile settings" : "Turn Volume Profile on and open its settings"}
          onClick={() => { if (!vpOn) setVpOn(true); setVpPanelOpen(true) }}
          className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5
                     hover:bg-white/10"
        >⚙</button>
        {vpOn && (
          <span className="text-muted-foreground">
            {vpBins} rows · VA {vpValueArea}%
          </span>
        )}

        {vpPanelOpen && vpOn && (
          <div className="absolute left-52 top-7 z-20 w-80 max-h-[70vh] overflow-y-auto rounded-lg border border-white/12
                          bg-[#0b1120] p-3 shadow-xl space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-sm">VolumeProfile Customizing</span>
              <button type="button" className="text-muted-foreground hover:text-foreground"
                      onClick={() => setVpPanelOpen(false)} aria-label="Close">✕</button>
            </div>
            <div className="flex gap-2 border-b border-white/8 pb-2">
              <button type="button" onClick={saveVpDefaults} aria-label="Save as default"
                      className="rounded border border-white/12 bg-white/5 px-2 py-1
                                 hover:bg-white/10">Save as default</button>
              <button type="button" onClick={resetVpFactory} aria-label="Reset to factory default"
                      className="rounded border border-white/12 bg-white/5 px-2 py-1
                                 hover:bg-white/10">Reset to factory default</button>
            </div>
            {vpSavedNote && (
              <p className="text-[#7dd3fc]">{vpSavedNote}</p>
            )}

            <label className="flex items-center gap-2">
              <span className="w-32 text-muted-foreground">value area percent</span>
              <input type="number" min={1} max={100} step={5} value={vpValueArea}
                     onChange={(e) => setVpValueArea(Number(e.target.value))}
                     className="flex-1 rounded border border-white/10 bg-white/5 px-2 py-1
                                text-foreground" />
            </label>
            <label className="flex items-center gap-2">
              <span className="w-32 text-muted-foreground">opacity</span>
              <input type="number" min={5} max={100} step={5} value={vpOpacity}
                     onChange={(e) => setVpOpacity(Number(e.target.value))}
                     className="flex-1 rounded border border-white/10 bg-white/5 px-2 py-1
                                text-foreground" />
            </label>
            <label className="flex items-center gap-2">
              <span className="w-32 text-muted-foreground">price per row height</span>
              <select value={vpRowMode} aria-label="price per row height mode"
                      onChange={(e) => setVpRowMode(e.target.value as RowHeightMode)}
                      className="flex-1 rounded border border-white/10 bg-white/5 px-2 py-1
                                 text-foreground">
                {["AUTOMATIC", "MANUAL"].map((m) => (
                  <option key={m} value={m} className="bg-[#0b1120] text-[#e6edf3]">{m}</option>
                ))}
              </select>
            </label>
            <label className={`flex items-center gap-2 ${vpRowMode === "AUTOMATIC" ? "opacity-40" : ""}`}>
              <span className="w-32 text-muted-foreground">custom row height</span>
              <input type="number" min={0.05} step={0.25} value={vpRowHeight}
                     disabled={vpRowMode === "AUTOMATIC"}
                     onChange={(e) => setVpRowHeight(Number(e.target.value))}
                     className="flex-1 rounded border border-white/10 bg-white/5 px-2 py-1
                                text-foreground" />
            </label>
            <label className={`flex items-center gap-2 ${vpRowMode === "MANUAL" ? "opacity-40" : ""}`}>
              <span className="w-32 text-muted-foreground">rows (bins)</span>
              <input type="number" min={6} max={240} step={6} value={vpBins}
                     disabled={vpRowMode === "MANUAL"}
                     onChange={(e) => setVpBins(Number(e.target.value))}
                     className="flex-1 rounded border border-white/10 bg-white/5 px-2 py-1
                                text-foreground" />
            </label>

            <div className="pt-1 border-t border-white/8 space-y-2">
              <label className="flex items-center gap-2">
                <span className="w-32 text-muted-foreground">time per profile</span>
                <select value={vpTimePer} aria-label="time per profile"
                        onChange={(e) => setVpTimePer(e.target.value as TimePerProfile)}
                        className="flex-1 rounded border border-white/10 bg-white/5 px-2 py-1
                                   text-foreground">
                  {["CHART", "DAY", "WEEK"].map((m) => (
                    <option key={m} value={m} className="bg-[#0b1120] text-[#e6edf3]">{m}</option>
                  ))}
                </select>
              </label>
              <label className="flex items-center gap-2">
                <span className="w-32 text-muted-foreground">multiplier</span>
                <input type="number" min={1} max={30} step={1} value={vpMultiplier}
                       onChange={(e) => setVpMultiplier(Number(e.target.value))}
                       className="flex-1 rounded border border-white/10 bg-white/5 px-2 py-1
                                  text-foreground" />
              </label>
              <label className="flex items-center gap-2">
                <span className="w-32 text-muted-foreground">profiles</span>
                <input type="number" min={1} max={1000} step={1} value={vpMaxProfiles}
                       onChange={(e) => setVpMaxProfiles(Number(e.target.value))}
                       className="flex-1 rounded border border-white/10 bg-white/5 px-2 py-1
                                  text-foreground" />
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={vpOnExpansion} aria-label="on expansion"
                       onChange={(e) => setVpOnExpansion(e.target.checked)} />
                <span>on expansion <span className="text-muted-foreground">
                  (draw the whole-chart profile in the space right of price)</span></span>
              </label>
            </div>

            <div className="space-y-1 pt-2 border-t border-white/8">
              <div className="text-muted-foreground mb-1">Options</div>
              {([
                ["Show study", vpShowStudy, setVpShowStudy],
                ["Show plot names", vpShowPlotNames, setVpShowPlotNames],
                ["Show input names", vpShowInputNames, setVpShowInputNames],
                ["Left axis", vpLeftAxis, setVpLeftAxis],
              ] as [string, boolean, (v: boolean) => void][]).map(([label, val, set]) => (
                <label key={label} className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={val} aria-label={label}
                         onChange={(e) => set(e.target.checked)} />
                  <span>{label}</span>
                </label>
              ))}
            </div>

            <div className="space-y-1 pt-2 border-t border-white/8">
              <div className="text-muted-foreground mb-1">Plots</div>
              {([
                ["show point of control", "poc"],
                ["show VAHigh", "vah"],
                ["show VALow", "val"],
                ["show ProfileHigh", "profileHigh"],
                ["show ProfileLow", "profileLow"],
              ] as [string, "poc" | "vah" | "val" | "profileHigh" | "profileLow"][]).map(([label, key]) => (
                <label key={key} className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={vpShow[key]}
                         aria-label={label}
                         onChange={(e) => setVpShow((v) => ({ ...v, [key]: e.target.checked }))} />
                  <span>{label}</span>
                </label>
              ))}
            </div>

            <p className="text-muted-foreground">
              The profile is rebuilt in the browser, so every control here
              redraws immediately.
            </p>
          </div>
        )}

        {vwapPanelOpen && vwapOn && (
          <div className="absolute left-0 top-7 z-20 w-72 rounded-lg border border-white/12
                          bg-[#0b1120] p-3 shadow-xl space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-sm">VWAP settings</span>
              <button type="button" className="text-muted-foreground hover:text-foreground"
                      onClick={() => setVwapPanelOpen(false)} aria-label="Close">✕</button>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <label className="space-y-1">
                <span className="text-muted-foreground">num dev dn</span>
                <input type="number" step="0.5" value={devDn}
                       onChange={(e) => setDevDn(Number(e.target.value))}
                       className="w-full rounded border border-white/10 bg-white/5 px-2 py-1
                                  text-foreground" />
              </label>
              <label className="space-y-1">
                <span className="text-muted-foreground">num dev up</span>
                <input type="number" step="0.5" value={devUp}
                       onChange={(e) => setDevUp(Number(e.target.value))}
                       className="w-full rounded border border-white/10 bg-white/5 px-2 py-1
                                  text-foreground" />
              </label>
            </div>

            <label className="flex items-center gap-2">
              <span className="w-20 text-muted-foreground">time frame</span>
              <select value={vwapTimeframe} disabled
                      className="flex-1 rounded border border-white/10 bg-white/5 px-2 py-1
                                 text-foreground disabled:opacity-60"
                      aria-label="VWAP timeframe">
                <option className="bg-[#0b1120] text-[#e6edf3]" value="DAY">DAY</option>
              </select>
            </label>

            <div className="space-y-1.5">
              {([
                ["VWAP", "vwap"],
                ["UpperBand", "upper"],
                ["LowerBand", "lower"],
              ] as [string, "vwap" | "upper" | "lower"][]).map(([label, key]) => (
                <div key={key} className="flex items-center gap-2">
                  <span className="w-20 text-muted-foreground">{label}</span>
                  <input
                    type="color"
                    value={vwapStyle[key].color}
                    onChange={(e) => setVwapStyle((v) => ({
                      ...v, [key]: { ...v[key], color: e.target.value },
                    }))}
                    className="h-6 w-8 cursor-pointer rounded border border-white/10 bg-transparent"
                    aria-label={`${label} colour`}
                  />
                  <select
                    value={vwapStyle[key].width}
                    onChange={(e) => setVwapStyle((v) => ({
                      ...v, [key]: { ...v[key], width: Number(e.target.value) },
                    }))}
                    className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5
                               text-foreground"
                    aria-label={`${label} width`}
                  >
                    {[1, 1.5, 2, 2.5, 3, 4].map((w) => (
                      <option key={w} value={w} className="bg-[#0b1120] text-[#e6edf3]">
                        {w}px
                      </option>
                    ))}
                  </select>
                  <select
                    value={vwapStyle[key].dash}
                    onChange={(e) => setVwapStyle((v) => ({
                      ...v, [key]: { ...v[key], dash: e.target.value },
                    }))}
                    className="rounded border border-white/10 bg-white/5 px-1.5 py-0.5
                               text-foreground"
                    aria-label={`${label} style`}
                  >
                    {["solid", "dash", "dot"].map((d) => (
                      <option key={d} value={d} className="bg-[#0b1120] text-[#e6edf3]">
                        {d}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>

            <p className="text-muted-foreground">
              Bands are rebuilt from the session σ already computed for this
              range, so changes redraw immediately.
            </p>
          </div>
        )}
      </div>

      <div className="flex-1 min-h-0">
      <Plot
        data={data}
        layout={layout}
        config={{
          scrollZoom: true, displayModeBar: true,
          modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
        }}
        style={{ width: "100%", height: "100%" }}
        useResizeHandler
        onRelayout={handleRelayout}
      />
      </div>
    </div>
  )
}
