/**
 * The strip above the chart: interval, alert, replay, undo/redo, snapshot.
 *
 * WHAT EACH CONTROL ACTUALLY DOES, since a toolbar of decorative buttons is
 * the easiest thing in the world to build and the least useful:
 *
 *   intervals  Quick buttons plus the full IntervalPicker popup. Both set
 *              cfg.timeframe, move the start date, and RE-RUN the backtest so
 *              the chart actually redraws at the new interval -- see
 *              setInterval below for why the run is required.
 *   Alert      Opens a real price-alert form. The level is stored, drawn on
 *              the chart, and listed in the Alerts tab on the right rail.
 *   Replay     Opens the replay page. That page already exists; this is the
 *              same setPage("replay") the Results header button calls.
 *   undo/redo  Steps through the drawings made with the left-hand rail.
 *   camera     Plotly's PNG export -- the same one already in the Save menu.
 *
 * Nothing here is a placeholder.
 */
import { useState } from "react"
import {
  Bell, Rewind, Undo2, Redo2, Camera, Plus, ZoomIn, ZoomOut, Home,
} from "lucide-react"

import { IntervalPicker } from "@/components/IntervalPicker"
import { useRunBacktest } from "@/features/backtest/useRunBacktest"
import { useConfigStore } from "@/store/configStore"
import { startDateForTimeframe } from "@/lib/chartSetup"
import { loadAlerts, saveAlerts, newAlert } from "@/lib/priceAlerts"

/** The intervals the reference puts on the strip, as quick buttons. */
const QUICK = ["1m", "5m", "15m", "30m", "1h", "4h", "1D", "1W", "1M"]

const BTN =
  "flex items-center gap-1 rounded border border-[color:var(--hairline-mid)] " +
  "bg-[color:var(--raise-3)] px-2 py-0.5 hover:bg-[color:var(--raise-4)] text-foreground"

export function ChartToolbar({
  symbol, lastPrice, canUndo, canRedo, onUndo, onRedo, onSnapshot, onAlertsChanged,
  onZoomIn, onZoomOut, onResetView, actions,
}: {
  symbol: string
  lastPrice: number | null
  canUndo: boolean
  canRedo: boolean
  onUndo: () => void
  onRedo: () => void
  onSnapshot: () => void
  onAlertsChanged: () => void
  /** Moved off Plotly's floating modebar, which is switched off: it repeated
   *  the camera this row already had and cost a strip of chart to sit in. */
  onZoomIn: () => void
  onZoomOut: () => void
  onResetView: () => void
  /** The chart's own controls -- Legend, Indicators, Save, full screen.
   *  They used to ride on the instrument line above; the reference puts
   *  every control on one row and leaves that line to the quote. */
  actions?: React.ReactNode
}) {
  const cfg = useConfigStore()
  const setPage = useConfigStore((s) => s.setPage)
  const [alertOpen, setAlertOpen] = useState(false)
  const [price, setPrice] = useState("")
  const [direction, setDirection] = useState<"above" | "below">("above")

  const run = useRunBacktest()

  /**
   * Change the interval AND redraw the chart at it.
   *
   * Setting cfg.timeframe alone did nothing visible, which is the bug this
   * fixes. The chart is drawn from a finished backtest -- its bars are keyed
   * on the backtest id and its header is labelled from that run's own summary
   * -- so a new interval cannot appear until a run has produced bars at it.
   * The pill lit up, the chart did not move, and nothing said why.
   *
   * On a chart toolbar, picking an interval means "show me this interval", so
   * this runs the backtest rather than quietly staging a value for later. The
   * new timeframe is passed as an override rather than read back from the
   * store, so the request cannot race this component's own re-render.
   */
  const setInterval = (tf: string) => {
    cfg.setField("timeframe", tf)
    const start = startDateForTimeframe(cfg.endDate, tf, cfg.startDate)
    if (start) cfg.setField("startDate", start)
    run.mutate({ timeframe: tf, startDate: start || undefined })
  }

  const addAlert = () => {
    const p = Number(price)
    if (!Number.isFinite(p) || p <= 0) return
    saveAlerts([...loadAlerts(), newAlert(symbol, p, direction)])
    setPrice("")
    setAlertOpen(false)
    onAlertsChanged()
    // `storage` only fires in OTHER tabs, so the header bell in THIS tab
    // would keep its old count without an explicit nudge.
    window.dispatchEvent(new Event("alerts-changed"))
  }

  return (
    <div className="flex items-center gap-1 overflow-x-auto tabs-scroll px-1 py-0.5 text-[11px]
                    border-b border-[color:var(--hairline-soft)]">
      {/* ── Interval quick buttons ── */}
      <div role="group" aria-label="Bar interval" className="flex items-center gap-0.5">
        {QUICK.map((tf) => (
          <button
            key={tf}
            type="button"
            aria-pressed={cfg.timeframe === tf}
            disabled={run.isPending}
            onClick={() => setInterval(tf)}
            title={`Redraw the chart with ${tf} bars`}
            className={`rounded px-1.5 py-0.5 transition-colors disabled:opacity-50 ${
              cfg.timeframe === tf
                ? "bg-[#2563eb] text-white font-medium"
                : "text-muted-foreground hover:bg-[color:var(--raise-3)] hover:text-foreground"
            }`}
          >
            {tf}
          </button>
        ))}
      </div>

      {/* The full picker, with favourites and custom intervals. */}
      <IntervalPicker value={cfg.timeframe} onChange={setInterval} compact />

      <span className="mx-1 h-4 w-px bg-[color:var(--hairline-soft)]" aria-hidden />

      {/* ── Alert ── */}
      <span className="relative">
        <button type="button" className={BTN}
                aria-haspopup="dialog" aria-expanded={alertOpen}
                onClick={() => {
                  // Seed with the last close: an alert is nearly always set
                  // relative to where price is now.
                  if (!alertOpen && lastPrice != null && !price) setPrice(lastPrice.toFixed(2))
                  setAlertOpen((v) => !v)
                }}
                title="Set a price alert on this instrument">
          <Bell className="h-3 w-3" aria-hidden /> Alert
        </button>
        {alertOpen && (
          <div role="dialog" aria-label="New price alert"
               className="absolute left-0 top-7 z-40 w-60 rounded-lg border border-[color:var(--hairline-mid)]
                          bg-[var(--surface-1)] p-2.5 shadow-xl">
            <p className="mb-2 text-[11px] text-muted-foreground">
              Alert on <span className="text-foreground font-medium">{symbol || "this symbol"}</span> when price goes
            </p>
            <div className="mb-2 flex gap-1">
              {(["above", "below"] as const).map((d) => (
                <button key={d} type="button"
                        aria-pressed={direction === d}
                        onClick={() => setDirection(d)}
                        className={`flex-1 rounded px-2 py-1 text-[11px] ${
                          direction === d
                            ? "bg-[#2563eb] text-white"
                            : "bg-[color:var(--raise-3)] text-muted-foreground hover:text-foreground"}`}>
                  {d}
                </button>
              ))}
            </div>
            <input
              type="number" step="0.01" inputMode="decimal"
              value={price} onChange={(e) => setPrice(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") addAlert() }}
              aria-label="Alert price"
              placeholder="Price"
              className="mb-2 w-full rounded border border-[color:var(--hairline-mid)] bg-transparent
                         px-2 py-1 text-[12px] text-foreground focus:outline-none focus:border-[#38bdf8]"
            />
            <div className="flex gap-1">
              <button type="button" onClick={addAlert}
                      className="flex-1 rounded bg-[#2563eb] px-2 py-1 text-[11px] text-white hover:bg-[#1d4ed8]">
                <Plus className="mr-0.5 inline h-3 w-3" aria-hidden /> Add
              </button>
              <button type="button" onClick={() => setAlertOpen(false)}
                      className="rounded border border-[color:var(--hairline-mid)] px-2 py-1 text-[11px]
                                 text-muted-foreground hover:text-foreground">
                Cancel
              </button>
            </div>
            <p className="mt-2 text-[10px] text-muted-foreground/80">
              Marked on the chart and listed under Alerts. Checked against the
              bars on screen — nothing watches the market while this is closed.
            </p>
          </div>
        )}
      </span>

      {/* ── Replay ── */}
      <button type="button" className={BTN} onClick={() => setPage("replay")}
              title="Replay the market bar by bar">
        <Rewind className="h-3 w-3" aria-hidden /> Replay
      </button>

      <span className="mx-1 h-4 w-px bg-[color:var(--hairline-soft)]" aria-hidden />

      {/* ── Drawing undo / redo ── */}
      <button type="button" onClick={onUndo} disabled={!canUndo}
              aria-label="Undo drawing" title="Undo the last drawing"
              className={`${BTN} disabled:opacity-35 disabled:cursor-not-allowed`}>
        <Undo2 className="h-3 w-3" aria-hidden />
      </button>
      <button type="button" onClick={onRedo} disabled={!canRedo}
              aria-label="Redo drawing" title="Redo the drawing you just undid"
              className={`${BTN} disabled:opacity-35 disabled:cursor-not-allowed`}>
        <Redo2 className="h-3 w-3" aria-hidden />
      </button>

      {/* ── View controls, moved off Plotly's modebar ── */}
      <button type="button" onClick={onZoomIn} className={BTN}
              aria-label="Zoom in" title="Zoom in">
        <ZoomIn className="h-3 w-3" aria-hidden />
      </button>
      <button type="button" onClick={onZoomOut} className={BTN}
              aria-label="Zoom out" title="Zoom out">
        <ZoomOut className="h-3 w-3" aria-hidden />
      </button>
      <button type="button" onClick={onResetView} className={BTN}
              aria-label="Reset the view" title="Reset the view to the default window">
        <Home className="h-3 w-3" aria-hidden />
      </button>

      {/* ── Snapshot. The ONLY camera on the chart now. ── */}
      <button type="button" onClick={onSnapshot} className={BTN}
              aria-label="Download chart as PNG" title="Download this chart as a PNG">
        <Camera className="h-3 w-3" aria-hidden />
      </button>

      {actions && (
        <>
          <span className="mx-1 h-4 w-px bg-[color:var(--hairline-soft)]" aria-hidden />
          {actions}
        </>
      )}

      {/* The price scale's currency.
          A LABEL, not the reference's dropdown. Every contract this platform
          trades -- ES, NQ, MES, YM, RTY, CL, GC and the rest -- is quoted in
          USD, and there is no FX rate anywhere in the app to convert a price
          with. A dropdown would offer a choice that could not be honoured;
          the label states the fact the axis is already in. */}
      <span className="ml-auto rounded border border-[color:var(--hairline-soft)] px-1.5 py-0.5
                       text-muted-foreground"
            title="Prices are quoted in US dollars. Every contract this platform trades is USD-denominated.">
        USD
      </span>
    </div>
  )
}
