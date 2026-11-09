/**
 * The VolumeAvg study under the price chart -- volume bars, their moving
 * average, and each candle's volume split into buyers and sellers.
 *
 * Specified by sir on 2026-11-09, against thinkorswim's VolumeAvg (20):
 *
 *   Red candle    seller % = (High - Close) / (High - Low)
 *   Green candle  buyer %  = (Close - Low)  / (High - Low)
 *
 * Those are one formula: (High - Close) / Range is exactly 1 - (Close - Low) /
 * Range, so the split below does not need to know the candle's colour.
 *
 * The % is applied to the candle's OWN volume, as his formula sheet does
 * (1,500,000 x 80% = 1,200,000 with a 20-period average of 1,000,000). Only
 * then do buyers and sellers add up to what actually traded; the average stays
 * a separate line saying whether this candle's volume is high or low.
 */

import type { OHLCVRecord } from "./types"

export const DEFAULT_VOLUME_AVG_LENGTH = 20
const MIN_LENGTH = 1
const MAX_LENGTH = 500

/** Bar colours as thinkorswim paints them: unchanged closes are its cyan. */
export const VOLUME_UP = "#26a69a"
export const VOLUME_DOWN = "#ef5350"
export const VOLUME_FLAT = "#22d3ee"
export const VOLUME_AVG_COLOR = "#e040fb"

export interface VolumeSplit {
  buyerPct: number
  sellerPct: number
  /** Whole contracts. buyers + sellers is always the candle's volume. */
  buyers: number
  sellers: number
}

export function buyerSellerSplit(bar: Pick<OHLCVRecord, "h" | "l" | "c" | "v">): VolumeSplit | null {
  if (bar.v == null || !Number.isFinite(bar.v)) return null
  const range = bar.h - bar.l
  // A candle with no range says nothing about either side.
  const raw = range > 0 ? (bar.c - bar.l) / range : 0.5
  const buyerPct = Math.min(1, Math.max(0, raw))
  // Sellers are the remainder, so rounding cannot lose or invent a contract.
  const buyers = Math.round(bar.v * buyerPct)
  return { buyerPct, sellerPct: 1 - buyerPct, buyers, sellers: bar.v - buyers }
}

/** Simple moving average; null until `length` bars with volume are in the window. */
export function volumeAverage(volumes: ReadonlyArray<number | null>, length: number): (number | null)[] {
  let sum = 0
  let missing = 0
  return volumes.map((v, i) => {
    if (v == null) missing++
    else sum += v
    if (i >= length) {
      const out = volumes[i - length]
      if (out == null) missing--
      else sum -= out
    }
    return i >= length - 1 && missing === 0 ? sum / length : null
  })
}

export function clampVolumeAvgLength(n: number): number {
  if (!Number.isFinite(n)) return DEFAULT_VOLUME_AVG_LENGTH
  return Math.min(MAX_LENGTH, Math.max(MIN_LENGTH, Math.trunc(n)))
}

/** Close against the PREVIOUS close, not the candle's own open -- thinkorswim's rule. */
export function volumeBarColors(closes: ReadonlyArray<number>): string[] {
  return closes.map((c, i) => {
    if (i === 0 || c === closes[i - 1]) return VOLUME_FLAT
    return c > closes[i - 1] ? VOLUME_UP : VOLUME_DOWN
  })
}

/** Top of the volume axis for the bars on screen, with 10% headroom. */
export function volumeAxisMax(
  bars: ReadonlyArray<OHLCVRecord>,
  average: ReadonlyArray<number | null>,
  startMs: number,
  endMs: number,
): number {
  let max = 0
  bars.forEach((b, i) => {
    const ms = Date.parse(b.t)
    if (ms < startMs || ms > endMs) return
    max = Math.max(max, b.v ?? 0, average[i] ?? 0)
  })
  return max > 0 ? max * 1.1 : 1
}
