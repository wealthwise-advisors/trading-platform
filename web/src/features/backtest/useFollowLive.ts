/**
 * Keep a run on live data moving: poll for new bars and swap them into the
 * chart's query, at Market Grid's follow-live pace. The server answers
 * live:false once there is nothing more to fetch, and polling stops.
 *
 * Shared by the Chart tab and every Multi-chart cell.
 */
import { useEffect } from "react"
import { useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api"
import { FOLLOW_POLL_MS } from "@/lib/followLive"

export function useFollowLive(backtestId: string | null | undefined, dataSource: string | undefined) {
  const queryClient = useQueryClient()
  const follow = dataSource === "schwab"
  useEffect(() => {
    if (!backtestId || !follow) return
    let busy = false
    const tick = async () => {
      if (busy || document.hidden) return
      busy = true
      try {
        const fresh = await api.refreshPriceData(backtestId)
        queryClient.setQueryData(["backtest", backtestId, "price-data"], fresh)
        if (fresh.live) void queryClient.invalidateQueries({ queryKey: ["backtest", backtestId, "zigzag"] })
        else clearInterval(timer)
      } catch {
        // The next tick tries again.
      } finally {
        busy = false
      }
    }
    const timer = setInterval(() => void tick(), FOLLOW_POLL_MS)
    void tick()
    return () => clearInterval(timer)
  }, [backtestId, follow, queryClient])
}
