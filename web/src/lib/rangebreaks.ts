// Periods a time axis should skip so bars read as one continuous series.
//
// Session filtering keeps only in-session bars, but a date axis still reserves
// space for the hours it removed — so an 09:30–16:00 session leaves an ~18h
// void every night and ~60h every weekend, and the chart renders as islands of
// candles separated by blank stretches.
//
// Breaks are derived from the timestamps themselves rather than from hardcoded
// market hours: whatever produced the gap — session filter, weekend, holiday,
// venue maintenance, or a hole in the data — is skipped, without anything
// needing to know which instrument trades when.
//
// Shared by CandlestickChart and ElliottWaveChart, and mirrored in Python by
// src/analysis/indicators.compute_rangebreaks() for the report exporters.

/** 40 minutes on a 5-minute chart. Measured rather than guessed: dense
 *  in-session data (ES, one week) gives 2 breaks at any factor from 1.5 to 20,
 *  while a sparse series (BTC, two weeks) gives 144/40/18/11 at 1.5/4/8/20.
 *  A low factor on sparse data compresses ordinary holes and misrepresents
 *  elapsed time; 8 still catches session and weekend boundaries, which run to
 *  hundreds of times the median spacing. */
import { formatterFor } from "@/lib/isoTime"

const GAP_FACTOR = 8
const MAX_BREAKS = 400   // guard against pathological data

export interface Rangebreak {
  bounds: [string, string]
}

export function computeRangebreaks(times: string[]): Rangebreak[] {
  if (times.length < 3) return []
  const ms = times.map((t) => Date.parse(t))
  const deltas: number[] = []
  for (let i = 1; i < ms.length; i++) deltas.push(ms[i] - ms[i - 1])
  // Modal spacing via the median — robust to the gaps themselves, which would
  // drag a mean upward.
  const sorted = [...deltas].sort((a, b) => a - b)
  const step = sorted[Math.floor(sorted.length / 2)]
  if (!step || step <= 0) return []

  // Same convention hazard as the candle timestamps: `times` are naive
  // wall-clock strings parsed as local, so serializing the bounds as UTC would
  // shift every break by the browser's UTC offset and cut the axis in the
  // wrong places. See lib/isoTime.ts.
  const fmt = formatterFor(times[0])
  const iso = (n: number) => fmt(n).slice(0, 19).replace("T", " ")
  const out: Rangebreak[] = []
  for (let i = 1; i < ms.length && out.length < MAX_BREAKS; i++) {
    if (ms[i] - ms[i - 1] > step * GAP_FACTOR) {
      // Start one step after the last bar so it keeps its full width, and end
      // exactly on the next one.
      out.push({ bounds: [iso(ms[i - 1] + step), iso(ms[i])] })
    }
  }
  return out
}
