/** Sir's structure zones (2026-11-20) in the Market Grid: the vs-average words and the Price Zone column. */

/** The word a "vs Average" cell carries: above the average High, below it Low, on it Neutral. */
export function avgWord(side: "above" | "below" | "equal"): "High" | "Low" | "Neutral" {
  return side === "above" ? "High" : side === "below" ? "Low" : "Neutral"
}

export type PriceZone = { word: "Buy / Reversal" | "Breakout" | "No trade" | "Short / Reversal"; cls: string }

/**
 * Where a timeframe's price sits among its own levels, in sir's words: at or above
 * VA High = resistance, buy / reversal; at or below VA Low = support, short /
 * reversal; between VWAP and VA High = breakout; otherwise the POC core, no trade.
 * Null when a level is missing.
 */
export function priceZone(close: number | null | undefined,
                          lv: { vah?: number | null; val?: number | null; vwap?: number | null }): PriceZone | null {
  const { vah, val, vwap } = lv
  if (close == null || vah == null || val == null || vwap == null) return null
  if (close >= vah) return { word: "Buy / Reversal", cls: "pz-res" }
  if (close <= val) return { word: "Short / Reversal", cls: "pz-sup" }
  if (close >= vwap) return { word: "Breakout", cls: "pz-brk" }
  return { word: "No trade", cls: "pz-core" }
}
