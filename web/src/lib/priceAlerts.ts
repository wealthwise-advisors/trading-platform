/**
 * Price alerts: a level on an instrument that the user wants to be told about.
 *
 * Marked on the chart and ticked against the bars on screen (alertTriggered).
 * Since 2026-11-22 they are also kept on the server (lib/accountSettings.ts) and
 * checked there against the live price, app open or closed (api/alerts.py);
 * components/AlertNotifier.tsx announces what the server saw reached.
 */

export interface PriceAlert {
  id: string
  symbol: string
  price: number
  /** "above" fires when price trades at or above `price`; "below" the reverse. */
  direction: "above" | "below"
  note: string
  createdAt: string
}

const KEY = "price-alerts"

export function loadAlerts(): PriceAlert[] {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "null")
    if (!Array.isArray(raw)) return []
    // Defensive: a hand-edited or half-written entry must not break the panel.
    return raw.filter(
      (a): a is PriceAlert =>
        a && typeof a.id === "string" && typeof a.symbol === "string" &&
        typeof a.price === "number" && Number.isFinite(a.price) &&
        (a.direction === "above" || a.direction === "below"),
    )
  } catch {
    return []
  }
}

export function saveAlerts(list: PriceAlert[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(list))
  } catch {
    /* private window or blocked storage: alerts still work for this session */
  }
}

export function newAlert(symbol: string, price: number,
                         direction: "above" | "below", note = ""): PriceAlert {
  return {
    // crypto.randomUUID is unavailable on insecure origins in some browsers,
    // and this id only has to be unique within one list.
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    symbol, price, direction, note, createdAt: new Date().toISOString(),
  }
}

/**
 * Has this alert been reached by the bars on screen?
 *
 * Checked against the bar HIGH and LOW, not the close: a level touched
 * intrabar was reached, and answering off the close alone would miss it.
 * Returns null when there are no bars to judge by -- which is not the same
 * as "not triggered", and the panel says so rather than showing a green tick.
 */
export function alertTriggered(
  a: PriceAlert,
  bars: Array<{ h: number; l: number }>,
): boolean | null {
  if (!bars.length) return null
  return a.direction === "above"
    ? bars.some((b) => b.h >= a.price)
    : bars.some((b) => b.l <= a.price)
}
