/**
 * Change the chart's interval AND redraw it there.
 *
 * Shared by the toolbar's interval buttons and the Volume Profile dialog's
 * day-range table, so picking an interval means exactly one thing wherever it
 * is picked: set the timeframe, move the start date to that interval's
 * specified lookback, and re-run.
 *
 * WHY THE RUN. Setting cfg.timeframe alone did nothing visible -- the chart is
 * drawn from a finished backtest, its bars keyed on the backtest id and its
 * header labelled from that run's own summary -- so a new interval cannot
 * appear until a run has produced bars at it. The pill lit up, the chart did
 * not move, and nothing said why.
 *
 * The new timeframe is passed to the run as an override rather than read back
 * from the store, so the request cannot race the caller's own re-render. The
 * store is read through getState() for the same reason: the caller may be a
 * component that does not subscribe to it.
 */
import { useConfigStore } from "@/store/configStore"
import { startDateForTimeframe } from "@/lib/chartSetup"
import { useRunBacktest } from "./useRunBacktest"

export function useSelectInterval() {
  const run = useRunBacktest()

  const select = (tf: string) => {
    const cfg = useConfigStore.getState()
    cfg.setField("timeframe", tf)
    // Null when the interval has no specified range (25m, 35m): the dates are
    // then left exactly as they were, rather than moved by a guessed number.
    const start = startDateForTimeframe(cfg.endDate, tf, cfg.startDate)
    if (start) cfg.setField("startDate", start)
    run.mutate({ timeframe: tf, startDate: start || undefined })
  }

  return { select, pending: run.isPending }
}
