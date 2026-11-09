/**
 * Which VWAP deviation bands the Chart draws and its hover box lists.
 *
 * +/-1 and +/-2 are always selected to begin with, here as on Market Grid
 * (requested 2026-11-10). Any other level is the viewer's choice, and stays
 * chosen across a refresh.
 */

export const ALL_VWAP_LEVELS = [0.5, 1, 1.5, 2, 2.5, 3, 4, 5] as const
export const DEFAULT_VWAP_LEVELS: readonly number[] = [1, 2]
export const VWAP_LEVELS_STORE_KEY = "autotrader.vwapLevels"

export interface VwapLevelColors {
  head: string
  upper: string
  lower: string
}

/** +/-0.5, 1 and 1.5 are read off sir's thinkorswim. */
const LEVEL_COLORS: Record<number, VwapLevelColors> = {
  0.5: { head: "#8a8af0", upper: "#d8c9a0", lower: "#e0a800" },
  1: { head: "#e040fb", upper: "#22d3ee", lower: "#22d3ee" },
  1.5: { head: "#e040fb", upper: "#d8c9a0", lower: "#d8c9a0" },
  2: { head: "#ff9f43", upper: "#ffd23f", lower: "#ff6b9a" },
}
const OTHER_LEVEL: VwapLevelColors = { head: "#94a3b8", upper: "#cbd5e1", lower: "#94a3b8" }

export function vwapLevelColors(level: number): VwapLevelColors {
  return LEVEL_COLORS[level] ?? OTHER_LEVEL
}

/** Selects or clears one level; the result is always in ascending order. */
export function toggleVwapLevel(levels: readonly number[], level: number): number[] {
  return levels.includes(level)
    ? levels.filter((l) => l !== level)
    : [...levels, level].sort((a, b) => a - b)
}

/** Never throws: storage can be disabled, full, or hold anything at all. */
export function loadVwapLevels(): number[] {
  try {
    const raw = localStorage.getItem(VWAP_LEVELS_STORE_KEY)
    if (!raw) return [...DEFAULT_VWAP_LEVELS]
    const saved: unknown = JSON.parse(raw)
    if (!Array.isArray(saved)) return [...DEFAULT_VWAP_LEVELS]
    return ALL_VWAP_LEVELS.filter((l) => saved.includes(l))
  } catch {
    return [...DEFAULT_VWAP_LEVELS]
  }
}

export function saveVwapLevels(levels: readonly number[]): void {
  try {
    localStorage.setItem(VWAP_LEVELS_STORE_KEY, JSON.stringify(levels))
  } catch {
    // Remembering the choice is a convenience; the chart works without it.
  }
}
