import type { BacktestSummary } from "@/lib/types"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { GOOD } from "@/components/cards/StatCard"

function fmtDate(iso: string | null): string {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "2-digit" })
}

export function StatusBanner({ s, lastRunAt }: { s: BacktestSummary; lastRunAt: string | null }) {
  const good = s.total_return_pct >= 0
  const message = good ? "Strategy performed well. Great job!" : "Strategy underperformed — see the insights below."

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border px-4 py-3"
         style={{ borderColor: `color-mix(in srgb, ${GOOD} 35%, transparent)`,
                  background: `color-mix(in srgb, ${GOOD} 10%, transparent)` }}>
      <div className="flex items-center gap-2 text-sm">
        <span style={{ color: GOOD }}>✅</span>
        <span className="font-medium">Backtest complete!</span>
        <span className="text-muted-foreground">{message}</span>
      </div>
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span>Backtested on: {fmtDate(lastRunAt)} • {s.session_start}–{s.session_end} EST</span>
        <Button asChild size="sm" variant="secondary">
          <a href={api.reportUrl(s.backtest_id)} download>📄 View Report</a>
        </Button>
      </div>
    </div>
  )
}
