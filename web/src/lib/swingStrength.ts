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

const GREEN = "#00c853"
const RED = "#ff6b6b"
const whole = (n: number) => Math.round(n).toLocaleString("en-US")
const signed = (n: number) => (n > 0 ? "+" : n < 0 ? "-" : "") + whole(Math.abs(n))

export interface Dominance {
  side: "buyers" | "sellers" | "even"
  /** How clearly: the winner's share of all the volume counted. */
  strength: "Strong" | "Moderate" | "Slight" | null
  share: number
}

/**
 * Who dominated a stretch, and how clearly: the winning side's share of the
 * volume that was counted. 65% or more is Strong, 55% or more Moderate, under
 * that Slight -- so 51/49 does not read like 90/10.
 */
export function dominance(s: SwingStrength): Dominance {
  const both = s.added + s.subtracted
  if (!both || s.stronger === "even") return { side: "even", strength: null, share: 50 }
  const share = ((s.stronger === "green" ? s.added : s.subtracted) / both) * 100
  return {
    side: s.stronger === "green" ? "buyers" : "sellers",
    strength: share >= 65 ? "Strong" : share >= 55 ? "Moderate" : "Slight",
    share,
  }
}

const pct = (part: number, total: number) => (total ? Math.round((part / total) * 100) : 0)

/**
 * One stretch's lines for the hover box, five bullets: buyers, sellers, net,
 * who dominated and how clearly, and the price change. Only the numbers and
 * the verdict carry green or red; labels stay plain.
 */
export function strengthLines(heading: string, s: SwingStrength | null,
                              move?: { from: number; to: number }): ReadoutLine[] {
  const head: ReadoutLine = { label: heading, value: "", kind: "heading" }
  if (!s) return [head, { label: "No bars in this stretch", value: "", bullet: true }]
  if (!s.hasVolume) return [head, { label: "No volume data", value: "", bullet: true }]
  const both = s.added + s.subtracted
  const d = dominance(s)
  const tone = d.side === "buyers" ? GREEN : d.side === "sellers" ? RED : undefined
  const lines: ReadoutLine[] = [
    head,
    { label: "Buyers", value: `+${whole(s.added)} (${pct(s.added, both)}%)`, valueColor: GREEN, bullet: true },
    { label: "Sellers", value: `-${whole(s.subtracted)} (${pct(s.subtracted, both)}%)`, valueColor: RED, bullet: true },
    { label: "Net", value: signed(s.net), valueColor: tone, bullet: true },
    { label: "Dominant", bullet: true, valueColor: tone,
      value: d.side === "even" ? "EVEN" : `${d.side.toUpperCase()} · ${d.strength}` },
  ]
  if (move) {
    const pts = move.to - move.from
    lines.push({
      label: "Price change", bullet: true,
      value: `${pts > 0 ? "▲ +" : pts < 0 ? "▼ -" : ""}${Math.abs(pts).toFixed(2)} pts`,
      valueColor: pts > 0 ? GREEN : pts < 0 ? RED : undefined,
    })
  }
  return lines
}

/** The tag beside a swing's title on the chart: "▲ BUYERS" or "▼ SELLERS". */
export function dominanceTag(s: SwingStrength | null): { text: string; color: string } | null {
  if (!s || !s.hasVolume) return null
  const d = dominance(s)
  if (d.side === "even") return { text: "◆ EVEN", color: "#9ca3af" }
  return d.side === "buyers"
    ? { text: `▲ BUYERS${d.strength === "Strong" ? " · STRONG" : ""}`, color: GREEN }
    : { text: `▼ SELLERS${d.strength === "Strong" ? " · STRONG" : ""}`, color: RED }
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
}

/** The swing whose region holds bar time `t`, or null. */
export function swingAt(spans: ReadonlyArray<SwingSpan>, t: string): SwingSpan | null {
  return spans.find((s) => t >= s.start && t < s.end) ?? spans.find((s) => t === s.end) ?? null
}
