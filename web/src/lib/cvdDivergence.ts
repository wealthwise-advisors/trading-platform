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
import type { OHLCVRecord, ZigZagPoint } from "./types"
import { buyerSellerSplit, volumeAverageWithContext } from "./volumeAverage"

export type DivergenceKind = "Hidden Bullish" | "Regular Bullish" | "Hidden Bearish" | "Regular Bearish"
/** What a divergence needs of a swing point. */
export type SwingPt = Pick<ZigZagPoint, "t" | "price" | "type">

export interface CvdDivergence<P extends SwingPt = ZigZagPoint> {
  kind: DivergenceKind
  from: P
  to: P
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

export function cvdDivergences<P extends SwingPt>(
  points: readonly P[], times: readonly string[],
  cvd: readonly (number | null)[], volAvg: readonly (number | null)[], zoneOffset = 0,
  opts: { weakBelow?: number; strongAbove?: number } = {},
): CvdDivergence<P>[] {
  const weakBelow = opts.weakBelow ?? WEAK_BELOW, strongAbove = opts.strongAbove ?? STRONG_ABOVE
  const at = new Map(times.map((t, i) => [t, i]))
  const out: CvdDivergence<P>[] = []
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
      if (strength < weakBelow) continue
      out.push({ kind, from: a, to: b, cvdFrom: ca, cvdTo: cb, dPrice, dCvd, strength, strong: strength > strongAbove })
    }
  }
  return out.sort((x, y) => x.to.t.localeCompare(y.to.t))
}

/** Delta per bar (buyers - sellers, sir's split) and CVD, restarting each session --
 *  the same numbers as src/analysis/indicators.py calc_volume_delta / calc_cvd. */
export function deltaAndCvd(bars: ReadonlyArray<Pick<OHLCVRecord, "t" | "h" | "l" | "c" | "v">>, zoneOffset = 0) {
  const delta: (number | null)[] = [], pct: (number | null)[] = [], cvd: (number | null)[] = []
  let run = 0, session = ""
  for (const b of bars) {
    const s = buyerSellerSplit(b)
    const d = s ? s.buyers - s.sellers : 0
    const key = cvdSession(b.t, zoneOffset)
    if (key !== session) { session = key; run = 0 }
    run += d
    delta.push(s ? d : null)
    pct.push(s && b.v ? (d / b.v) * 100 : s ? 0 : null)
    cvd.push(run)
  }
  return { delta, pct, cvd }
}

/** One Market Grid row: the newest bar's Delta, Delta % and CVD, and the newest
 *  divergence between the timeframe's recent 10 Leg points. */
export function orderFlowNow<P extends SwingPt>(
  bars: ReadonlyArray<OHLCVRecord>, points: readonly P[],
  volContext?: { t: string[]; v: (number | null)[] }, volLength = 20,
  opts: { weakBelow?: number; strongAbove?: number; regular?: boolean; hidden?: boolean } = {},
) {
  if (!bars.length) return null
  const { delta, pct, cvd } = deltaAndCvd(bars)
  const n = bars.length - 1
  const divs = points.length > 1
    ? cvdDivergences(points, bars.map((b) => b.t), cvd, volumeAverageWithContext(bars, volContext, volLength), 0, opts)
        .filter((d) => (d.kind.startsWith("Regular") ? opts.regular ?? true : opts.hidden ?? true))
    : []
  return { delta: delta[n], pct: pct[n], cvd: cvd[n], divergence: divs.at(-1) ?? null }
}
