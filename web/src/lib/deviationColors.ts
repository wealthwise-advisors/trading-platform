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

export interface DeviationColorGroups {
  /** whole number -> colour, for values in Upper columns */
  upper: Map<number, string>
  /** whole number -> colour, for values in Lower columns */
  lower: Map<number, string>
  /** the whole numbers, ascending — index is the colour slot */
  upperOrder: number[]
  lowerOrder: number[]
}

export interface BuildOptions {
  upperPalette?: readonly string[]
  lowerPalette?: readonly string[]
}

/**
 * Group the displayed values by whole number and assign each group a colour.
 *
 * Both sides are grouped independently and given colours from their own
 * palette, so an identical whole number appearing on both sides gets two
 * different colours.
 *
 * Order is ascending numeric, which makes the mapping deterministic: the same
 * data always yields the same colours, and the lowest group is always slot 1.
 * Nothing is keyed to a particular price, so the mapping simply re-derives
 * when the date, symbol, timeframes or deviation levels change.
 *
 * null / undefined / NaN are skipped and get no group; the caller leaves those
 * cells at their default styling.
 */
export function buildDeviationColorGroups(
  upperValues: ReadonlyArray<number | null | undefined>,
  lowerValues: ReadonlyArray<number | null | undefined>,
  opts: BuildOptions = {},
): DeviationColorGroups {
  const side = (
    values: ReadonlyArray<number | null | undefined>,
    which: DeviationSide,
    palette?: readonly string[],
  ) => {
    const keys = new Set<number>()
    for (const v of values) {
      if (v == null || !Number.isFinite(v)) continue
      keys.add(wholePart(v))
    }
    const order = [...keys].sort((a, b) => a - b)
    const map = new Map<number, string>()
    order.forEach((k, i) => map.set(k, colorForSlot(which, i, palette)))
    return { order, map }
  }

  const u = side(upperValues, "upper", opts.upperPalette)
  const l = side(lowerValues, "lower", opts.lowerPalette)
  return { upper: u.map, lower: l.map, upperOrder: u.order, lowerOrder: l.order }
}

/**
 * Colour for one cell, or null when the value has no group (missing/NaN) so
 * the caller can fall back to the neutral default.
 */
export function colorFor(
  groups: DeviationColorGroups,
  side: DeviationSide,
  value: number | null | undefined,
): string | null {
  if (value == null || !Number.isFinite(value)) return null
  return (side === "upper" ? groups.upper : groups.lower).get(wholePart(value)) ?? null
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
