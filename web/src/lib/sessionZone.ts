/**
 * Which clock the Session Hours fields are typed in, and the Market Grid's tape
 * is labelled in.
 *
 * WHAT IS STORED NEVER CHANGES. The backend reads session_start / session_end
 * as EASTERN exchange time -- that pair is what anchors VWAP, what a saved
 * config holds, and what a report prints -- so a zone chosen here converts on
 * the way in and on the way out and alters nothing that is sent. Pick Central
 * and the same 09:30-16:00 ET window reads 08:30-15:00; type 08:00 there and
 * 09:00 ET is stored. Switching zone therefore RELABELS a window, it does not
 * re-filter one: the backtest you were about to run is the one you still run.
 *
 * Offsets are minutes to ADD to an Eastern time for display, the same
 * convention the Market Grid's tape clocks use.
 *
 * They are fixed gaps from Eastern rather than real time-zone rules on purpose.
 * US Central, Mountain and Pacific enter and leave DST on the same instant as
 * Eastern, so the gap never moves and a fixed number is exactly right all year.
 * Arizona does not observe DST, so its gap from Eastern is 2 hours in summer
 * and 3 in winter -- which is why no zone that skips DST is offered here rather
 * than offered and silently wrong for half the year.
 */
import { pad } from "./clock"

export interface SessionZone {
  /** Shown on the control, e.g. "CT". */
  short: string
  /** The spoken name, used as the title and the accessible name. */
  label: string
  /** Minutes to ADD to an Eastern time to display it in this zone. */
  offset: number
}

export const SESSION_ZONES: readonly SessionZone[] = [
  { short: "ET", label: "Eastern (exchange)", offset: 0 },
  { short: "CT", label: "Central", offset: -60 },
  { short: "MT", label: "Mountain", offset: -120 },
  { short: "PT", label: "Pacific", offset: -180 },
] as const

const MINUTES_PER_DAY = 24 * 60
const HHMM = /^(\d{1,2}):(\d{2})$/

/**
 * "HH:MM" shifted by `minutes`, wrapping at midnight.
 *
 * Wrapping is required, not a nicety: the Globex preset runs 18:00-17:00 ET,
 * and on Pacific that is 15:00-14:00. Anything unparseable comes back
 * untouched -- a half-typed field must not be rewritten under the cursor.
 */
export function shiftClock(hhmm: string, minutes: number): string {
  const m = HHMM.exec((hhmm ?? "").trim())
  if (!m) return hhmm
  const h = Number(m[1])
  const min = Number(m[2])
  if (h > 23 || min > 59) return hhmm
  const total = (((h * 60 + min + minutes) % MINUTES_PER_DAY) + MINUTES_PER_DAY) % MINUTES_PER_DAY
  return `${pad(Math.floor(total / 60))}:${pad(total % 60)}`
}

/** An Eastern time as the chosen zone shows it. */
export function toZone(eastern: string, offset: number): string {
  return shiftClock(eastern, offset)
}

/** A time typed in the chosen zone, back to the Eastern time that is stored. */
export function fromZone(zoneTime: string, offset: number): string {
  return shiftClock(zoneTime, -offset)
}

/** The badge for an offset; anything unrecognised reads as Eastern. */
export function zoneShort(offset: number): string {
  return SESSION_ZONES.find((z) => z.offset === offset)?.short ?? "ET"
}

export const ZONE_KEY = "session-hours-zone"

interface Store {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

const browserStore = (): Store | null =>
  typeof localStorage === "undefined" ? null : localStorage

/**
 * The chosen zone, per browser.
 *
 * Persisted because it describes the person, not the backtest: someone in
 * Chicago is in Chicago tomorrow too, and re-picking CT on every reload is a
 * step with no decision in it. It is a display preference, so it never reaches
 * the config store or a request -- exactly like the interval list's favourites.
 * A blocked or corrupt store falls back to Eastern rather than throwing.
 */
export function loadZoneOffset(store: Store | null = browserStore()): number {
  try {
    const raw = store?.getItem(ZONE_KEY)
    const n = Number(raw)
    return SESSION_ZONES.some((z) => z.offset === n) ? n : 0
  } catch {
    return 0
  }
}

export function saveZoneOffset(offset: number, store: Store | null = browserStore()): void {
  try {
    store?.setItem(ZONE_KEY, String(offset))
  } catch {
    /* storage blocked -- the choice simply does not persist */
  }
}
