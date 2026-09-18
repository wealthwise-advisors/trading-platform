/**
 * What Deploy asks before it starts anything.
 *
 * This dialog exists because the button beside it will one day be able to
 * place real orders. Today it starts a paper session and nothing it does can
 * cost anyone money -- but the habit of reading a summary before starting a
 * trading loop is the thing worth building now, while the stakes are zero.
 *
 * So it states every input the session will run on, including the ones it did
 * not ask you for: the limits come from the server's own defaults, and they
 * are shown rather than assumed, because a rail nobody knows about is a rail
 * nobody can object to.
 *
 * PAPER IS SAID FOUR TIMES. In the title, in the mode row, in the banner and
 * on the button. Mistaking a simulated session for a real one is the single
 * most expensive misreading this screen could produce, so it is made
 * difficult rather than merely possible to avoid.
 */

import { useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent } from "@/components/ui/dialog"
import { FlaskConical, ShieldCheck } from "lucide-react"

export interface DeployPlan {
  mode: "paper"
  dataSource: string
  symbol: string
  timeframe: string
  strategyName: string
  params: Record<string, number | string | boolean>
  contracts: number
}

/** The server's own ceilings, mirrored so the dialog can show them.
 *  Kept next to src/live/paper_session.py::default_limits; if that changes
 *  and this does not, the dialog under-reports and the tests below fail. */
export function limitsFor(contracts: number) {
  const n = Math.max(1, contracts)
  return {
    maxPerOrder: n,
    maxPosition: n * 2,
    maxOrders: 50,
    minSecondsBetween: 1,
  }
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1
                    border-b border-[color:var(--hairline-soft)] last:border-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-xs text-foreground text-right break-words min-w-0">{value}</span>
    </div>
  )
}

export function DeployDialog({
  open, onOpenChange, plan, onConfirm, starting, error,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  plan: DeployPlan
  onConfirm: () => void
  starting: boolean
  error?: string | null
}) {
  const lim = limitsFor(plan.contracts)
  const confirmRef = useRef<HTMLButtonElement>(null)

  // Focus CANCEL, not Start. A dialog that opens with the action focused can
  // be dismissed into starting a trading session by someone pressing Enter to
  // clear something else.
  const cancelRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    if (open) cancelRef.current?.focus()
  }, [open])

  const paramList = Object.entries(plan.params)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-md"
        title="Start paper trading"
        description="Simulated orders filled against the chart. Nothing is sent to a broker."
      >
        {/* The banner. Not a colour alone -- an icon and the word, because a
            colour is the one cue a colour-blind reader does not get. */}
        <div className="mt-2 flex items-start gap-2 rounded-lg border
                        border-sky-500/30 bg-sky-500/10 px-3 py-2">
          <FlaskConical className="mt-0.5 h-4 w-4 shrink-0 text-sky-800 dark:text-sky-300" aria-hidden />
          <p className="text-[11.5px] leading-snug text-foreground">
            <b>Paper trading.</b> Orders are simulated and filled against the
            chart. Nothing is sent to a broker and no real money is involved.
          </p>
        </div>

        <dl className="mt-3">
          <Row label="Mode" value={<b>Paper trading (simulated)</b>} />
          <Row label="Data source" value={plan.dataSource} />
          <Row label="Symbol" value={plan.symbol} />
          <Row label="Timeframe" value={plan.timeframe} />
          <Row label="Strategy" value={plan.strategyName} />
          <Row
            label="Parameters"
            value={paramList.length
              ? paramList.map(([k, v]) => `${k}=${v}`).join(", ")
              : "defaults"}
          />
          <Row label="Order size" value={`${plan.contracts} contract${plan.contracts === 1 ? "" : "s"}`} />
        </dl>

        <div className="mt-3 rounded-lg border border-[color:var(--hairline-soft)]
                        bg-[color:var(--raise-1)] px-3 py-2">
          <p className="flex items-center gap-1.5 text-[11px] font-medium text-foreground">
            <ShieldCheck className="h-3.5 w-3.5 shrink-0" aria-hidden /> Limits this session runs under
          </p>
          <ul className="mt-1 space-y-0.5 text-[11px] text-muted-foreground">
            <li>At most {lim.maxPerOrder} contract{lim.maxPerOrder === 1 ? "" : "s"} per order</li>
            <li>Net position capped at ±{lim.maxPosition}</li>
            <li>At most {lim.maxOrders} orders this session</li>
            <li>At least {lim.minSecondsBetween}s between orders</li>
            <li>{plan.symbol} only — any other symbol is refused</li>
            <li>Stops on its own if this tab closes or loses connection</li>
          </ul>
        </div>

        {error && (
          <p role="alert" className="mt-2 text-[11.5px] text-destructive">{error}</p>
        )}

        <div className="mt-4 flex items-center justify-end gap-2">
          <Button ref={cancelRef} size="sm" variant="secondary"
                  onClick={() => onOpenChange(false)} disabled={starting}>
            Cancel
          </Button>
          <Button ref={confirmRef} size="sm" onClick={onConfirm} disabled={starting}>
            {starting ? "Starting…" : "Start paper session"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
