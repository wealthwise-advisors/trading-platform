import type { BacktestSummary } from "@/lib/types"
import { GOOD } from "@/components/cards/StatCard"

function sessionDuration(start: string, end: string): string {
  const [sh, sm] = start.split(":").map(Number)
  const [eh, em] = end.split(":").map(Number)
  const totalMin = (eh * 60 + em) - (sh * 60 + sm)
  const h = Math.floor(totalMin / 60)
  const m = totalMin % 60
  return `${h}h ${m}m`
}

function fmtRelative(iso: string | null): string {
  if (!iso) return "—"
  const diffSec = (Date.now() - new Date(iso).getTime()) / 1000
  if (diffSec < 60) return "just now"
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`
  return new Date(iso).toLocaleTimeString()
}

export function ResultsFooterBar({ s, lastRunAt }: { s: BacktestSummary; lastRunAt: string | null }) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-muted-foreground px-1">
      <span className="flex items-center gap-1"><span style={{ color: GOOD }}>●</span> Status: Completed</span>
      <span>Backtest ID: {s.backtest_id}</span>
      <span>Duration: {sessionDuration(s.session_start, s.session_end)}</span>
      <span>Data Points: {s.data_points.toLocaleString()}</span>
      <span>Last updated: {fmtRelative(lastRunAt)}</span>
    </div>
  )
}
