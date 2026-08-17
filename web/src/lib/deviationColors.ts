/**
 * Colour the VWAP deviation columns by the whole number they land on.
 *
 * On a multi-timeframe tape the useful question is "do these timeframes agree
 * on a level?", and that is answered by the digits before the decimal:
 * 7842.52 and 7842.14 are the same level, 7841.96 is a different one despite
 * being 0.18 away. The whole number is also the unit already used when
 * checking bar construction against the reference platform.
 *
 * Upper and lower are coloured from SEPARATE palettes and never share a
 * colour, so a tinted cell always tells you which side of the VWAP it is on
 * before you read the column header. The two default palettes are drawn from
 * disjoint hue ranges, which makes that guarantee structural rather than a
 * property of two hand-written lists that a later edit could break.
 */

/** Upper hues live here; lower hues never do. */
const UPPER_HUE_RANGE: readonly [number, number] = [25, 165]
/** Lower hues live here; upper hues never do. */
const LOWER_HUE_RANGE: readonly [number, number] = [195, 355]

/**
 * Warm side: amber through green. First entry is the amber the column used
 * before grouping existed, so a single-group tape looks unchanged.
 */
export const DEFAULT_UPPER_PALETTE: readonly string[] = [
  "#e3b341", // amber   — the original Upper colour
  "#7ee787", // green
  "#ffa657", // orange
  "#d2f57a", // lime
  "#c9a227", // dark gold
  "#4ac26b", // emerald
  "#f0883e", // burnt orange
  "#a5d6a7", // sage
]

/**
 * Cool side: cyan through magenta. First entry is the pink the column used
 * before grouping existed, for the same reason.
 */
export const DEFAULT_LOWER_PALETTE: readonly string[] = [
  "#f06292", // pink    — the original Lower colour
  "#58a6ff", // blue
  "#bc8cff", // purple
  "#39d0d8", // cyan
  "#ff7b9c", // rose
  "#79c0ff", // sky
  "#d2a8ff", // lilac
  "#56d4dd", // teal
]

export type DeviationSide = "upper" | "lower"

/**
 * The digits before the decimal point.
 *
 * Truncation toward zero, not flooring. For the prices this is used on the two
 * agree, but they diverge for negatives: Math.floor(-1.2) is -2, which would
 * put -1.2 and -1.8 in DIFFERENT groups while claiming "the part before the
 * decimal", and would group -1.0 with -1.8. Math.trunc gives -1 for both, which
 * is what "before the decimal" means. Spreads can legitimately go negative, so
 * this is not hypothetical.
 */
export function wholePart(value: number): number {
  return Math.trunc(value)
}

/** Deterministic overflow colour for group `index` beyond the palette. */
function generated(side: DeviationSide, index: number): string {
  const [lo, hi] = side === "upper" ? UPPER_HUE_RANGE : LOWER_HUE_RANGE
  const span = hi - lo
  // Golden-angle stepping wrapped into the side's own hue band: successive
  // groups land far apart instead of drifting, and can never cross into the
  // other side's band.
  const hue = lo + ((index * 137.508) % span)
  // Alternate lightness so a long run stays separable once hues start to
  // revisit similar angles.
  const light = index % 2 === 0 ? 66 : 52
  return `hsl(${hue.toFixed(1)} 70% ${light}%)`
}

/** Colour for the Nth group on a side, from the palette then generated. */
export function colorForSlot(
  side: DeviationSide,
  index: number,
  palette?: readonly string[],
): string {
  const base = palette ?? (side === "upper" ? DEFAULT_UPPER_PALETTE : DEFAULT_LOWER_PALETTE)
  return index < base.length ? base[index] : generated(side, index)
}

export interface DeviationColumn {
  side: DeviationSide
  values: ReadonlyArray<number | null | undefined>
}

export interface DeviationColorGroups {
  /** whole number -> colour, one map per column, positionally matched */
  byColumn: Array<Map<number, string>>
  /** groups in slot order, for the settings preview */
  upperGroups: number[]
  lowerGroups: number[]
}

export interface BuildOptions {
  upperPalette?: readonly string[]
  lowerPalette?: readonly string[]
}

/**
 * Group each COLUMN independently and assign every group a colour.
 *
 * Per column, not per side. Upper +1s and Upper +2s are different bands: if
 * one timeframe's +1s and another's +2s happen to land on the same whole
 * number that is a coincidence, not two timeframes agreeing on a level.
 * Pooling them would paint that coincidence as agreement, which is the
 * opposite of what the colour is meant to say.
 *
 * Slots are still allocated from a single counter per SIDE, so two distinct
 * groups anywhere in the Upper columns never share a colour -- "different
 * group, different colour" holds across the whole table, not just within one
 * column. Upper and Lower keep their own counters and their own palettes.
 *
 * Order within a column is ascending numeric, and columns are visited left to
 * right, so the mapping is fully deterministic.
 */
export function buildDeviationColorGroups(
  columns: ReadonlyArray<DeviationColumn>,
  opts: BuildOptions = {},
): DeviationColorGroups {
  const next = { upper: 0, lower: 0 }
  const byColumn: Array<Map<number, string>> = []
  const upperGroups: number[] = []
  const lowerGroups: number[] = []

  for (const col of columns) {
    const keys = new Set<number>()
    for (const v of col.values) {
      if (v == null || !Number.isFinite(v)) continue
      keys.add(wholePart(v))
    }
    const map = new Map<number, string>()
    for (const whole of [...keys].sort((a, b) => a - b)) {
      const palette = col.side === "upper" ? opts.upperPalette : opts.lowerPalette
      map.set(whole, colorForSlot(col.side, next[col.side], palette))
      ;(col.side === "upper" ? upperGroups : lowerGroups).push(whole)
      next[col.side] += 1
    }
    byColumn.push(map)
  }
  return { byColumn, upperGroups, lowerGroups }
}

export function colorFor(
  groups: DeviationColorGroups,
  column: number,
  value: number | null | undefined,
): string | null {
  if (value == null || !Number.isFinite(value)) return null
  return groups.byColumn[column]?.get(wholePart(value)) ?? null
}

/**
 * Colours configured for both sides that are the same. Surfaced in the
 * settings UI rather than silently corrected — the user's choice stands, they
 * are just told the two sides are no longer distinguishable.
 */
export function paletteCollisions(
  upperPalette: readonly string[],
  lowerPalette: readonly string[],
): string[] {
  const norm = (c: string) => c.trim().toLowerCase()
  const lower = new Set(lowerPalette.map(norm))
  const seen = new Set<string>()
  const out: string[] = []
  for (const c of upperPalette) {
    const n = norm(c)
    if (lower.has(n) && !seen.has(n)) { seen.add(n); out.push(c) }
  }
  return out
}
