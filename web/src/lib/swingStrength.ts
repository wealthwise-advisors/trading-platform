/**
 * Who won a swing, by sir's running total (confirmed 2026-11-10).
 *
 * Each candle's volume is split into buyers (green) and sellers (red) with his
 * formula (lib/volumeAverage.ts). Candle by candle, the HIGHER of the two
 * counts: added when green is higher, subtracted when red is higher. The total
 * left at the end of the swing says who won -- positive green, negative red.
 * Nothing is averaged. The same for the 10 Leg Dev stretch (A to B) and the
 * 3 Leg Dev stretch (a to e).
 *
 * A stretch runs from the bar AFTER its first pivot through the bar of its last
 * pivot: the first pivot's bar is where the previous move ended.
 */

import type { OHLCVRecord } from "./types"
import type { ReadoutLine } from "./chartReadout"
import { price } from "./priceFormat"
import { buyerSellerSplit } from "./volumeAverage"

export interface SwingStrength {
  candles: number
  /** Candles where buyers were higher, and the buyer volume they added. */
  greenLed: number
  added: number
  /** Candles where sellers were higher, and the seller volume they took off. */
  redLed: number
  subtracted: number
  /** added - subtracted: the value left at the end of the swing. */
  net: number
  stronger: "green" | "red" | "even"
  /** False when no candle in the stretch carried volume. */
  hasVolume: boolean
}

export function swingStrength(bars: ReadonlyArray<OHLCVRecord>, from: string, to: string): SwingStrength | null {
  const inside = bars.filter((b) => b.t > from && b.t <= to)
  if (!inside.length) return null
  let added = 0, subtracted = 0, greenLed = 0, redLed = 0, hasVolume = false
  for (const b of inside) {
    const s = buyerSellerSplit(b)
    if (!s) continue
    hasVolume = true
    if (s.buyers > s.sellers) { added += s.buyers; greenLed++ }
    else if (s.sellers > s.buyers) { subtracted += s.sellers; redLed++ }
  }
  const net = added - subtracted
  return {
    candles: inside.length, greenLed, added, redLed, subtracted, net, hasVolume,
    stronger: net > 0 ? "green" : net < 0 ? "red" : "even",
  }
}

export interface SwingBreakeven {
  high: number
  low: number
  volume: number
  /** Sum of typical price x volume over the swing's candles. */
  priceVolume: number
  /** priceVolume / volume: the swing's anchored VWAP. Null without volume. */
  breakeven: number | null
  /** (high + low) / 2: the swing's pure midpoint. */
  equilibrium: number
  /** Cumulative Buyer Control: every candle's buyer volume, added up (not rounded per candle). */
  buyers: number
}

/**
 * Sir's swing levels (2026-11-17). Typical price (H+L+C)/3 x volume, candle by
 * candle; the sum over the swing's total volume is the True Volume Breakeven
 * (the VWAP anchored at the swing's start), and the swing's highest high and
 * lowest low halve to the 50% Swing Equilibrium. Unlike swingStrength, BOTH
 * pivot candles count: his Bar 1 is the swing low itself.
 */
export function swingBreakeven(bars: ReadonlyArray<OHLCVRecord>, from: string, to: string): SwingBreakeven | null {
  const inside = bars.filter((b) => b.t >= from && b.t <= to)
  if (!inside.length) return null
  let high = -Infinity, low = Infinity, volume = 0, priceVolume = 0, buyers = 0
  for (const b of inside) {
    high = Math.max(high, b.h)
    low = Math.min(low, b.l)
    if (b.v == null || !Number.isFinite(b.v)) continue
    volume += b.v
    priceVolume += ((b.h + b.l + b.c) / 3) * b.v
    buyers += b.v * (buyerSellerSplit(b)?.buyerPct ?? 0.5)
  }
  return { high, low, volume, priceVolume, buyers, breakeven: volume > 0 ? priceVolume / volume : null, equilibrium: (high + low) / 2 }
}

const GREEN = "#00c853"
const RED = "#ff6b6b"
const whole = (n: number) => Math.round(n).toLocaleString("en-US")
const signed = (n: number) => (n > 0 ? "+" : n < 0 ? "-" : "") + whole(Math.abs(n))

export interface Dominance {
  side: "buyers" | "sellers" | "even"
  /** The winner's share of all the volume counted, 0-100. */
  share: number
}

/**
 * Who dominated a stretch, and by how much: the winning side's share of the
 * volume that was counted, shown as a plain percentage so 51% and 90% read
 * differently without any graded words (sir found Strong / Moderate / Slight
 * confusing, 2026-11-10).
 */
export function dominance(s: SwingStrength): Dominance {
  const both = s.added + s.subtracted
  if (!both || s.stronger === "even") return { side: "even", share: 50 }
  const share = ((s.stronger === "green" ? s.added : s.subtracted) / both) * 100
  return { side: s.stronger === "green" ? "buyers" : "sellers", share }
}

const pct = (part: number, total: number) => (total ? Math.round((part / total) * 100) : 0)

/** Cumulative Buyer Control as the grid and the hover box print it: "17,002 (89%)". */
export function buyerControl(b: SwingBreakeven): { text: string; side: "buyers" | "sellers" | "even" } {
  if (!(b.volume > 0)) return { text: "—", side: "even" }
  const share = b.buyers / b.volume
  return { text: `${whole(b.buyers)} (${Math.round(share * 100)}%)`, side: share > 0.5 ? "buyers" : share < 0.5 ? "sellers" : "even" }
}

/**
 * One stretch's lines for the hover box, five bullets: buyers, sellers, net,
 * who dominated and how clearly, and the price change. Only the numbers and
 * the verdict carry green or red; labels stay plain.
 */
export function strengthLines(heading: string, s: SwingStrength | null,
                              move?: { from: number; to: number }, levels?: SwingBreakeven | null): ReadoutLine[] {
  const head: ReadoutLine = { label: heading, value: "", kind: "heading" }
  if (!s) return [head, { label: "No bars in this stretch", value: "", bullet: true }]
  if (!s.hasVolume) return [head, { label: "No volume data", value: "", bullet: true }]
  // Sir's Buyer Control (2026-11-17) replaces the 10 Nov winner-takes-all count
  // wherever the swing's levels are known: one rule, one number, everywhere.
  const useLevels = !!levels && levels.volume > 0
  const buyers = useLevels ? levels!.buyers : s.added
  const sellers = useLevels ? levels!.volume - levels!.buyers : s.subtracted
  const both = buyers + sellers
  const d = useLevels ? controlOf(levels!) : dominance(s)
  const tone = d.side === "buyers" ? GREEN : d.side === "sellers" ? RED : undefined
  const lines: ReadoutLine[] = [
    head,
    { label: "Buyers", value: `+${whole(buyers)} (${pct(buyers, both)}%)`, valueColor: GREEN, bullet: true },
    { label: "Sellers", value: `-${whole(sellers)} (${pct(sellers, both)}%)`, valueColor: RED, bullet: true },
    { label: "Net", value: signed(buyers - sellers), valueColor: tone, bullet: true },
    { label: "Dominant", bullet: true, valueColor: tone,
      value: d.side === "even" ? "EVEN" : `${d.side.toUpperCase()} ${Math.round(d.share)}%` },
  ]
  if (move) {
    const pts = move.to - move.from
    lines.push({
      label: "Price change", bullet: true,
      value: `${pts > 0 ? "▲ +" : pts < 0 ? "▼ -" : ""}${Math.abs(pts).toFixed(2)} pts`,
      valueColor: pts > 0 ? GREEN : pts < 0 ? RED : undefined,
    })
  }
  if (levels) {
    lines.push({ label: "Volume Breakeven", value: price(levels.breakeven), bullet: true },
               { label: "50% Equilibrium", value: price(levels.equilibrium), bullet: true })
  }
  return lines
}

/** Who controlled a swing by sir's Buyer Control: buyer volume over all the swing's volume. */
function controlOf(b: SwingBreakeven): Dominance {
  const share = (b.buyers / b.volume) * 100
  return share > 50 ? { side: "buyers", share } : share < 50 ? { side: "sellers", share: 100 - share } : { side: "even", share: 50 }
}

/**
 * Beside a swing's title: who dominated it and by how much, "(Dominant: Buyers
 * 56%)" in green or "(Dominant: Sellers 60%)" in red. Since 2026-11-17 by sir's
 * Buyer Control, the same number as the swing's box and hover -- the 10 Nov
 * winner-takes-all count left two different percentages on one swing.
 */
export function dominantTitle(b: SwingBreakeven | null): string | null {
  if (!b || !(b.volume > 0)) return null
  const d = controlOf(b)
  if (d.side === "even") return `(Dominant: Even 50%)`
  const color = d.side === "buyers" ? GREEN : RED
  return `(<span style="color:${color}"><b>Dominant: ${d.side === "buyers" ? "Buyers" : "Sellers"} ${Math.round(d.share)}%</b></span>)`
}

export interface SwingSpan {
  swing: number
  color: string
  /** The swing's own region on the chart, for finding the swing under the cursor. */
  start: string
  end: string
  /** Times and prices of the stretch's first and last pivots. */
  tenLeg: { from: string; to: string; label: string; fromPrice: number; toPrice: number }
  threeLeg: { from: string; to: string; label: string; fromPrice: number; toPrice: number } | null
  /** The 1 Leg points (a, b, c ...) inside the swing, when there are any. */
  oneLeg?: { from: string; to: string; label: string; fromPrice: number; toPrice: number } | null
  /** The Swing levels figures, shown in the Data Window for the swing under the
   *  cursor (they were boxes over the candles until 2026-11-27). */
  levels?: { range: string; buyerPct: number; breakeven: number; equilibrium: number } | null
}

/** The swing whose region holds bar time `t`, or null. */
export function swingAt(spans: ReadonlyArray<SwingSpan>, t: string): SwingSpan | null {
  return spans.find((s) => t >= s.start && t < s.end) ?? spans.find((s) => t === s.end) ?? null
}

export interface SwingLevelMarks {
  from: string
  to: string
  breakeven: number
  equilibrium: number
  side: "buyers" | "sellers" | "even"
  /** Who led, in words: "Buyers 89%". */
  leader: string
  /** In full, for sir: "Buyers in control (89%)". */
  control: string
  /** Buyers' whole-number share of the swing's volume; sellers are 100 minus it. */
  buyerPct: number
}

/**
 * What the chart draws across one swing for its "Swing levels" study: a line at
 * the Volume Breakeven, a dotted line at the 50% Equilibrium, and who led the
 * swing by Buyer Control -- so swings read side by side, swing to swing,
 * without hovering (2026-11-17). Null when the swing has no volume to weigh.
 */
export function swingLevelMarks(bars: ReadonlyArray<OHLCVRecord>, from: string, to: string): SwingLevelMarks | null {
  const lv = swingBreakeven(bars, from, to)
  if (!lv || lv.breakeven == null) return null
  const buyerShare = lv.buyers / lv.volume
  const side = buyerShare > 0.5 ? "buyers" : buyerShare < 0.5 ? "sellers" : "even"
  const share = Math.round((side === "sellers" ? 1 - buyerShare : buyerShare) * 100)
  const who = side === "buyers" ? "Buyers" : side === "sellers" ? "Sellers" : "Even"
  return { from, to, breakeven: lv.breakeven, equilibrium: lv.equilibrium, side, leader: `${who} ${share}%`,
           control: side === "even" ? "Buyers and sellers even (50%)" : `${who} in control (${share}%)`,
           buyerPct: Math.round(buyerShare * 100) }
}
