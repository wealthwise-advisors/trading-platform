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
 * Colours for the level groups -- CLEARLY DIFFERENT (2026-10-27).
 *
 * Sir finds similar shades hard to tell apart. The old eight (sky, amber,
 * purple, cyan, orange, pink, pale blue, lilac) plus generated hues past them
 * had several that read alike to him: sky / cyan / pale blue, purple / lilac /
 * pink, amber / orange. The first six are the Okabe-Ito set, chosen to stay
 * apart under the common forms of colour blindness, with its blue lifted so it
 * reads on the dark ground and its green and vermilion left out: green and red
 * mean above/below the average in the column beside this one. Grey and brown
 * follow: nine timeframes on eight levels repeated colours with only six.
 *
 * Colour only -- a symbol per level was tried and removed on request. Past
 * eight levels the colours repeat; neighbouring levels never share one.
 */
export const POC_LEVEL_PALETTE: readonly string[] = [
  "#56b4e9", // sky blue
  "#e69f00", // orange
  "#f2f2f2", // white
  "#f0e442", // yellow
  "#3d8bff", // strong blue
  "#cc79a7", // reddish purple
  "#9ca3af", // grey
  "#b5835a", // brown
]

/** Colour for the Nth level (Nth-lowest on screen). */
export function levelColor(index: number): string {
  return POC_LEVEL_PALETTE[index % POC_LEVEL_PALETTE.length]
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
  first?: Iterable<number | null | undefined>,
): Map<number, string> {
  const out = new Map<number, string>()
  levelOrder(values, first).forEach((w, i) => out.set(w, levelColor(i)))
  return out
}

/**
 * The order levels take colours in: the `first` levels (the Live
 * state table's, a handful) lowest-first, then every other level lowest-first.
 * So the table read most gets the first and most distinct colours -- sky
 * blue, orange, white -- rather than whatever slot the tape's history left.
 */
function levelOrder(
  values: Iterable<number | null | undefined>,
  first?: Iterable<number | null | undefined>,
): number[] {
  const whole = (xs: Iterable<number | null | undefined>) => {
    const set = new Set<number>()
    for (const v of xs) if (v != null && Number.isFinite(v)) set.add(wholePart(v))
    return [...set].sort((a, b) => a - b)
  }
  const head = first ? whole(first) : []
  const seen = new Set(head)
  return [...head, ...whole(values).filter((w) => !seen.has(w))]
}

/**
 * "X vs Avg" for any per-timeframe value -- POC, VA High, VA Low.
 *
 * average = sum of the values of every timeframe that has one / how many have
 * one. A timeframe without a value is left out of BOTH, so it cannot drag the
 * average towards zero. Each value is then measured against that average:
 * diff = value - average, side above / below / equal.
 *
 * VAH vs Avg and VAL vs Avg were added 2026-10-27 "the same way as POC vs Avg";
 * POC vs Avg now goes through this too, so the three cannot drift apart.
 */
export function averageColumn(
  rows: ReadonlyArray<{ tf: string; value: number | null | undefined }>,
): { average: number | null; side: Map<string, AvgSide>; diff: Map<string, number>; counted: number } {
  const valid = rows.filter(
    (r): r is { tf: string; value: number } => r.value != null && Number.isFinite(r.value),
  )
  const side = new Map<string, AvgSide>()
  const diff = new Map<string, number>()
  if (valid.length === 0) return { average: null, side, diff, counted: 0 }
  const average = valid.reduce((s, r) => s + r.value, 0) / valid.length
  for (const r of valid) {
    const v = sideVsAverage(r.value, average)
    side.set(r.tf, v.side)
    diff.set(r.tf, v.diff)
  }
  return { average, side, diff, counted: valid.length }
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
  if (valid.length === 0) {
    return { level, side: new Map(), diff: new Map(), average: null, counted: 0 }
  }

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
  const { average, side, diff } = averageColumn(valid.map((r) => ({ tf: r.tf, value: r.poc })))

  return { level, side, diff, average, counted: valid.length }
}
