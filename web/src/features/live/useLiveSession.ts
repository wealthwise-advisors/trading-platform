/**
 * The dashboard's half of a paper-trading session.
 *
 * THE BROWSER DRIVES THE BARS. The server holds the strategy, the broker and
 * the guard; this hook decides which bars it is allowed to see. That split is
 * deliberate: a session driven from the open tab stops when the tab does, and
 * a trading loop that keeps running after you have closed the window is a
 * trading loop that can surprise you.
 *
 * ONLY CLOSED BARS GO OVER THE WIRE. The last bar the price feed returns is
 * still forming -- its high and low can still move -- and a strategy that
 * sees it is reading the future by one tick. `closedBars` drops it, so the
 * paper result cannot flatter itself in a way the live one never could.
 *
 * SENDING THE SAME BAR TWICE IS HARMLESS. The server deduplicates on the
 * bar's own timestamp, so a reload, a retry or a second tab cannot re-open a
 * trade. This hook still tracks what it has sent, to avoid the pointless
 * round trips -- but correctness does not depend on it getting that right,
 * which is the only sane place to put that boundary.
 */

import { useCallback, useEffect, useRef } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { LiveStatus, OHLCVRecord } from "@/lib/types"

/** How often to poll the session's state, and to say "still here". */
const POLL_MS = 15_000

/**
 * Every bar except the last.
 *
 * The final element of a live price series is the bar in progress. Nothing
 * downstream can tell that from a closed one, so it is dropped here, once.
 */
export function closedBars(bars: OHLCVRecord[]): OHLCVRecord[] {
  return bars.length > 1 ? bars.slice(0, -1) : []
}

export function useLiveSession(bars: OHLCVRecord[] | undefined) {
  const qc = useQueryClient()
  // The last bar time this tab has pushed. A ref, not state: it must not
  // trigger a render, and it must be readable from inside the effect without
  // re-subscribing it every time a bar arrives.
  const sentUpTo = useRef<string | null>(null)

  const statusQ = useQuery({
    queryKey: ["live-status"],
    queryFn: () => api.liveStatus(),
    refetchInterval: POLL_MS,
    // Keep polling in a background tab so a session cannot appear frozen
    // just because the window lost focus.
    refetchIntervalInBackground: true,
  })
  const status = statusQ.data
  const running = !!status?.running

  const refresh = useCallback((next: LiveStatus) => {
    qc.setQueryData(["live-status"], next)
  }, [qc])

  const start = useMutation({
    mutationFn: api.liveStart,
    onSuccess: (s) => {
      // A fresh session has decided about nothing, so this tab starts its own
      // bookkeeping over -- otherwise a second session in the same tab would
      // skip every bar the first one had already pushed.
      sentUpTo.current = null
      refresh(s)
    },
  })
  const stop = useMutation({ mutationFn: api.liveStop, onSuccess: refresh })

  // ── push newly closed bars ────────────────────────────────────────────
  useEffect(() => {
    if (!running || !bars?.length) return
    let cancelled = false

    const pending = closedBars(bars).filter(
      (b) => sentUpTo.current === null || b.t > sentUpTo.current,
    )
    if (!pending.length) return

    void (async () => {
      for (const b of pending) {
        if (cancelled) return
        try {
          const next = await api.liveBar(b)
          // Marked as sent only after the server has taken it. Marking first
          // would lose a bar whenever a request failed, and a strategy with a
          // hole in its history is worse than one that saw a bar twice --
          // the server can spot the duplicate, but nothing can recover the
          // gap.
          sentUpTo.current = b.t
          refresh(next)
          if (!next.running) return     // stopped or halted; stop pushing
        } catch {
          // Leave sentUpTo where it is and let the next bar retry. A dropped
          // request is a network event, not a reason to abandon the session.
          return
        }
      }
    })()

    return () => { cancelled = true }
  }, [bars, running, refresh])

  // ── say we are still here, between bars ───────────────────────────────
  useEffect(() => {
    if (!running) return
    const id = setInterval(() => { void api.liveHeartbeat().then(refresh).catch(() => {}) }, POLL_MS)
    return () => clearInterval(id)
  }, [running, refresh])

  // ── going away ────────────────────────────────────────────────────────
  //
  // NOTHING IS SENT ON UNLOAD, deliberately. `pagehide` fires for a reload as
  // well as for a close, and the two cannot be told apart from inside the
  // page -- so stopping there killed the session every time the tab
  // refreshed, and "handle reconnects safely" became "there is never anything
  // to reconnect to".
  //
  // The server's staleness timeout covers both cases properly and needs no
  // cooperation from a tab that may already be gone: a closed tab stops
  // sending heartbeats and the session is reaped, while a reload is back
  // within seconds and simply carries on -- its replayed bars deduplicated by
  // timestamp, so nothing is re-traded.
  //
  // The cost is that a closed tab leaves a session nominally running for up to
  // the timeout. On paper that is harmless, and it is the same window a
  // crashed tab or a dropped connection would leave anyway -- a farewell
  // message you cannot rely on is not a safety mechanism.


  return {
    status,
    running,
    isStarting: start.isPending,
    startError: start.error as Error | null,
    start: start.mutateAsync,
    stop: stop.mutateAsync,
  }
}
