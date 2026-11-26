/**
 * CVD divergence, as sir defined it (email, 2026-11-26).
 *
 * Between two consecutive swing lows (or two swing highs), compare the price
 * change with the CVD change over the same two candles. Opposite signs are a
 * divergence:
 *
 *   lows   price higher low,  CVD lower low   -> Hidden Bullish   (absorption)
 *          price lower low,   CVD higher low  -> Regular Bullish  (selling exhaustion)
 *   highs  price lower high,  CVD higher high -> Hidden Bearish   (absorption)
 *          price higher high, CVD lower high  -> Regular Bearish  (buying exhaustion)
 *
 * Strength = |ΔCVD| / VolumeAvg(20) at the second point. Below 1.5 is noise and is
 * skipped; above 3.0 is strong. CVD restarts every session, so two points in
 * different sessions are never compared.
 */
import type { ZigZagPoint } from "./types"

export type DivergenceKind = "Hidden Bullish" | "Regular Bullish" | "Hidden Bearish" | "Regular Bearish"

export interface CvdDivergence {
  kind: DivergenceKind
  from: ZigZagPoint
  to: ZigZagPoint
  cvdFrom: number
  cvdTo: number
  dPrice: number
  dCvd: number
  strength: number
  strong: boolean
}

export const WEAK_BELOW = 1.5
export const STRONG_ABOVE = 3.0

/**
 * The CVD session a bar belongs to (Eastern): 6 PM - midnight, midnight - 8 AM,
 * 8 AM to the next 6 PM -- src/analysis/indicators.py calc_cvd. `zoneOffset` is
 * the chart's "Times in" shift (minutes added to Eastern), undone first.
 */
export function cvdSession(t: string, zoneOffset = 0): string {
  const ms = Date.parse(`${t.slice(0, 19)}Z`) - zoneOffset * 60_000
  const d = new Date(ms)
  const h = d.getUTCHours()
  return `${d.toISOString().slice(0, 10)} ${h >= 18 ? 18 : h < 8 ? 0 : 8}`
}

function classify(type: "H" | "L", dPrice: number, dCvd: number): DivergenceKind | null {
  if (dPrice === 0 || dCvd === 0 || Math.sign(dPrice) === Math.sign(dCvd)) return null
  if (type === "L") return dPrice > 0 ? "Hidden Bullish" : "Regular Bullish"
  return dPrice < 0 ? "Hidden Bearish" : "Regular Bearish"
}

export function cvdDivergences(
  points: readonly ZigZagPoint[], times: readonly string[],
  cvd: readonly (number | null)[], volAvg: readonly (number | null)[], zoneOffset = 0,
): CvdDivergence[] {
  const at = new Map(times.map((t, i) => [t, i]))
  const out: CvdDivergence[] = []
  for (const type of ["L", "H"] as const) {
    const pts = points.filter((p) => p.type === type && at.has(p.t))
    for (let k = 1; k < pts.length; k++) {
      const a = pts[k - 1], b = pts[k]
      if (cvdSession(a.t, zoneOffset) !== cvdSession(b.t, zoneOffset)) continue
      const ia = at.get(a.t)!, ib = at.get(b.t)!
      const ca = cvd[ia], cb = cvd[ib], avg = volAvg[ib]
      if (ca == null || cb == null || avg == null || !(avg > 0)) continue
      const dPrice = b.price - a.price, dCvd = cb - ca
      const kind = classify(type, dPrice, dCvd)
      if (!kind) continue
      const strength = Math.abs(dCvd) / avg
      if (strength < WEAK_BELOW) continue
      out.push({ kind, from: a, to: b, cvdFrom: ca, cvdTo: cb, dPrice, dCvd, strength, strong: strength > STRONG_ABOVE })
    }
  }
  return out.sort((x, y) => x.to.t.localeCompare(y.to.t))
}
