// Full-fidelity port of ui/components/charts.py's candlestick_with_trades().
// Indicator math (EMA/RSI/Stoch) is computed server-side (api/serializers.py)
// and delivered as arrays — this component only handles the plotting/shape/
// annotation logic, mirroring the Python trace-by-trace.

import { useEffect, useRef, useState } from "react"
import Plot from "react-plotly.js"
import type { Data, Layout, Shape, Annotations, PlotRelayoutEvent } from "plotly.js"
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
  // Stochastic is off by default -- TradingView-style layouts give the
  // price panel the bulk of the vertical space and keep only RSI as the
  // default secondary panel; Stochastic stays fully wired up (data,
  // hlines, swing-label mirroring) and can be turned back on via this prop
  // without any of that logic needing to be rebuilt.
  showStochastic?: boolean
}

// Display-only aggregation of 1-minute bars into wider buckets, purely so
// each candle gets more horizontal pixels (candle width is driven by how
// many bars are packed into the visible range -- no Plotly line-width
// setting can widen the body itself). Only the candlestick trace's own
// OHLC arrays use this; EMA/RSI/Stoch lines, zigzag swing markers, and
// trade entry/exit markers all keep the original per-minute timestamps,
// since they're plotted on the same continuous date axis and never needed
// to align with candle boundaries in the first place.
function resampleOHLC(bars: OHLCVRecord[], bucketMinutes: number): OHLCVRecord[] {
  if (!bars.length || bucketMinutes <= 1) return bars
  const bucketMs = bucketMinutes * 60_000
  const order: number[] = []
  const buckets = new Map<number, OHLCVRecord[]>()
  for (const b of bars) {
    const ms = new Date(b.t).getTime()
    const key = Math.floor(ms / bucketMs) * bucketMs
    if (!buckets.has(key)) { buckets.set(key, []); order.push(key) }
    buckets.get(key)!.push(b)
  }
  return order.map((key) => {
    const grp = buckets.get(key)!
    return {
      t: grp[0].t,
      o: grp[0].o,
      h: Math.max(...grp.map((g) => g.h)),
      l: Math.min(...grp.map((g) => g.l)),
      c: grp[grp.length - 1].c,
      v: grp.reduce((sum, g) => sum + (g.v ?? 0), 0),
    }
  })
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
  showStochastic = true,
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
  // 9-minute display candles (down from 12-min, a bit thinner) -- 2-hour
  // default window unchanged.
  const candleBars = resampleOHLC(bars, 9)

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
  // active indicator rows. With Stochastic back on (3 indicator rows), each
  // gets 15% (45% total) -- generous enough that RSI(2)/RSI(13) don't read
  // as squeezed, which was the recurring complaint at smaller shares.
  const PRICE_WEIGHT = 0.55
  const indicatorWeight = (1 - PRICE_WEIGHT) / indicatorRows.length
  const domains = rowDomains([PRICE_WEIGHT, ...indicatorRows.map(() => indicatorWeight)], 0.05)

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
    const MIN_HEADER_SPACING_FRACTION = 0.08
    const placedHeaderXs: { xMs: number; level: number }[] = []
    function placeHeaderLevel(xMs: number): number {
      const thresholdMs = totalSpanMs * MIN_HEADER_SPACING_FRACTION
      const colliders = placedHeaderXs.filter((p) => Math.abs(p.xMs - xMs) < thresholdMs)
      const level = colliders.length ? Math.max(...colliders.map((p) => p.level)) + 1 : 0
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
  const rangeSelectorY = (hasSwingHeaders ? 1.13 : 1.02) + extraHeaderRows * HEADER_LEVEL_HEIGHT

  // Default view opens on the last ~2 hours instead of the whole day --
  // aggregation alone couldn't make candles look wide on a full-day view,
  // because "wide" is a function of how many bars are visible at once, not
  // just how much time each one covers. "All" (and the other range-
  // selector buttons) still show/restore the complete range.
  const DEFAULT_WINDOW_MS = 2 * 60 * 60 * 1000

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
        const lo = Math.min(...scope.map((b) => b.l))
        const hi = Math.max(...scope.map((b) => b.h))
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
  const rowOrder = ["price", ...indicatorRows]
  const dynamicAxes: Record<string, unknown> = {}
  rowOrder.forEach((name, idx) => {
    const suffix = axisSuffix[idx]
    const isPrice = idx === 0
    const isBottom = idx === rowOrder.length - 1
    dynamicAxes[`xaxis${suffix}`] = {
      gridcolor: GRID,
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
      title: { text: rowTitles[name], font: { size: 9, color: "#8b8ba0" } },
      domain: domains[idx], anchor: `x${suffix}`,
      fixedrange: !isPrice,
      range: isPrice ? priceYRange : [0, 100],
    }
  })

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
    title: { text: `${symbol} — ${strategyName} · ${dateLabel}`, font: { size: 14, color: "#cdd6f4" },
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
    margin: hasSwingHeaders
      ? { l: 50, r: 20, t: 94 + extraHeaderRows * 23, b: 24 }
      : { l: 50, r: 20, t: 45, b: 24 },
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
    <div ref={containerRef} style={{ width: "100%", height: "100%", minHeight: 420 }}>
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
  )
}
