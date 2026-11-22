/**
 * Alerts the server saw reached (upgrade plan, Feature 4): which to announce, and how.
 *
 * The server checks the chart's price alerts against the live price even with no
 * browser open (api/alerts.py). This browser remembers the newest event it has
 * shown, so each one is announced once here, and one that fired while the app was
 * closed is announced when it next opens.
 */
export interface AlertEvent {
  id: number
  alert_id: string
  symbol: string
  /** "condition" for a scanner alert: then `note` says what matched and `price` is the close. */
  direction: "above" | "below" | "condition"
  level: number
  note: string
  price: number
  /** Eastern time with its offset, e.g. 2026-11-23T10:42:05-05:00. */
  fired_at: string
}

export const SEEN_KEY = "alert-events-seen"
/** A browser that has never shown an event starts with the last 12 hours only. */
const FIRST_VISIT_MS = 12 * 60 * 60 * 1000

/** The newest event this browser has shown; null on its first visit. */
export function seen(): number | null {
  try { const v = localStorage.getItem(SEEN_KEY); return v == null ? null : Number(v) || 0 } catch { return 0 }
}

/** The events to announce now; remembers the newest so none is announced twice. */
export function takeNew(events: AlertEvent[], now = Date.now()): AlertEvent[] {
  const after = seen()
  const fresh = events.filter((e) => after == null
    ? now - new Date(e.fired_at).getTime() <= FIRST_VISIT_MS
    : e.id > after)
  const newest = Math.max(after ?? 0, ...events.map((e) => e.id))
  try { if (events.length) localStorage.setItem(SEEN_KEY, String(newest)) } catch { /* private mode */ }
  return fresh
}

const money = (n: number) => n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

export function alertText(e: AlertEvent): string {
  const at = e.fired_at.slice(11, 16)
  if (e.direction === "condition") return `${e.symbol}: ${e.note}. Close ${money(e.price)} at ${at}.`
  return `${e.symbol} reached ${money(e.level)} (${e.direction}): traded ${money(e.price)} at ${at}.${e.note ? ` ${e.note}` : ""}`
}
