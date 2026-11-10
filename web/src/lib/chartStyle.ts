/**
 * How the price chart is drawn, from the Style menu: chart type, candle
 * colours, background, extended-hours shading, space after the last bar and a
 * compared symbol (requested 2026-11-10, after thinkorswim's chart settings).
 *
 * Only presentation. Every indicator, the hover box and the strategy keep
 * reading the real bars; a Heikin Ashi or Renko chart changes what is drawn,
 * not what is measured.
 */

import type { OHLCVRecord } from "./types"

export type ChartType = "candles" | "heikin" | "bars" | "line" | "renko"

export const CHART_TYPES: { id: ChartType; label: string }[] = [
  { id: "candles", label: "Candles" },
  { id: "heikin", label: "Heikin Ashi" },
  { id: "bars", label: "OHLC bars" },
  { id: "line", label: "Line" },
  { id: "renko", label: "Renko" },
]

export interface ChartStyle {
  type: ChartType
  up: string
  down: string
  /** thinkorswim's dark maroon instead of the app's background. */
  maroon: boolean
  /** Tint the bars outside 09:30-16:00 ET. */
  shadeExtended: boolean
  /** Empty bars' worth of space after the last bar. */
  rightSpace: number
  /** Renko brick in points; null works one out from the bars. */
  renkoBrick: number | null
  /** A second symbol drawn on its own scale; null for none. */
  compare: string | null
}

export const DEFAULT_CHART_STYLE: ChartStyle = {
  type: "candles", up: "#2dd4bf", down: "#f0576b", maroon: false,
  shadeExtended: true, rightSpace: 3, renkoBrick: null, compare: null,
}

export const MAROON_BG = "#1a0508"
export const CHART_STYLE_STORE_KEY = "autotrader.chartStyle"

const HEX = /^#[0-9a-f]{6}$/i

/** Never throws; anything unrecognised in storage falls back to the default. */
export function loadChartStyle(): ChartStyle {
  try {
    const raw = localStorage.getItem(CHART_STYLE_STORE_KEY)
    if (!raw) return { ...DEFAULT_CHART_STYLE }
    const s = JSON.parse(raw) as Partial<ChartStyle> | null
    if (!s || typeof s !== "object" || Array.isArray(s)) return { ...DEFAULT_CHART_STYLE }
    const d = DEFAULT_CHART_STYLE
    return {
      type: CHART_TYPES.some((c) => c.id === s.type) ? s.type! : d.type,
      up: typeof s.up === "string" && HEX.test(s.up) ? s.up : d.up,
      down: typeof s.down === "string" && HEX.test(s.down) ? s.down : d.down,
      maroon: typeof s.maroon === "boolean" ? s.maroon : d.maroon,
      shadeExtended: typeof s.shadeExtended === "boolean" ? s.shadeExtended : d.shadeExtended,
      rightSpace: typeof s.rightSpace === "number" && s.rightSpace >= 0 && s.rightSpace <= 200
        ? Math.round(s.rightSpace) : d.rightSpace,
      renkoBrick: typeof s.renkoBrick === "number" && s.renkoBrick > 0 ? s.renkoBrick : null,
      compare: typeof s.compare === "string" && /^[A-Z0-9/]{1,8}$/.test(s.compare) ? s.compare : null,
    }
  } catch {
    return { ...DEFAULT_CHART_STYLE }
  }
}

export function saveChartStyle(s: ChartStyle): void {
  try {
    localStorage.setItem(CHART_STYLE_STORE_KEY, JSON.stringify(s))
  } catch {
    // Remembering the choice is a convenience; the chart works without it.
  }
}

/**
 * Heikin Ashi: close = (O+H+L+C)/4, open = midpoint of the previous HA candle
 * (the first one's own (O+C)/2), high and low widened to take both in.
 */
export function heikinAshi(bars: ReadonlyArray<OHLCVRecord>): OHLCVRecord[] {
  const out: OHLCVRecord[] = []
  bars.forEach((b, i) => {
    const c = (b.o + b.h + b.l + b.c) / 4
    const o = i === 0 ? (b.o + b.c) / 2 : (out[i - 1].o + out[i - 1].c) / 2
    out.push({ t: b.t, o, h: Math.max(b.h, o, c), l: Math.min(b.l, o, c), c, v: b.v })
  })
  return out
}

/** A brick size from the data: twice the median bar range, to the tick. */
export function autoRenkoBrick(bars: ReadonlyArray<OHLCVRecord>, tick = 0.25): number {
  const ranges = bars.map((b) => b.h - b.l).filter((r) => r > 0).sort((a, b) => a - b)
  const median = ranges.length ? ranges[Math.floor(ranges.length / 2)] : tick
  return Math.max(tick, Math.round((median * 2) / tick) * tick)
}

/**
 * Renko from closes. A brick forms each time the close moves a full brick
 * beyond the last one; turning round takes two, the usual rule. Each brick is
 * stamped with the bar that completed it, so several can share a time.
 */
export function renkoBricks(bars: ReadonlyArray<OHLCVRecord>, size: number): OHLCVRecord[] {
  if (!bars.length || !(size > 0)) return []
  const out: OHLCVRecord[] = []
  let lo = Math.round(bars[0].c / size) * size
  let hi = lo
  for (const b of bars) {
    while (b.c >= hi + size) {
      out.push({ t: b.t, o: hi, h: hi + size, l: hi, c: hi + size, v: null })
      lo = hi
      hi += size
    }
    while (b.c <= lo - size) {
      out.push({ t: b.t, o: lo, h: lo, l: lo - size, c: lo - size, v: null })
      hi = lo
      lo -= size
    }
  }
  return out
}

const RTH_OPEN = 9 * 60 + 30
const RTH_CLOSE = 16 * 60

function minuteOfDay(t: string): number | null {
  const m = /[T ](\d\d):(\d\d)/.exec(t)
  return m ? Number(m[1]) * 60 + Number(m[2]) : null
}

/**
 * Runs of bars outside 09:30-16:00 ET, as [first bar, last bar] pairs, for
 * shading. Daily and longer bars have no session, so they return nothing.
 */
export function extendedHoursSpans(times: ReadonlyArray<string>, stepMs: number): [string, string][] {
  if (!(stepMs > 0) || stepMs >= 20 * 3_600_000) return []
  const out: [string, string][] = []
  let start: string | null = null
  let prev: string | null = null
  for (const t of times) {
    const m = minuteOfDay(t)
    const outside = m != null && (m < RTH_OPEN || m >= RTH_CLOSE)
    if (outside && start == null) start = t
    if (!outside && start != null) {
      out.push([start, prev!])
      start = null
    }
    prev = t
  }
  if (start != null && prev != null) out.push([start, prev])
  return out
}
