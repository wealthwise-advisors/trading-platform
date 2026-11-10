/**
 * Four charts side by side, each its own timeframe -- thinkorswim's chart grid
 * (requested 2026-11-10).
 *
 * Each cell is a run of the config panel's own settings at that cell's
 * timeframe, so every number in it is the Chart tab's number for that
 * timeframe. A run on live data keeps moving, as the Chart tab does.
 */
import { lazy, Suspense, useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { api } from "@/lib/api"
import { QUICK_INTERVALS, startDateForTimeframe } from "@/lib/chartSetup"
import { useConfigStore, ZIGZAG_DEV_3_DEFAULT, ZIGZAG_DEV_10_DEFAULT } from "@/store/configStore"
import { buildRunRequest } from "./useRunBacktest"
import { useFollowLive } from "./useFollowLive"

const CandlestickChart = lazy(() =>
  import("@/components/charts/CandlestickChart").then((m) => ({ default: m.CandlestickChart })))

export const DEFAULT_GRID_TIMEFRAMES = ["1m", "5m", "15m", "1h"]

interface Cell {
  tf: string
  id: string | null
  error: string | null
}

function GridCell({ cell, symbol, dataSource, onTf }: {
  cell: Cell
  symbol: string
  dataSource: string
  onTf: (tf: string) => void
}) {
  const priceQ = useQuery({
    queryKey: ["backtest", cell.id, "price-data"],
    queryFn: () => api.getPriceData(cell.id!),
    enabled: !!cell.id,
  })
  const zigzagQ = useQuery({
    queryKey: ["backtest", cell.id, "zigzag"],
    queryFn: () => api.getZigZag(cell.id!, ZIGZAG_DEV_3_DEFAULT / 100, ZIGZAG_DEV_10_DEFAULT / 100),
    enabled: !!cell.id,
  })
  useFollowLive(cell.id, dataSource)

  return (
    <div className="flex flex-col min-h-0 rounded-lg border border-[color:var(--hairline-soft)] p-1" data-testid={`grid-cell-${cell.tf}`}>
      <label className="flex items-center gap-2 px-1 pb-1 text-xs text-muted-foreground">
        timeframe
        <select aria-label="Grid timeframe" value={cell.tf} onChange={(e) => onTf(e.target.value)}
                className="rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-1.5 py-0.5 text-foreground">
          {QUICK_INTERVALS.map((tf) => <option key={tf} value={tf} className="bg-[var(--surface-1)]">{tf}</option>)}
        </select>
      </label>
      {/* Tall enough for the chart's own minimum (price plus six rows), so a
          chart never spills into the cell below it. */}
      <div className="h-[860px] min-h-0 overflow-hidden">
        {cell.error ? (
          <p className="p-4 text-sm text-[color:var(--loss)]">{cell.error}</p>
        ) : priceQ.data && zigzagQ.data ? (
          <Suspense fallback={<p className="p-4 text-sm text-muted-foreground">Loading chart…</p>}>
            <CandlestickChart symbol={symbol} strategyName="" interval={cell.tf}
                              bars={priceQ.data.bars} indicators={priceQ.data.indicators}
                              volumeContext={priceQ.data.volume_context}
                              zigzag={zigzagQ.data} trades={[]} />
          </Suspense>
        ) : (
          <p className="p-4 text-sm text-muted-foreground">{cell.id ? "Loading…" : "Press Load charts."}</p>
        )}
      </div>
    </div>
  )
}

export function MultiChartGrid() {
  const cfg = useConfigStore()
  const [cells, setCells] = useState<Cell[]>(DEFAULT_GRID_TIMEFRAMES.map((tf) => ({ tf, id: null, error: null })))
  const [busy, setBusy] = useState(false)

  const load = async (only?: number, tf?: string) => {
    setBusy(true)
    const s = useConfigStore.getState()
    const targets = cells.map((c, i) => ({ ...c, tf: i === only && tf ? tf : c.tf }))
    // One run at a time: four saved at once lock the results database, and
    // the broker is asked for one timeframe at a time either way.
    const next: Cell[] = []
    for (const [i, c] of targets.entries()) {
      if (only != null && i !== only) { next.push(c); continue }
      const start = startDateForTimeframe(s.endDate, c.tf, s.startDate)
      try {
        const run = await api.runBacktest(buildRunRequest(s, { timeframe: c.tf, startDate: start || undefined }))
        next.push({ tf: c.tf, id: run.backtest_id, error: null })
      } catch (e) {
        next.push({ tf: c.tf, id: null, error: e instanceof Error ? e.message : String(e) })
      }
    }
    setCells(next)
    setBusy(false)
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3 text-sm">
        <button type="button" onClick={() => void load()} disabled={busy}
                className="rounded-lg border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-3 py-1 hover:bg-[color:var(--raise-4)] disabled:opacity-50">
          {busy ? "Loading…" : "Load charts"}
        </button>
        <span className="text-muted-foreground">
          {cfg.symbol} · the config panel's settings, one timeframe per chart
        </span>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
        {cells.map((cell, i) => (
          <GridCell key={i} cell={cell} symbol={cfg.symbol} dataSource={cfg.dataSource}
                    onTf={(tf) => {
                      setCells((cs) => cs.map((c, j) => (j === i ? { tf, id: null, error: null } : c)))
                      if (cells.some((c) => c.id)) void load(i, tf)
                    }} />
        ))}
      </div>
    </div>
  )
}
