/**
 * Persistence for the user's deviation-colour palettes.
 *
 * Uses localStorage under an "autotrader.*" key, matching the volume-profile
 * defaults in CandlestickChart and the saved backtest configs — no second
 * settings system.
 *
 * Only presentation is stored. Nothing here touches VWAP, the deviation
 * formula, grouping, or which rows appear; the palettes are handed to
 * buildDeviationColorGroups and affect the fill of a cell and nothing else.
 */
import { DEFAULT_UPPER_PALETTE, DEFAULT_LOWER_PALETTE } from "./deviationColors"

export const DEVIATION_COLOR_STORE_KEY = "autotrader.deviationColors"

/** Slots offered in the settings UI. Groups beyond this still get colours,
 *  generated deterministically — the limit is on what is editable, not on how
 *  many groups the tape can show. */
export const EDITABLE_SLOTS = 8

export interface DeviationPalettes {
  upper: string[]
  lower: string[]
}

export function factoryPalettes(): DeviationPalettes {
  return {
    upper: DEFAULT_UPPER_PALETTE.slice(0, EDITABLE_SLOTS),
    lower: DEFAULT_LOWER_PALETTE.slice(0, EDITABLE_SLOTS),
  }
}

/** #rgb or #rrggbb. Anything else is treated as corrupt and replaced. */
const HEX = /^#(?:[0-9a-f]{3}|[0-9a-f]{6})$/i

function sanitise(input: unknown, fallback: readonly string[]): string[] {
  const out = fallback.slice(0, EDITABLE_SLOTS)
  if (!Array.isArray(input)) return out
  for (let i = 0; i < out.length; i++) {
    const v = input[i]
    if (typeof v === "string" && HEX.test(v.trim())) out[i] = v.trim()
  }
  return out
}

/**
 * Stored palettes, falling back to factory for anything missing or malformed.
 * Never throws: storage can be disabled, full, or hold a value written by an
 * older build, and none of that should stop the tape rendering.
 */
export function loadPalettes(): DeviationPalettes {
  const factory = factoryPalettes()
  try {
    const raw = localStorage.getItem(DEVIATION_COLOR_STORE_KEY)
    if (!raw) return factory
    const parsed = JSON.parse(raw) as Partial<DeviationPalettes>
    return {
      upper: sanitise(parsed?.upper, factory.upper),
      lower: sanitise(parsed?.lower, factory.lower),
    }
  } catch {
    return factory
  }
}

/** True when the choice was stored. False means storage was unavailable. */
export function savePalettes(p: DeviationPalettes): boolean {
  try {
    localStorage.setItem(DEVIATION_COLOR_STORE_KEY, JSON.stringify({
      upper: p.upper.slice(0, EDITABLE_SLOTS),
      lower: p.lower.slice(0, EDITABLE_SLOTS),
    }))
    return true
  } catch {
    return false
  }
}

/** Forget the customisation; the next load returns factory colours. */
export function resetPalettes(): DeviationPalettes {
  try {
    localStorage.removeItem(DEVIATION_COLOR_STORE_KEY)
  } catch {
    /* nothing stored is the state we wanted anyway */
  }
  return factoryPalettes()
}
