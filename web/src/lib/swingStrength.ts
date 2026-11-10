/**
 * Who pushed harder inside a swing: buyers or sellers.
 *
 * Asked for by sir on 2026-11-10 for every swing, on its 10 Leg Dev stretch
 * (A to B) and its 3 Leg Dev stretch (a to e), shown in the hover. The measure
 * is his buyer/seller split (lib/volumeAverage.ts): each candle's volume is
 * divided by where it closed in its range, and the side with more volume over
 * the stretch is the stronger one. Volume rather than a candle count, because
 * three heavy red candles outweigh ten light green ones.
 *
 * A stretch runs from the bar AFTER its first pivot through the bar of its last
 * pivot: the first pivot's bar is where the previous move ended.
 */

import type { OHLCVRecord } from "./types"
import type { ReadoutLine } from "./chartReadout"
import { buyerSellerSplit } from "./volumeAverage"

export interface SideStats {
  volume: number
  /** Share of the stretch's volume, 0-100. */
  pct: number
  /** Volume per candle in the stretch. */
  avgPerCandle: number
}

export interface SwingStrength {
  candles: number
  green: number
  red: number
  buyers: SideStats
  sellers: SideStats
  stronger: "buyers" | "sellers" | "even"
}

export function swingStrength(bars: ReadonlyArray<OHLCVRecord>, from: string, to: string): SwingStrength | null {
  const inside = bars.filter((b) => b.t > from && b.t <= to)
  if (!inside.length) return null
  let buy = 0, sell = 0, green = 0, red = 0
  for (const b of inside) {
    if (b.c > b.o) green++
    else if (b.c < b.o) red++
    const s = buyerSellerSplit(b)
    if (s) { buy += s.buyers; sell += s.sellers }
  }
  const total = buy + sell
  const n = inside.length
  const side = (v: number): SideStats => ({ volume: v, pct: total ? (v / total) * 100 : 0, avgPerCandle: v / n })
  // With no volume at all the candles are the only evidence left.
  const stronger = total
    ? (buy > sell ? "buyers" : sell > buy ? "sellers" : "even")
    : (green > red ? "buyers" : red > green ? "sellers" : "even")
  return { candles: n, green, red, buyers: side(buy), sellers: side(sell), stronger }
}

const BUY = "#00c853"
const SELL = "#ff6b6b"
const whole = (n: number) => Math.round(n).toLocaleString("en-US")

/** One stretch's lines for the hover box. */
export function strengthLines(heading: string, s: SwingStrength | null, headColor: string): ReadoutLine[] {
  const head = { label: heading, value: "", color: headColor }
  if (!s) return [head, { label: "No bars in this stretch", value: "" }]
  return [
    head,
    { label: "Buyers", value: `${whole(s.buyers.volume)} (${s.buyers.pct.toFixed(0)}%)`, color: BUY },
    { label: "Sellers", value: `${whole(s.sellers.volume)} (${s.sellers.pct.toFixed(0)}%)`, color: SELL },
    { label: "Avg / candle", value: `${whole(s.buyers.avgPerCandle)} / ${whole(s.sellers.avgPerCandle)}` },
    { label: "Green / red candles", value: `${s.green} / ${s.red}` },
    s.stronger === "even"
      ? { label: "Stronger", value: "EVEN" }
      : { label: "Stronger", value: s.stronger === "buyers" ? "BUYERS (green)" : "SELLERS (red)",
          color: s.stronger === "buyers" ? BUY : SELL },
  ]
}

export interface SwingSpan {
  swing: number
  color: string
  /** The swing's own region on the chart, for finding the swing under the cursor. */
  start: string
  end: string
  tenLeg: { from: string; to: string; label: string }
  threeLeg: { from: string; to: string; label: string } | null
}

/** The swing whose region holds bar time `t`, or null. */
export function swingAt(spans: ReadonlyArray<SwingSpan>, t: string): SwingSpan | null {
  return spans.find((s) => t >= s.start && t < s.end) ?? spans.find((s) => t === s.end) ?? null
}
