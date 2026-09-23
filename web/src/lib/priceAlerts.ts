/**
 * Price alerts: a level on an instrument that the user wants to be told about.
 *
 * WHY THESE LIVE IN THE BROWSER. An alert that fires while the app is closed
 * needs a server watching a live feed and a way to reach the user -- a push
 * subscription or an email. None of that exists here, and an alert that
 * silently never fires is worse than no alert at all. So these are explicitly
 * CHART alerts: a level you mark, see drawn on the chart, and that reports
 * whether the loaded bars have crossed it. That is a real, honest answer to
 * "tell me when ES reaches 4600" for a platform that backtests and replays.
 *
 * Stored per browser, like the watchlist and the interval favourites.
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
