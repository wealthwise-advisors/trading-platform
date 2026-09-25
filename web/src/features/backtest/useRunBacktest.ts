/**
 * Running a backtest, from anywhere.
 *
 * WHY THIS EXISTS. The run lived inside ConfigForm, so the only thing that
 * could start one was the Run Backtest button. That was fine until the chart
 * toolbar grew interval buttons: clicking 1m wrote cfg.timeframe and lit the
 * pill, but the chart kept drawing the finished run's bars at the interval
 * that run used, because the chart's data is keyed on the backtest id and its
 * header is labelled from the run's own summary.
 *
 * So the button looked like it worked and nothing happened. Pulling the
 * mutation out here lets the toolbar re-run with the new interval, which is
 * what changing the interval on a chart is supposed to mean, and keeps ONE
 * definition of what a run request contains -- ConfigForm uses this too, so
 * the two entry points cannot drift into sending different payloads.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query"

import { api } from "@/lib/api"
import { useConfigStore } from "@/store/configStore"

/** Fields a caller may change as part of starting the run, so it does not
 *  have to write the store and then race its own render to read it back. */
export interface RunOverrides {
  timeframe?: string
  startDate?: string
}

export function useRunBacktest() {
  const cfg = useConfigStore()
  const queryClient = useQueryClient()

  return useMutation({
    // The request is built when the mutation FIRES, not when the hook renders,
    // so a caller that changes a field and immediately runs -- which is exactly
    // what the interval buttons do -- sends the new value rather than the one
    // captured at render time.
    mutationFn: (overrides: RunOverrides | void) => {
      const o = (overrides ?? {}) as RunOverrides
      const s = useConfigStore.getState()
      return api.runBacktest({
        data_source: s.dataSource,
        symbol: s.symbol,
        timeframe: o.timeframe ?? s.timeframe,
        strategy_id: s.strategyId,
        params: s.params,
        initial_capital: s.initialCapital,
        contracts_per_trade: s.contractsPerTrade,
        commission_per_contract: s.commission,
        start_date: o.startDate ?? s.startDate,
        end_date: s.endDate,
        // null on both edges tells the engine to skip session filtering.
        session_start: s.session24h ? null : s.sessionStart,
        session_end: s.session24h ? null : s.sessionEnd,
        zigzag_dev_3: s.zigzagDev3 / 100,
        zigzag_dev_10: s.zigzagDev10 / 100,
      })
    },
    onSuccess: (summary) => {
      cfg.setBacktestId(summary.backtest_id)
      cfg.setLastRunAt(new Date().toISOString())
      queryClient.invalidateQueries({ queryKey: ["backtest", summary.backtest_id] })
    },
  })
}
