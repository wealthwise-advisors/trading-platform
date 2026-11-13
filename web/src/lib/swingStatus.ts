/**
 * Where the current swing stands, for the chart's "Swing now" panel and its
 * protected-level line (2026-11-13: "every detail of the swing").
 *
 * Mirrors the rules in src/analysis/swing_count.py: in an up swing the odd
 * points are highs, and the swing ends when a candle CLOSES at or below the
 * protected low -- the last even point, or the swing's start before there is
 * one. A down swing is the mirror (a close above the protected high).
 */
import type { ZigZagPoint } from "@/lib/types"
import { swingName } from "@/lib/swingHeaders"

export interface SwingStatus {
  swing: number
  name: string
  up: boolean
  last: ZigZagPoint
  /** The level whose close-through ends this swing. */
  protectedPrice: number
  protectedLabel: string
  /** The last odd point the next odd must close beyond, when there is one. */
  lastOdd?: ZigZagPoint
}

export function swingStatus(zz10: readonly ZigZagPoint[]): SwingStatus | null {
  if (!zz10.length) return null
  const swing = Math.max(...zz10.map((p) => p.swing))
  const pts = zz10.filter((p) => p.swing === swing).sort((a, b) => (a.t < b.t ? -1 : a.t > b.t ? 1 : 0))
  const body = pts.filter((p) => p.label !== "0")
  if (!body.length) return null
  const up = body[0].type === "H"
  const evens = body.filter((p) => Number(p.label) % 2 === 0)
  const odds = body.filter((p) => Number(p.label) % 2 === 1)
  let protectedPt: ZigZagPoint | undefined = evens.at(-1) ?? pts.find((p) => p.label === "0")
  if (!protectedPt) {
    // the swing's start is the last point of the swing before it
    const before = zz10.filter((p) => p.swing < swing).sort((a, b) => (a.t < b.t ? -1 : 1))
    protectedPt = before.at(-1)
  }
  if (!protectedPt) return null
  return {
    swing, name: swingName(swing), up, last: body.at(-1)!,
    protectedPrice: protectedPt.price,
    protectedLabel: protectedPt.label === "0" || protectedPt.swing !== swing ? "start" : `point ${protectedPt.label}`,
    lastOdd: odds.at(-1),
  }
}

/** The panel's lines, plain words. */
export function statusLines(st: SwingStatus): string[] {
  const dir = st.up ? "▲ up" : "▼ down"
  const kind = st.last.type === "H" ? "High" : "Low"
  const lines = [
    `<b>Swing ${st.name} ${dir}</b>`,
    `Last 10 Leg point: ${st.last.label}${st.last.structure ? ` (${st.last.structure})` : ""} · ${kind} ${st.last.price.toFixed(2)}`,
    `Swing ends on a close ${st.up ? "at or below" : "above"} ${st.protectedPrice.toFixed(2)} (${st.protectedLabel})`,
  ]
  if (st.lastOdd) {
    lines.push(`Next ${st.up ? "high" : "low"} must close ${st.up ? "above" : "below"} ${st.lastOdd.price.toFixed(2)}`)
  }
  return lines
}
