/**
 * Which side of a reference price each timeframe's POC sits on, and whether
 * they agree.
 *
 * THE QUESTION THIS ANSWERS. The all-timeframes table already shows a POC per
 * timeframe, but as nine unrelated numbers: telling whether they cluster above
 * price or below it meant reading every row and holding the comparison in your
 * head. The useful fact is one-sidedness -- "every timeframe's heaviest traded
 * price is ABOVE where we are now" is a different market from the same nine
 * numbers scattered either side, and it is the fact a bias is built on.
 *
 * SIDES ARE DECIDED ON THE WHOLE NUMBER, not the raw float, and that is the
 * load-bearing decision here. This project already treats the digits before
 * the decimal as the level -- see `wholePart` in ./deviationColors, where
 * 7842.75 and 7842.10 are the same level and 7841.96 is a different one. If
 * the side were computed on the raw value, a POC of 7842.75 against a
 * reference of 7842.10 would read ABOVE while the colour grouping in the very
 * next column called them equal. The table would contradict itself one cell
 * apart. So a POC on the reference's own level is AT, not above and not below.
 *
 * Reference is supplied by the caller rather than chosen here: the panel
 * defaults it to the clock-base timeframe's last close ("where we are now")
 * and lets it be pinned to a typed level instead, and neither of those is a
 * decision this module should be making.
 */

import { colorForSlot, wholePart, type DeviationSide } from "./deviationColors"

export type PocSide = "above" | "below" | "at"

/**
 * One row's input. `tf` is only carried through so the caller can map results
 * back without a second pass; nothing here interprets it.
 */
export interface PocRow {
  tf: string
  poc: number | null | undefined
}

export interface PocConsensus {
  /** The level every side was decided against, or null if there wasn't one. */
  reference: number | null
  /** Per-timeframe side. Timeframes with no POC are absent, not defaulted. */
  sides: Map<string, PocSide>
  above: string[]
  below: string[]
  at: string[]
  /** Timeframes that reported a POC at all -- the denominator for the counts. */
  counted: number
  /**
   * Every POC that exists sits on ONE side, and there are at least two of
   * them to agree. A single timeframe is not a consensus, and `at` rows break
   * it: sitting on the reference is not agreeing about a direction.
   */
  oneSided: boolean
  /** The side they all agree on when `oneSided`, else the strict majority. */
  dominantSide: PocSide | null
  /** whole-number POC level -> colour, so shared levels share a colour. */
  levelColors: Map<number, string>
}

/**
 * Side colours.
 *
 * Deliberately NOT the green/red this table already spends on Change, P&L and
 * Position. A POC above price is not good news and below it is not bad news --
 * heavy volume overhead is resistance, which most readers would call bearish,
 * so painting it green would assert the opposite of what it means. Amber and
 * blue carry the split without claiming a direction is profitable.
 */
export const POC_SIDE_COLOR: Record<PocSide, string> = {
  above: "#e3b341", // amber
  below: "#58a6ff", // blue
  at: "#8b949e", // grey — on the level, no side to take
}

export const POC_SIDE_GLYPH: Record<PocSide, string> = {
  above: "↑",
  below: "↓",
  at: "•",
}

/**
 * Palette for the POC column's level groups.
 *
 * First entry is the sky blue the column was already painted before grouping
 * existed, so a table whose timeframes all land on one level looks exactly as
 * it did. The upper/lower palettes in ./deviationColors open with their own
 * pre-grouping colours for the same reason.
 *
 * POC is not a deviation band, so it is not bound by the upper/lower hue
 * separation -- that guarantee exists so a tinted band cell tells you which
 * side of the VWAP it is on, and POC has no such pairing to confuse.
 */
export const DEFAULT_POC_PALETTE: readonly string[] = [
  "#38bdf8", // sky — the original POC colour
  "#7ee787", // green
  "#e3b341", // amber
  "#bc8cff", // purple
  "#39d0d8", // cyan
  "#f0883e", // orange
  "#f06292", // pink
  "#a5d6a7", // sage
]

/** Which side of `reference` a price sits on, by level rather than by float. */
export function sideOf(poc: number, reference: number): PocSide {
  const p = wholePart(poc)
  const r = wholePart(reference)
  if (p === r) return "at"
  return p > r ? "above" : "below"
}

/**
 * Group POCs by level and work out whether the timeframes are one-sided.
 *
 * Levels are coloured by their position in the ascending order of levels
 * PRESENT, the same rule `buildDeviationColorGroups` uses per column, so the
 * colour means "the Nth-lowest POC level on screen" and stays inside the
 * curated palette instead of being a hash of the price.
 */
export function buildPocConsensus(
  rows: ReadonlyArray<PocRow>,
  reference: number | null | undefined,
  palette: readonly string[] = DEFAULT_POC_PALETTE,
): PocConsensus {
  const sides = new Map<string, PocSide>()
  const above: string[] = []
  const below: string[] = []
  const at: string[] = []
  const levels = new Set<number>()

  const ref = reference != null && Number.isFinite(reference) ? reference : null

  for (const { tf, poc } of rows) {
    if (poc == null || !Number.isFinite(poc)) continue
    levels.add(wholePart(poc))
    if (ref == null) continue
    const side = sideOf(poc, ref)
    sides.set(tf, side)
    ;(side === "above" ? above : side === "below" ? below : at).push(tf)
  }

  // Colour by the Nth-lowest level on screen, ascending and deterministic.
  const levelColors = new Map<number, string>()
  ;[...levels]
    .sort((a, b) => a - b)
    .forEach((lvl, i) => {
      // Reuse the slot allocator so overflow past the palette is the same
      // low-discrepancy spread the band columns get. "upper" only selects the
      // generator's hue band; the palette passed in governs everything the
      // table actually shows.
      levelColors.set(lvl, colorForSlot("upper" as DeviationSide, i, palette))
    })

  const counted = above.length + below.length + at.length
  const oneSided =
    counted >= 2 && at.length === 0 && (above.length === counted || below.length === counted)

  let dominantSide: PocSide | null = null
  if (counted > 0) {
    if (above.length > below.length && above.length > at.length) dominantSide = "above"
    else if (below.length > above.length && below.length > at.length) dominantSide = "below"
    else if (at.length > above.length && at.length > below.length) dominantSide = "at"
    // A tie leaves it null: there is no dominant side, and naming one would be
    // the table asserting a bias the numbers do not support.
  }

  return { reference: ref, sides, above, below, at, counted, oneSided, dominantSide, levelColors }
}

/** Colour for one POC cell, by the level it lands on. */
export function pocLevelColor(
  consensus: PocConsensus,
  poc: number | null | undefined,
): string | null {
  if (poc == null || !Number.isFinite(poc)) return null
  return consensus.levelColors.get(wholePart(poc)) ?? null
}

/**
 * The header summary, e.g. "3↑ / 6↓" or "ONE-SIDED ↑ 9/9".
 *
 * Returns null when there is nothing to say -- no reference, or fewer than two
 * POCs -- so the caller renders nothing rather than a badge reading "0".
 */
export function pocConsensusLabel(c: PocConsensus): string | null {
  if (c.reference == null || c.counted < 2) return null
  if (c.oneSided) {
    const side = c.above.length === c.counted ? "above" : "below"
    return `ONE-SIDED ${POC_SIDE_GLYPH[side]} ${c.counted}/${c.counted}`
  }
  // Every POC on the reference's own level. Spelled out rather than left as
  // the bare "4•" the glyph format produces, which reads as a typo.
  if (c.at.length === c.counted) return `${c.counted} ON LEVEL`
  const parts: string[] = []
  if (c.above.length) parts.push(`${c.above.length}${POC_SIDE_GLYPH.above}`)
  if (c.below.length) parts.push(`${c.below.length}${POC_SIDE_GLYPH.below}`)
  if (c.at.length) parts.push(`${c.at.length}${POC_SIDE_GLYPH.at}`)
  return parts.join(" / ")
}
