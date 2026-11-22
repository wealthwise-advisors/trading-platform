/**
 * Keep a run on live data moving: poll for new bars and swap them into the
 * chart's query. From every 2 s while the server's Schwab stream is up (slower
 * when the chart is heavy to redraw), every 15 s when the server has to ask
 * Schwab itself (lib/followLive.ts nextChartPollMs).
 * The server answers live:false once there is nothing more to fetch, and
 * polling stops.
 *
 * Shared by the Chart tab and every Multi-chart cell.
 */
import { useEffect } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api"
import { FOLLOW_POLL_MS, nextChartPollMs } from "@/lib/followLive"

export function useFollowLive(backtestId: string | null | undefined, dataSource: string | undefined) {
  const queryClient = useQueryClient()
  const follow = dataSource === "schwab"
  useEffect(() => {
    if (!backtestId || !follow) return
    let timer: ReturnType<typeof setTimeout> | undefined
    let stopped = false
    let zigAt = 0, zigBars = -1
    const tick = async () => {
      let next = FOLLOW_POLL_MS
      if (!document.hidden) {
        try {
          const fresh = await api.refreshPriceData(backtestId)
          if (stopped) return
          const t0 = performance.now()
          queryClient.setQueryData(["backtest", backtestId, "price-data"], fresh)
          if (!fresh.live) return
          // Swing points: on a new bar, or every 15 s -- not on every 2 s move of the forming bar.
          if (fresh.bars.length !== zigBars || Date.now() - zigAt >= FOLLOW_POLL_MS) {
            zigAt = Date.now(); zigBars = fresh.bars.length
            void queryClient.invalidateQueries({ queryKey: ["backtest", backtestId, "zigzag"] })
          }
          // The chart redraws before the next frame; that time sets the pace.
          await new Promise((r) => requestAnimationFrame(() => setTimeout(r, 0)))
          next = nextChartPollMs(fresh, performance.now() - t0)
        } catch {
          // The next tick tries again.
        }
      }
      if (!stopped) timer = setTimeout(() => void tick(), next)
    }
    void tick()
    return () => { stopped = true; clearTimeout(timer) }
  }, [backtestId, follow, queryClient])
}
