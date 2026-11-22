/** The scanner's conditions (upgrade plan, Feature 7): shapes and how they read. */
export type ScanCondition =
  | { kind: "indicator"; name: "rsi2" | "rsi13" | "stochrsi" | "mfi"; op: "above" | "below" | "crosses_above" | "crosses_below"; value: number }
  | { kind: "change_pct"; bars: number; op: "above" | "below"; value: number }
  | { kind: "volume_vs_avg"; op: "above" | "below"; value: number }
  | { kind: "breakout"; bars: number; direction: "high" | "low" }
  | { kind: "vwap"; position: "above_upper" | "above_vwap" | "below_vwap" | "below_lower" }

export interface SavedScan { name: string; timeframe: string; combine: "all" | "any"; symbols: string[]; conditions: ScanCondition[] }

export interface ScanRow {
  symbol: string; matched: boolean; error: string | null; last: number | null; bar_time: string | null
  values: { label: string; value: number | null; met: boolean }[]
}

const IND = { rsi2: "RSI(2)", rsi13: "RSI(13)", stochrsi: "StochRSI %K", mfi: "MFI" }
const OP = { above: "above", below: "below", crosses_above: "crosses above", crosses_below: "crosses below" }
const POS = { above_upper: "above the upper VWAP band", above_vwap: "above VWAP", below_vwap: "below VWAP", below_lower: "below the lower VWAP band" }

/** One condition as a sentence, for the list and for saved scans. */
export function describe(c: ScanCondition): string {
  switch (c.kind) {
    case "indicator": return `${IND[c.name]} ${OP[c.op]} ${c.value}`
    case "change_pct": return `Price change over ${c.bars} bars ${c.op} ${c.value}%`
    case "volume_vs_avg": return `Volume ${c.op} ${c.value}x its 20-bar average`
    case "breakout": return `Close breaks the ${c.bars}-bar ${c.direction}`
    case "vwap": return `Close ${POS[c.position]}`
  }
}

const KEY = "saved-scans"
export function loadScans(): SavedScan[] {
  try { const v = JSON.parse(localStorage.getItem(KEY) ?? "[]"); return Array.isArray(v) ? v : [] } catch { return [] }
}
/** Saved in browser storage, which the settings sync carries to the server (Phase 1). */
export function saveScans(list: SavedScan[]) {
  try { localStorage.setItem(KEY, JSON.stringify(list)) } catch { /* private mode */ }
}
