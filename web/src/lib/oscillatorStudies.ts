/**
 * The oscillator panels under the price chart -- RSI(2), StochRSI, RSI(13) and
 * MFI -- as studies a user switches on and off, the way VWAP and Volume Profile
 * already work.
 *
 * Every number below is what the chart draws: the calculations in
 * src/analysis/indicators.py and the level lines. RSI(2) at 94/2 and RSI(13) at
 * 70/30 are confirmed final and deliberately differ from the reference
 * platform's 5 and 55/45. StochRSI (RSI 14, K 3, D 3, Wilder's, 80/20) replaced
 * the price Stochastic on 2026-09-15. MFI is listed but not yet built.
 */

export type OscKey = "rsi2" | "stochrsi" | "rsi13" | "mfi"
/** The oscillators that can occupy a chart row today. */
export type OscRowKey = Exclude<OscKey, "mfi">

/** Strip order, matching the reference stack top to bottom. */
export const OSC_ORDER: OscKey[] = ["rsi2", "stochrsi", "rsi13", "mfi"]
const ROW_ORDER: OscRowKey[] = ["rsi2", "stochrsi", "rsi13"]

export interface StudyInfo {
  label: string
  available: boolean
  /** Inputs as drawn, label -> value. */
  inputs: [string, string][]
  levels: { overbought: number; oversold: number } | null
  /** Why an unavailable study cannot be switched on. */
  pending?: string
}

export const OSC_STUDIES: Record<OscKey, StudyInfo> = {
  rsi2: {
    label: "RSI(2)", available: true,
    inputs: [["length", "2"], ["price", "CLOSE"], ["average", "Wilder's"]],
    levels: { overbought: 94, oversold: 2 },
  },
  stochrsi: {
    label: "StochRSI", available: true,
    inputs: [
      ["RSI length", "14"], ["stochastic length", "14"], ["K period", "3"], ["D period", "3"],
      ["RSI average", "Wilder's"], ["K/D average", "Wilder's"],
    ],
    levels: { overbought: 80, oversold: 20 },
  },
  rsi13: {
    label: "RSI(13)", available: true,
    inputs: [["length", "13"], ["price", "CLOSE"], ["average", "Wilder's"]],
    levels: { overbought: 70, oversold: 30 },
  },
  mfi: {
    label: "MFI", available: false, inputs: [], levels: null,
    pending: "Money Flow Index is not built yet.",
  },
}

export type OscToggles = Record<OscKey, boolean>

/**
 * The rows to draw, top to bottom. An unavailable study never gets a row, even
 * if its toggle is somehow on -- there is nothing to plot in it.
 */
export function activeOscillatorRows(toggles: OscToggles): OscRowKey[] {
  return ROW_ORDER.filter((k) => toggles[k] && OSC_STUDIES[k].available)
}

/**
 * Relative row heights: price first, then an equal share per oscillator.
 *
 * With every oscillator off the price panel takes the whole chart. The previous
 * split divided the indicator share by the row count, which with no rows is a
 * division by zero.
 */
export function oscillatorRowHeights(rows: number, priceWeight = 0.68): number[] {
  if (rows <= 0) return [1]
  return [priceWeight, ...Array.from({ length: rows }, () => (1 - priceWeight) / rows)]
}

/** Overbought / oversold reference lines for the rows being drawn. */
export function levelLines(rows: OscRowKey[]): { row: OscRowKey; value: number; kind: "overbought" | "oversold" }[] {
  return rows.flatMap((row) => {
    const lv = OSC_STUDIES[row].levels
    return lv
      ? [{ row, value: lv.overbought, kind: "overbought" as const },
         { row, value: lv.oversold, kind: "oversold" as const }]
      : []
  })
}
