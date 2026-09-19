/**
 * Whether a panel is the element currently in full screen, and how to toggle it.
 *
 * Its own module rather than living beside the buttons that use it: a file that
 * exports both components and a hook loses fast refresh, which is what
 * react(only-export-components) is warning about.
 *
 * WHY FULL SCREEN IS WORTH A BUTTON ON THESE PANELS. Live state and the
 * consolidated tape carry twenty-odd columns each -- OHLC, change, volume,
 * position, P&L, the VWAP band pairs, POC, VAH, VAL and the last signal. At any
 * normal window width the row scrolls sideways, so reading across one bar is a
 * drag-and-read-back. Full screen is the difference between scrolling to the
 * VWAP columns and simply looking at them.
 *
 * The Fullscreen API on the panel itself, not a screenshot and not a modal: the
 * real element goes full screen, so it keeps its own scrolling, its sticky
 * header and its live updates while it is there.
 */

import { useCallback, useEffect, useState } from "react"
import type { RefObject } from "react"

export function usePanelFullscreen(ref: RefObject<HTMLElement | null>) {
  const [isFull, setIsFull] = useState(false)

  useEffect(() => {
    const sync = () => setIsFull(document.fullscreenElement === ref.current)
    document.addEventListener("fullscreenchange", sync)
    return () => document.removeEventListener("fullscreenchange", sync)
  }, [ref])

  const toggle = useCallback(() => {
    const el = ref.current
    if (!el) return
    // A rejected request -- an iframe without allowfullscreen, a browser that
    // refuses -- must not take the page down with it.
    if (document.fullscreenElement === el) void document.exitFullscreen().catch(() => {})
    else void el.requestFullscreen?.().catch(() => {})
  }, [ref])

  return { isFull, toggle }
}
