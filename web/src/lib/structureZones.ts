/**
 * Sir's structure zones (2026-11-20), from the levels of every timeframe on the
 * Market Grid at once:
 *
 *   Resistance level      VA High high and average   above: buy / reversal
 *   Breakout zone         VWAP high to VA High low    the band price breaks out through
 *   Equilibrium core POC  POC high, average, low      neutral: no trade zone
 *   Support floor         VA Low high, average, low   below: short / reversal
 *
 * "High" and "low" are the highest and lowest value of that column across the
 * timeframes; "average" is their mean, the same one the columns' averages use.
 */
export interface ZoneRow {
  vwap?: number | null
  poc?: number | null
  vah?: number | null
  val?: number | null
}

export interface Spread { high: number; avg: number; low: number }

export interface StructureZones {
  resistance: Spread | null
  breakout: { vwapHigh: number; vahLow: number } | null
  core: Spread | null
  support: Spread | null
}

function spread(values: ReadonlyArray<number | null | undefined>): Spread | null {
  const v = values.filter((x): x is number => x != null && Number.isFinite(x))
  if (!v.length) return null
  return { high: Math.max(...v), avg: v.reduce((s, x) => s + x, 0) / v.length, low: Math.min(...v) }
}

export function structureZones(rows: ReadonlyArray<ZoneRow>): StructureZones {
  const vwap = spread(rows.map((r) => r.vwap))
  const vah = spread(rows.map((r) => r.vah))
  return {
    resistance: vah,
    breakout: vwap && vah ? { vwapHigh: vwap.high, vahLow: vah.low } : null,
    core: spread(rows.map((r) => r.poc)),
    support: spread(rows.map((r) => r.val)),
  }
}

/** The word a "vs Average" cell carries: above the average High, below it Low, on it Neutral. */
export function avgWord(side: "above" | "below" | "equal"): "High" | "Low" | "Neutral" {
  return side === "above" ? "High" : side === "below" ? "Low" : "Neutral"
}
