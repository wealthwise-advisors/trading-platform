/**
 * Which swing points sit on the candle under the cursor, and the hover lines
 * that name them (requested 2026-11-12: "whenever I move to any point, the
 * hover box should say whether it is 10 Leg or 3 Leg").
 */
import type { ReadoutLine } from "@/lib/chartReadout"
import { onDisplayCandle } from "@/lib/resample"

export interface SwingPointInfo {
  /** The bar the point belongs to. */
  t: string
  level: "10 Leg" | "3 Leg" | "1 Leg"
  label: string
  type: "H" | "L"
  price: number
  /** HH / HL / LH / LL, when the level carries it. */
  structure?: string
}

/**
 * The points on the hovered candle. The cursor snaps to a raw bar, but a
 * drawn candle may hold several bars (merged to fit the screen), so a point
 * counts when it is on the same DRAWN candle as the hovered bar.
 */
export function pointsAt(points: readonly SwingPointInfo[], barT: string, candleTimes: readonly string[]): SwingPointInfo[] {
  if (!points.length) return []
  const exact = points.filter((p) => p.t === barT)
  if (exact.length || !candleTimes.length) return exact
  const [hovered] = onDisplayCandle([barT], [...candleTimes])
  return points.filter((p) => onDisplayCandle([p.t], [...candleTimes])[0] === hovered)
}

const LEVEL_ORDER = { "10 Leg": 0, "3 Leg": 1, "1 Leg": 2 } as const

/** "Swing point" heading, then one bullet per point: 10 Leg, then 3 Leg, then 1 Leg. */
export function pointLines(pts: readonly SwingPointInfo[]): ReadoutLine[] {
  if (!pts.length) return []
  const ordered = [...pts].sort((a, b) => LEVEL_ORDER[a.level] - LEVEL_ORDER[b.level])
  return [
    { label: "Swing point on this candle", value: "", kind: "heading" },
    ...ordered.map((p) => ({
      label: `${p.level} point ${p.label}`,
      value: `${p.structure ? `${p.structure} · ` : ""}${p.type === "H" ? "High" : "Low"} ${p.price.toFixed(2)}`,
      bullet: true,
    })),
  ]
}

export interface SwingStart {
  swing: number
  t: string
  price: number
  type: "H" | "L"
  /** The swing's direction: up when its point 1 is a high. */
  up: boolean
}

/**
 * Where each swing (A, B, C ...) starts: its first 10 Leg point -- "0" for the
 * very first swing, point 1 (the break that flipped the trend) for every one
 * after. That is the same place the chart's swing boundary is drawn, so the
 * marker and the boundary always agree. Direction comes from point 1: a high
 * means the swing climbs to it, a low that it falls.
 */
export function swingStarts(points: ReadonlyArray<{ t: string; price: number; type: string; swing: number; label: string }>): SwingStart[] {
  const bySwing = new Map<number, typeof points[number][]>()
  for (const p of points) {
    if (!bySwing.has(p.swing)) bySwing.set(p.swing, [])
    bySwing.get(p.swing)!.push(p)
  }
  const out: SwingStart[] = []
  for (const [swing, grp] of [...bySwing.entries()].sort((a, b) => a[0] - b[0])) {
    const sorted = [...grp].sort((a, b) => (a.t < b.t ? -1 : a.t > b.t ? 1 : 0))
    const first = sorted[0]
    const one = sorted.find((p) => p.label === "1") ?? first
    out.push({ swing, t: first.t, price: first.price, type: first.type as "H" | "L", up: one.type === "H" })
  }
  return out
}
