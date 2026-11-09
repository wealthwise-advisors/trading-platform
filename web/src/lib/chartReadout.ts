/**
 * What every chart row reads at the bar under the cursor.
 *
 * thinkorswim shows one vertical line through all its panels and a value box in
 * each of them at once, wherever the mouse is (requested 2026-11-10). Plotly's
 * own hover only speaks for the subplot under the mouse, so the boxes are drawn
 * by ChartCrosshair from what is here.
 *
 * The per-bar series come from the traces the chart actually built, so a box
 * can only list what is drawn: switch a study off and it leaves the box too.
 */

import type { OHLCVRecord } from "./types"
import { buyerSellerSplit } from "./volumeAverage"

export interface ReadoutLine {
  label: string
  value: string
  color?: string
}

export interface ReadoutSeries {
  label: string
  color?: string
  values: ReadonlyArray<number | null>
  digits: number
}

export interface ReadoutRow {
  /** Plotly's axis id for the row: y, y2, y3... */
  axis: string
  title: string
  series: ReadoutSeries[]
  /** Lines that do not change bar to bar: overbought, POC... */
  fixed: ReadoutLine[]
}

interface TraceLike {
  type?: string
  name?: string
  x?: unknown
  y?: unknown
  yaxis?: string
  line?: { color?: unknown }
}

export function formatReadoutNumber(n: number | null | undefined, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return "N/A"
  return n.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

/** "2026-11-09T11:33:00" -> "11/9/26 11:33 AM", as thinkorswim's box prints it. */
export function formatReadoutDate(t: string): string {
  const m = /^\d\d(\d\d)-(\d\d)-(\d\d)[T ](\d\d):(\d\d)/.exec(t)
  if (!m) return t
  const hour = Number(m[4])
  return `${Number(m[2])}/${Number(m[3])}/${m[1]} ${hour % 12 || 12}:${m[5]} ${hour < 12 ? "AM" : "PM"}`
}

/**
 * The traces plotted one point per bar, grouped by row. Identity on `times` is
 * the test: swing lines and trade markers have their own x arrays and are not
 * readings of the bar.
 */
export function seriesByAxis(traces: ReadonlyArray<TraceLike>, times: ReadonlyArray<string>): Map<string, ReadoutSeries[]> {
  const out = new Map<string, ReadoutSeries[]>()
  for (const d of traces) {
    if (d.x !== times || !Array.isArray(d.y) || !d.name) continue
    const axis = d.yaxis ?? "y"
    const list = out.get(axis) ?? []
    list.push({
      label: d.name, values: d.y as (number | null)[], digits: d.name === "Vol" ? 0 : 2,
      color: typeof d.line?.color === "string" ? d.line.color : undefined,
    })
    out.set(axis, list)
  }
  return out
}

/** Index of the bar nearest `value`; `sorted` ascending. -1 when empty. */
export function nearestBarIndex(sorted: ReadonlyArray<number>, value: number): number {
  if (!sorted.length) return -1
  let lo = 0, hi = sorted.length - 1
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (sorted[mid] < value) lo = mid + 1
    else hi = mid
  }
  return lo > 0 && value - sorted[lo - 1] <= sorted[lo] - value ? lo - 1 : lo
}

export function priceLines(bar: OHLCVRecord): ReadoutLine[] {
  return [
    { label: "Date", value: formatReadoutDate(bar.t) },
    { label: "Open", value: formatReadoutNumber(bar.o) },
    { label: "High", value: formatReadoutNumber(bar.h) },
    { label: "Low", value: formatReadoutNumber(bar.l) },
    { label: "Close", value: formatReadoutNumber(bar.c) },
    { label: "Range", value: formatReadoutNumber(bar.h - bar.l) },
  ]
}

export function volumeSplitLines(bar: OHLCVRecord): ReadoutLine[] {
  const s = buyerSellerSplit(bar)
  if (!s) return [{ label: "Buyers", value: "N/A" }, { label: "Sellers", value: "N/A" }]
  return [
    { label: "Buyers", value: `${formatReadoutNumber(s.buyers, 0)} (${(s.buyerPct * 100).toFixed(2)}%)`, color: "#26a69a" },
    { label: "Sellers", value: `${formatReadoutNumber(s.sellers, 0)} (${(s.sellerPct * 100).toFixed(2)}%)`, color: "#ef5350" },
  ]
}

/** One row's box at bar `i`. The price and volume rows add their bar lines. */
export function readoutLines(row: ReadoutRow, bar: OHLCVRecord, i: number, volumeAxis?: string): ReadoutLine[] {
  const series = row.series.map((s) => ({ label: s.label, color: s.color, value: formatReadoutNumber(s.values[i], s.digits) }))
  return [
    ...(row.axis === "y" ? priceLines(bar) : []),
    ...series,
    ...(row.axis === volumeAxis ? volumeSplitLines(bar) : []),
    ...row.fixed,
  ]
}
