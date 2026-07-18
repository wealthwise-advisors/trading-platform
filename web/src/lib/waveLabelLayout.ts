// Pure, chart-agnostic label decluttering for the Elliott Wave chart.
// Deliberately has ZERO knowledge of the wave-counting algorithm (wave_numbering.py)
// -- it only ever reorders/hides/reveals WHICH already-computed WaveLabels get a
// text annotation and which get drawn on the line/marker trace, based on
// priority + on-screen crowding. The underlying wave COUNT never changes --
// only how much of it is currently drawn/annotated.
//
// Revised 2026-07-17 after a real-data QA pass surfaced two gaps in the first
// version: (1) the connecting line/markers were drawn at full detail
// regardless of zoom, so a busy chart still LOOKED busy even with text
// decluttered -- fixed by making tierFilter() (below) gate the line/marker
// points the same way allowedTiers() already gated text; (2) collision
// detection only checked TIME spacing, so two labels far apart in time but
// close in PRICE (e.g. during a choppy consolidation) could both survive and
// visually stack -- fixed by requiring BOTH time and price proximity to
// count as a real collision (a genuine 2D check, not 1D).

import type { WaveLabel } from "@/lib/types"

// Plain const object instead of `enum` -- this project's tsconfig has
// erasableSyntaxOnly set, which rejects real TS enums (they emit runtime
// code, not purely-erasable types).
export const WaveTier = {
  Core: 0,       // 1, 3, 5, a, c -- the impulse/corrective backbone, always eligible
  Secondary: 1,  // 2, 4, b -- the retracements between backbone points
  Tertiary: 2,   // continuation 6..11 -- only shown once meaningfully zoomed in
} as const
export type WaveTier = (typeof WaveTier)[keyof typeof WaveTier]

const CORE_WAVES = new Set(["1", "3", "5", "a", "c"])
const SECONDARY_WAVES = new Set(["2", "4", "b"])

export function tierOf(wave: string): WaveTier {
  if (CORE_WAVES.has(wave)) return WaveTier.Core
  if (SECONDARY_WAVES.has(wave)) return WaveTier.Secondary
  return WaveTier.Tertiary
}

// Collision-resolution priority -- higher wins when two labels crowd the same
// spot. Tier dominates; within a tier, a higher-confidence fib+pattern match
// (sub === 1) outranks pattern-only (sub === 2), and continuation/ABC waves
// (no sub, sub === null) sit in between since they're not fib-scored at all.
export function priorityOf(w: WaveLabel): number {
  const tier = tierOf(w.wave)
  const tierScore = (WaveTier.Tertiary - tier) * 10
  const subScore = w.sub === 1 ? 2 : w.sub === 2 ? 0.5 : 1
  return tierScore + subScore
}

export interface LabelPoint {
  w: WaveLabel
  t: number   // ms epoch, parsed once up front so layout math never re-parses dates
  tier: WaveTier
  priority: number
  color: string   // per-run color, attached by the caller so declutter stays chart-agnostic
}

export function toLabelPoints(sequence: WaveLabel[], colorOf: (w: WaveLabel) => string): LabelPoint[] {
  return sequence.map((w) => ({
    w,
    t: new Date(w.t).getTime(),
    tier: tierOf(w.wave),
    priority: priorityOf(w),
    color: colorOf(w),
  }))
}

// Zoom thresholds, expressed as "visible span / full chart span". Zoomed out
// (>= 50% of the chart visible) shows only the impulse/corrective backbone;
// mid-zoom reveals the retracement waves too; only once meaningfully zoomed
// in (< 15% of the chart visible) do continuation waves 6..11 appear --
// those are the ones that flood a wide view with numbers on a busy chart.
const ZOOM_CORE_ONLY = 0.5
const ZOOM_CORE_PLUS_SECONDARY = 0.15

export function allowedTiers(zoomFraction: number): Set<WaveTier> {
  if (zoomFraction >= ZOOM_CORE_ONLY) return new Set([WaveTier.Core])
  if (zoomFraction >= ZOOM_CORE_PLUS_SECONDARY) return new Set([WaveTier.Core, WaveTier.Secondary])
  return new Set([WaveTier.Core, WaveTier.Secondary, WaveTier.Tertiary])
}

export function zoomFractionOf(visibleRange: [number, number], fullRange: [number, number]): number {
  const visibleSpan = Math.max(visibleRange[1] - visibleRange[0], 1)
  const fullSpan = Math.max(fullRange[1] - fullRange[0], 1)
  return Math.min(visibleSpan / fullSpan, 1)
}

// Filters a single run's points down to whatever tier the current zoom
// allows -- used for the LINE/MARKER trace itself, not just text, so a
// zoomed-out chart draws a clean simplified backbone (e.g. just 1-3-5-a-c)
// instead of every micro-pivot with the labels merely stripped off. Always
// keeps the run's first and last point so the line never disappears
// entirely for a short/partial run at coarse zoom.
export function tierFilterRun<T extends { wave: string }>(run: T[], zoomFraction: number): T[] {
  const tiers = allowedTiers(zoomFraction)
  const filtered = run.filter((w) => tiers.has(tierOf(w.wave)))
  if (filtered.length > 0) return filtered
  // Degenerate case: a run whose points are ALL below the allowed tier
  // (shouldn't normally happen since every run starts at "1", which is
  // Core) -- fall back to endpoints so it doesn't vanish outright.
  return run.length ? [run[0], run[run.length - 1]] : []
}

// Minimum gap between two SAME-LANE (both "high" or both "low") labels for
// them to count as visually colliding -- expressed as fractions of the
// currently visible range on EACH axis independently, so both automatically
// loosen as you zoom in. A collision requires BOTH axes to be close: two
// labels far apart in time but at nearly the same price (a choppy
// consolidation), or close in time but at very different prices, don't
// actually overlap on screen -- only genuine 2D proximity does.
const MIN_SPACING_T_FRACTION = 0.022
const MIN_SPACING_P_FRACTION = 0.045
// Small padding so labels just past the viewport edge don't pop in/out on
// every single pixel of pan.
const VIEWPORT_PAD_FRACTION = 0.03

export interface DeclutterResult {
  shown: LabelPoint[]
  hiddenCount: number
}

export function declutter(
  points: LabelPoint[],
  visibleRange: [number, number],
  fullRange: [number, number],
  visiblePriceRange: [number, number],
): DeclutterResult {
  const visibleSpan = Math.max(visibleRange[1] - visibleRange[0], 1)
  const priceSpan = Math.max(visiblePriceRange[1] - visiblePriceRange[0], 1e-9)
  const zoomFraction = zoomFractionOf(visibleRange, fullRange)
  const tiers = allowedTiers(zoomFraction)

  const pad = visibleSpan * VIEWPORT_PAD_FRACTION
  const inView = points.filter(
    (p) => p.t >= visibleRange[0] - pad && p.t <= visibleRange[1] + pad && tiers.has(p.tier)
  )

  // Two independent lanes (high/low) -- a high-label sits above the candle
  // and a low-label sits below it, so a high/low pair never really competes
  // for the same spot regardless of proximity. Only same-lane crowding is
  // real crowding.
  const lanes: Record<"high" | "low", LabelPoint[]> = { high: [], low: [] }
  const byPriority = [...inView].sort((a, b) => b.priority - a.priority || a.t - b.t)

  const shown: LabelPoint[] = []
  for (const cand of byPriority) {
    const lane = lanes[cand.w.kind]
    const collides = lane.some((p) => {
      const dt = Math.abs(p.t - cand.t) / visibleSpan
      const dp = Math.abs(p.w.price - cand.w.price) / priceSpan
      return dt < MIN_SPACING_T_FRACTION && dp < MIN_SPACING_P_FRACTION
    })
    if (!collides) {
      lane.push(cand)
      shown.push(cand)
    }
  }
  shown.sort((a, b) => a.t - b.t)
  return { shown, hiddenCount: inView.length - shown.length }
}
