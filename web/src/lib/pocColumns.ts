/**
 * The two POC columns on Market Grid's "Live state -- all timeframes" table.
 *
 * Specified by sir on 2026-10-11, for whatever set of timeframes is selected
 * (four, five, eleven -- any number):
 *
 *   POC MATCH   Timeframes whose POC has the same digits BEFORE the decimal
 *               point are on the same level and share one colour; each
 *               different level gets its own. Eleven selected with seven on
 *               7842.xx and four elsewhere reads as one colour on seven rows.
 *
 *   POC VS AVG  The reference is the AVERAGE POC of the selected timeframes.
 *               A POC above it is green, below it is red.
 *
 * "Same level" is the whole number, by the rule this project already uses for
 * the VWAP band columns -- see `wholePart` in ./deviationColors: 7842.75 and
 * 7842.10 are one level, 7841.96 is another. Truncation, not flooring, so a
 * negative value cannot land in the wrong group.
 *
 * The AVERAGE comparison is on the raw value, deliberately. "Above the
 * average" is a question about the number, and the average is almost never a
 * whole number -- rounding both sides first would call 7842.9 "not above"
 * 7842.1, which is not what anyone reading the column would mean.
 *
 * Supersedes the earlier POC-side work (reverted 2026-10-09, f2fce7f), which
 * measured against the current price or a typed level. The reference here is
 * the average, as specified.
 */

import { wholePart } from "./deviationColors"

export interface PocRow {
  tf: string
  poc: number | null | undefined
}

/** One POC level shared by one or more timeframes. */
export interface PocLevel {
  /** The whole-number level, e.g. 7842. */
  level: number
  color: string
  /** How many of the counted timeframes sit on it. */
  count: number
}

export type AvgSide = "above" | "below" | "equal"

export interface PocColumns {
  /** Per timeframe: its level group. Absent when the timeframe has no POC. */
  level: Map<string, PocLevel>
  /** Per timeframe: where its POC sits against the average. */
  side: Map<string, AvgSide>
  /** Per timeframe: its POC minus the average, for the readout. */
  diff: Map<string, number>
  /** The average POC of every timeframe that has one; null with none. */
  average: number | null
  /** How many timeframes had a POC -- the "of N" in "7 of 11". */
  counted: number
}

/**
 * Colours for the level groups. Opens on the sky blue the POC column already
 * used, so a table where every timeframe agrees looks as it always did; the
 * rest are picked to stay distinct from each other on the dark ground.
 * Deliberately NOT green or red: those mean above/below the average in the
 * column beside this one, and a level coloured green would read as "above".
 */
export const POC_LEVEL_PALETTE: readonly string[] = [
  "#38bdf8", // sky -- the original POC colour
  "#e3b341", // amber
  "#bc8cff", // purple
  "#39d0d8", // cyan
  "#ffa657", // orange
  "#f778ba", // pink
  "#a5d6ff", // pale blue
  "#d2a8ff", // lilac
]

/**
 * Colour for the Nth level, from the palette and then generated.
 *
 * NOT deviationColors' colorForSlot: its overflow hues come from a 25-165
 * degree band, which runs straight through green. Eleven timeframes on a
 * trending day can easily sit on eleven different levels, and the ninth would
 * have come out green -- the colour that means "above the average" one column
 * over. Generated hues here are confined to bands that avoid both green
 * (roughly 85-165) and red (roughly 340-20), spread by the golden-ratio
 * conjugate so successive levels stay far apart.
 */
const SAFE_BANDS: ReadonlyArray<readonly [number, number]> = [[22, 82], [168, 336]]
const SAFE_SPAN = SAFE_BANDS.reduce((s, [a, b]) => s + (b - a), 0)

export function levelColor(index: number): string {
  if (index < POC_LEVEL_PALETTE.length) return POC_LEVEL_PALETTE[index]
  const k = index - POC_LEVEL_PALETTE.length
  let t = ((k + 1) * 0.618033988749895 % 1) * SAFE_SPAN
  let hue = SAFE_BANDS[0][0]
  for (const [a, b] of SAFE_BANDS) {
    if (t <= b - a) { hue = a + t; break }
    t -= b - a
  }
  const light = [66, 54, 74, 60][k % 4]
  return `hsl(${hue.toFixed(1)} 70% ${light}%)`
}

/**
 * One colour per whole-number POC level, for EVERY table that shows POC Match.
 *
 * Shared so that a level is the same colour in the Live state table and in
 * the Consolidated tape -- 5823 is not amber up there and blue down here. The
 * VWAP band columns already work this way (one grouping for both tables, see
 * devColors in ReplayPage). Colour is by the Nth-LOWEST level among the values
 * given, so it follows price, not which row happened to arrive first.
 */
export function buildLevelColorMap(
  values: Iterable<number | null | undefined>,
): Map<number, string> {
  const levels = new Set<number>()
  for (const v of values) if (v != null && Number.isFinite(v)) levels.add(wholePart(v))
  const out = new Map<number, string>()
  ;[...levels].sort((a, b) => a - b).forEach((w, i) => out.set(w, levelColor(i)))
  return out
}

/** Where one POC sits against a reference average. Raw value, not whole number. */
export function sideVsAverage(poc: number, average: number): { side: AvgSide; diff: number } {
  const diff = poc - average
  // A tolerance well below a tick, so floating-point noise in the mean can
  // never paint a POC that IS the average green or red.
  return { side: Math.abs(diff) < 1e-9 ? "equal" : diff > 0 ? "above" : "below", diff }
}

/**
 * How many of a timeframe's bars had CLOSED by `moment` -- the bar count its
 * volume profile stood at then.
 *
 * `opensMs` are the bars' open times in ms, oldest first. A bar closes at
 * open + its length, so the count is the number whose close is at or before
 * the moment. Binary search: the tape asks this for up to 400 rows times every
 * shown timeframe, on every tick.
 */
export function barsClosedBy(opensMs: ReadonlyArray<number>, minutes: number, moment: number): number {
  const span = minutes * 60_000
  let lo = 0, hi = opensMs.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (opensMs[mid] + span <= moment) lo = mid + 1
    else hi = mid
  }
  return lo
}

export function buildPocColumns(
  rows: ReadonlyArray<PocRow>,
  /** A colour map shared with another table; built from these rows if absent. */
  colors?: ReadonlyMap<number, string>,
): PocColumns {
  const valid = rows.filter(
    (r): r is { tf: string; poc: number } => r.poc != null && Number.isFinite(r.poc),
  )
  const level = new Map<string, PocLevel>()
  const side = new Map<string, AvgSide>()
  const diff = new Map<string, number>()
  if (valid.length === 0) return { level, side, diff, average: null, counted: 0 }

  // ── POC Match: group by whole number ──
  const counts = new Map<number, number>()
  for (const r of valid) {
    const w = wholePart(r.poc)
    counts.set(w, (counts.get(w) ?? 0) + 1)
  }
  // Colour by the Nth-LOWEST level on screen (see buildLevelColorMap), unless
  // a map shared with another table was passed in.
  const colorOf = colors ?? buildLevelColorMap(valid.map((r) => r.poc))
  for (const r of valid) {
    const w = wholePart(r.poc)
    level.set(r.tf, { level: w, color: colorOf.get(w) ?? levelColor(0), count: counts.get(w)! })
  }

  // ── POC vs Avg: the mean of the selected timeframes' POCs ──
  const average = valid.reduce((s, r) => s + r.poc, 0) / valid.length
  for (const r of valid) {
    const v = sideVsAverage(r.poc, average)
    diff.set(r.tf, v.diff)
    side.set(r.tf, v.side)
  }

  return { level, side, diff, average, counted: valid.length }
}
