/**
 * Deploy: the button, its dialog, and the running session's state.
 *
 * It starts a PAPER session. Real order routing does not exist yet, and this
 * button says "paper" everywhere rather than implying otherwise -- an enabled
 * Deploy that quietly simulated would be worse than the disabled one it
 * replaced.
 *
 * While a session runs the button becomes Stop, and the label carries the
 * position so the state is legible without opening anything.
 */

import { useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { useConfigStore } from "@/store/configStore"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { FlaskConical, Rocket, Square } from "lucide-react"
import { DeployDialog, type DeployPlan } from "./DeployDialog"
import { useLiveSession } from "./useLiveSession"
import type { OHLCVRecord } from "@/lib/types"

export function DeployButton() {
  // The bars come from ResultsPage's own price query, read through the cache
  // by the SAME key so this shares that request rather than issuing a second.
  // Undefined until a backtest has run, which is exactly when there is
  // nothing to push anyway.
  const backtestId = useConfigStore((s) => s.backtestId)
  const priceQ = useQuery({
    queryKey: ["backtest", backtestId, "price-data"],
    queryFn: () => api.getPriceData(backtestId!),
    enabled: !!backtestId,
  })
  const bars: OHLCVRecord[] | undefined = priceQ.data?.bars
  const dataSource = useConfigStore((s) => s.dataSource)
  const symbol = useConfigStore((s) => s.symbol)
  const timeframe = useConfigStore((s) => s.timeframe)
  const strategyId = useConfigStore((s) => s.strategyId)
  const params = useConfigStore((s) => s.params)
  const [open, setOpen] = useState(false)
  const { status, running, start, stop, isStarting, startError } = useLiveSession(bars)

  // For the dialog's summary only -- the session is started by id, so a
  // missing catalogue costs a nice name and nothing else.
  const strategiesQ = useQuery({
    queryKey: ["strategies"], queryFn: () => api.strategies(), staleTime: 5 * 60_000,
  })
  const strategyName = useMemo(
    () => strategiesQ.data?.find((s) => s.id === strategyId)?.label ?? strategyId,
    [strategiesQ.data, strategyId],
  )

  const plan: DeployPlan = {
    mode: "paper",
    dataSource: dataSource,
    symbol: symbol,
    timeframe: timeframe,
    strategyName,
    params: params,
    contracts: 1,
  }

  if (running && status) {
    const pos = status.position
    return (
      <Button size="sm" variant="secondary" onClick={() => void stop()}
              title={`Paper session: ${status.strategy} on ${status.symbol}. `
                     + `${status.bars_seen} bars, ${status.orders_sent} orders. Click to stop.`}>
        <Square className="h-3.5 w-3.5 shrink-0" aria-hidden />
        <FlaskConical className="h-3.5 w-3.5 shrink-0 text-sky-800 dark:text-sky-300" aria-hidden />
        Stop paper
        <span className="ml-1 tabular-nums text-muted-foreground">
          {pos === 0 ? "flat" : `${pos > 0 ? "+" : ""}${pos}`}
        </span>
      </Button>
    )
  }

  return (
    <>
      <Button size="sm" onClick={() => setOpen(true)}
              title="Start a paper-trading session on the current configuration">
        <Rocket className="h-3.5 w-3.5" aria-hidden /> Deploy
      </Button>
      <DeployDialog
        open={open}
        onOpenChange={setOpen}
        plan={plan}
        starting={isStarting}
        error={startError?.message ?? null}
        onConfirm={async () => {
          try {
            await start({
              strategy_id: strategyId,
              symbol: symbol,
              params: params,
              contracts: plan.contracts,
            })
            // Closed only on success. A dialog that closes on a failed start
            // leaves someone believing a session is running when none is.
            setOpen(false)
          } catch {
            /* the message is rendered in the dialog */
          }
        }}
      />
    </>
  )
}
