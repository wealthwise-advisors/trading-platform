/**
 * Which row each swing title goes on above the chart.
 *
 * A title moves up a row only when it would really overlap a neighbour: the
 * two are compared by their estimated text widths in pixels, not by a fixed
 * share of the window. The fixed share (14% of the visible time) lifted titles
 * that had room once they grew longer ("10 Leg Dev", the dominance tag), which
 * left swings floating above the chart for no reason (reported 2026-11-10).
 */

/** Plotly's Arial at 10px: about this many pixels per character, plus padding.
 *  5.6 was too narrow for the capitals in "▼ SELLERS 60%": titles touched (2026-11-13). */
const CHAR_PX = 6.4
const PAD_PX = 10
/** Clear space kept between two titles on one row. */
const GAP_PX = 8

/** Rough rendered width of a title: its longest line, tags stripped. */
export function titleWidthPx(html: string): number {
  const lines = html.split(/<br\s*\/?>/i).map((l) => l.replace(/<[^>]*>/g, ""))
  return Math.max(...lines.map((l) => l.length)) * CHAR_PX + PAD_PX
}

export interface PlacedTitle {
  xPx: number
  widthPx: number
  level: number
}

/**
 * The lowest row (0 first) where a title centred at `xPx` overlaps nothing
 * already placed; with every row taken, the row whose nearest neighbour is
 * furthest away.
 */
// Three rows: two left titles touching when zoomed out (2026-11-14); still capped, so no staircase.
export function titleLevel(placed: ReadonlyArray<PlacedTitle>, xPx: number, widthPx: number, maxLevels = 3): number {
  const colliders = placed.filter((p) => Math.abs(p.xPx - xPx) < (p.widthPx + widthPx) / 2 + GAP_PX)
  const taken = new Set(colliders.map((p) => p.level))
  for (let level = 0; level < maxLevels; level++) if (!taken.has(level)) return level
  let best = 0
  let bestGap = -1
  for (let level = 0; level < maxLevels; level++) {
    const gap = Math.min(...colliders.filter((p) => p.level === level).map((p) => Math.abs(p.xPx - xPx)))
    if (gap > bestGap) { bestGap = gap; best = level }
  }
  return best
}

/**
 * A swing's name in its title: run 1 is "A", 2 "B", 26 "Z", 27 "AA". Inside a
 * swing the 10 Leg points are 1, 2, 3 and the 3 Leg points i, ii, iii, so the
 * three levels never share a style (2026-11-12). Mirrors swing_name() in
 * src/analysis/swing_count.py.
 */
export function swingName(run: number): string {
  let n = run
  let out = ""
  while (n > 0) {
    const r = (n - 1) % 26
    out = String.fromCharCode(65 + r) + out
    n = Math.floor((n - 1) / 26)
  }
  return out
}
