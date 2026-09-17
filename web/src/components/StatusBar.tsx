/**
 * The bottom strip: what was run, over what, when, and whether it finished.
 *
 * Every field is read from state the app already holds — the config store for
 * the source, symbol, timeframe and dates, the summary for the trade count,
 * and /api/version for the build. Nothing here is decorative: "Data:
 * Synthetic" is the difference between a result worth acting on and a shape
 * generated from a random walk, and until now that fact lived only in a
 * dropdown the reader had to scroll back to.
 */
import { useQuery } from "@tanstack/react-query"
import { Clock, Database, Hash } from "lucide-react"

import { api } from "@/lib/api"
import { useConfigStore } from "@/store/configStore"

const SOURCE_LABEL: Record<string, string> = {
  synthetic: "Synthetic",
  external_csv: "CSV archive",
  schwab: "Schwab",
  rithmic: "Rithmic",
}

/** "Sep 16, 2026 15:32:18 ET" — the tape's clock, not the reader's. */
function runLabel(iso: string | null): string | null {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  })
}

export function StatusBar() {
  const dataSource = useConfigStore((s) => s.dataSource)
  const symbol = useConfigStore((s) => s.symbol)
  const timeframe = useConfigStore((s) => s.timeframe)
  const startDate = useConfigStore((s) => s.startDate)
  const endDate = useConfigStore((s) => s.endDate)
  const backtestId = useConfigStore((s) => s.backtestId)
  const lastRunAt = useConfigStore((s) => s.lastRunAt)

  const versionQ = useQuery({
    queryKey: ["version"],
    queryFn: () => api.version(),
    staleTime: Infinity,
  })

  // Same key the results page uses, so this shares that request rather than
  // issuing a second one -- and cannot show a trade count that disagrees with
  // the table above it.
  const summaryQ = useQuery({
    queryKey: ["backtest", backtestId, "summary"],
    queryFn: () => api.getBacktest(backtestId!),
    enabled: !!backtestId,
  })
  const trades = summaryQ.data?.total_trades ?? null

  const ran = runLabel(lastRunAt)
  const source = SOURCE_LABEL[dataSource] ?? dataSource
  // Synthetic is the one source whose numbers are not a market, so it is the
  // one worth marking rather than stating flatly.
  const synthetic = dataSource === "synthetic"

  return (
    <footer className="status-bar" aria-label="Run status">
      <span className="inline-flex items-center gap-1.5">
        <Database className="h-3 w-3 shrink-0" aria-hidden />
        Data:{" "}
        <span className={synthetic ? "text-amber-800 dark:text-amber-300" : "text-foreground"}>{source}</span>
      </span>

      <span className="inline-flex items-center gap-1.5">
        <Hash className="h-3 w-3 shrink-0" aria-hidden />
        <span className="text-foreground">{symbol}</span>
        <span>{timeframe}</span>
        <span>{startDate} → {endDate}</span>
        {trades != null && (
          <span className="text-foreground">
            {trades.toLocaleString()} {trades === 1 ? "trade" : "trades"}
          </span>
        )}
      </span>

      <span className="ml-auto inline-flex items-center gap-1.5">
        <Clock className="h-3 w-3 shrink-0" aria-hidden />
        {ran ? <>Last run: <span className="text-foreground">{ran}</span></> : "Not run yet"}
      </span>

      {/* Green only for a run that actually produced a result. "Completed"
          next to an empty page would be the app congratulating itself. */}
      <span className={`rounded-md px-2 py-0.5 ${backtestId
          ? "bg-emerald-500/15 text-emerald-800 dark:text-emerald-300 ring-1 ring-emerald-400/25"
          : "bg-[color:var(--raise-3)] text-muted-foreground ring-1 ring-[color:var(--hairline-mid)]"}`}>
        {backtestId ? "Completed" : "Idle"}
      </span>

      {/* Only a real version number. A source checkout reports "unknown (not
          installed as a package)", and printing that in the corner of the
          dashboard reads as a fault rather than as a dev build. */}
      {/^\d/.test(versionQ.data?.version ?? "") && (
        <span className="text-muted-foreground/75">v{versionQ.data!.version}</span>
      )}
    </footer>
  )
}
