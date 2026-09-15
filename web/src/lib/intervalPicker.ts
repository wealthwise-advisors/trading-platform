/**
 * The Interval Picker's list: which intervals it shows, in what order, which are
 * starred, and what each row says. Pure functions, so every rule the popup
 * applies can be tested without rendering it.
 *
 * WHERE THE NUMBERS COME FROM
 * ---------------------------
 * Every interval is ALL_CHART_TIMEFRAMES and every day count is daysFor(), both
 * from lib/chartSetup.ts. Nothing here adds an interval or a day count. An
 * interval the table has no entry for (2m, 25m, 35m) gets no range label rather
 * than a guessed one -- the same null chartSetup returns, for the same reason.
 *
 * WHAT A USER CAN CHANGE
 * ----------------------
 * Only presentation, and only in this browser: the order of the rows, which
 * rows are hidden, and which are starred. Those are conveniences -- like the
 * instrument picker's favourites they never reach the config store, a saved
 * config, or a request. A user cannot add an interval (the backend serves only
 * these eleven) or edit a day count (that would override the specified table).
 */
import { ALL_CHART_TIMEFRAMES, daysFor } from "./chartSetup"

export const FAV_KEY = "interval-favourites"
export const LAYOUT_KEY = "interval-list-layout"

const KNOWN = new Set<string>(ALL_CHART_TIMEFRAMES)

export interface Layout {
  /** Every known interval exactly once, in display order. */
  order: string[]
  /** Intervals left out of the Time frame tab. */
  hidden: string[]
}

type Store = Pick<Storage, "getItem" | "setItem">

/** localStorage when this browser allows it. Private modes can throw on access. */
function browserStore(): Store | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage
  } catch {
    return null
  }
}

export function defaultLayout(): Layout {
  return { order: [...ALL_CHART_TIMEFRAMES], hidden: [] }
}

/**
 * Coerce whatever was stored into a valid layout.
 *
 * Unknown intervals are dropped, duplicates collapse, and any known interval
 * missing from the stored order is appended in its natural place at the end --
 * so an interval added to chartSetup.ts later appears in everyone's list
 * instead of being silently absent because their saved order predates it.
 */
export function normalizeLayout(raw: unknown): Layout {
  const r = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {}
  const order: string[] = []
  for (const tf of Array.isArray(r.order) ? r.order : []) {
    if (typeof tf === "string" && KNOWN.has(tf) && !order.includes(tf)) order.push(tf)
  }
  for (const tf of ALL_CHART_TIMEFRAMES) if (!order.includes(tf)) order.push(tf)
  const hidden = [...new Set(
    (Array.isArray(r.hidden) ? r.hidden : [])
      .filter((tf): tf is string => typeof tf === "string" && KNOWN.has(tf)),
  )]
  return { order, hidden }
}

export function loadLayout(store: Store | null = browserStore()): Layout {
  try {
    const raw = store?.getItem(LAYOUT_KEY)
    return normalizeLayout(raw ? JSON.parse(raw) : null)
  } catch {
    return defaultLayout()
  }
}

export function saveLayout(layout: Layout, store: Store | null = browserStore()): void {
  try { store?.setItem(LAYOUT_KEY, JSON.stringify(layout)) } catch { /* private mode */ }
}

export function loadFavourites(store: Store | null = browserStore()): string[] {
  try {
    const raw = store?.getItem(FAV_KEY)
    const v = raw ? JSON.parse(raw) : []
    return Array.isArray(v)
      ? [...new Set(v.filter((x): x is string => typeof x === "string" && KNOWN.has(x)))]
      : []
  } catch {
    return []
  }
}

export function saveFavourites(favs: string[], store: Store | null = browserStore()): void {
  try { store?.setItem(FAV_KEY, JSON.stringify(favs)) } catch { /* private mode */ }
}

export function toggleFavourite(favs: string[], tf: string): string[] {
  return favs.includes(tf) ? favs.filter((f) => f !== tf) : [...favs, tf]
}

/** Swap `tf` with its neighbour; a move off either end changes nothing. */
export function moveInterval(order: string[], tf: string, delta: -1 | 1): string[] {
  const i = order.indexOf(tf)
  const j = i + delta
  if (i < 0 || j < 0 || j >= order.length) return order
  const next = [...order]
  ;[next[i], next[j]] = [next[j], next[i]]
  return next
}

export function toggleHidden(layout: Layout, tf: string): Layout {
  return {
    ...layout,
    hidden: layout.hidden.includes(tf)
      ? layout.hidden.filter((h) => h !== tf)
      : [...layout.hidden, tf],
  }
}

/** The Time frame tab: the custom order, minus hidden rows. */
export function visibleRows(layout: Layout): string[] {
  return layout.order.filter((tf) => !layout.hidden.includes(tf))
}

/**
 * The Favorites tab: starred rows in the custom order.
 *
 * Hidden rows are NOT removed here. Hiding tidies the full list; starring is an
 * explicit request to see that interval, and the more specific choice wins.
 */
export function favouriteRows(layout: Layout, favs: string[]): string[] {
  return layout.order.filter((tf) => favs.includes(tf))
}

/** "2 D" for an interval with a specified day count, null otherwise. */
export function rangeLabel(tf: string): string | null {
  const days = daysFor(tf)
  return days == null ? null : `${days} D`
}
