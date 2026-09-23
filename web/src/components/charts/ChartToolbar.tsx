/**
 * The strip above the chart: interval, alert, replay, undo/redo, snapshot.
 *
 * WHAT EACH CONTROL ACTUALLY DOES, since a toolbar of decorative buttons is
 * the easiest thing in the world to build and the least useful:
 *
 *   intervals  Quick buttons plus the full IntervalPicker popup. Both write
 *              cfg.timeframe and move the start date, exactly as the Interval
 *              Picker in the Backtest panel does -- this is a THIRD control
 *              for one setting, so all of them always read the same value.
 *              Changing it needs a re-run to take effect, and the strip says
 *              so rather than pretending the chart redrew.
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
  Bell, Rewind, Undo2, Redo2, Camera, Plus,
} from "lucide-react"

import { IntervalPicker } from "@/components/IntervalPicker"
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
}: {
  symbol: string
  lastPrice: number | null
  canUndo: boolean
  canRedo: boolean
  onUndo: () => void
  onRedo: () => void
  onSnapshot: () => void
  onAlertsChanged: () => void
}) {
  const cfg = useConfigStore()
  const setPage = useConfigStore((s) => s.setPage)
  const [alertOpen, setAlertOpen] = useState(false)
  const [price, setPrice] = useState("")
  const [direction, setDirection] = useState<"above" | "below">("above")

  /** One place that changes the interval, so the quick buttons and the popup
   *  cannot drift apart or skip the start-date move. */
  const setInterval = (tf: string) => {
    cfg.setField("timeframe", tf)
    const start = startDateForTimeframe(cfg.endDate, tf, cfg.startDate)
    if (start) cfg.setField("startDate", start)
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
    <div className="flex flex-wrap items-center gap-1 px-1 py-1 text-[11px]
                    border-b border-[color:var(--hairline-soft)]">
      {/* ── Interval quick buttons ── */}
      <div role="group" aria-label="Bar interval" className="flex items-center gap-0.5">
        {QUICK.map((tf) => (
          <button
            key={tf}
            type="button"
            aria-pressed={cfg.timeframe === tf}
            onClick={() => setInterval(tf)}
            title={`${tf} bars — takes effect on the next run`}
            className={`rounded px-1.5 py-0.5 transition-colors ${
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
      <IntervalPicker value={cfg.timeframe} onChange={setInterval} />

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

      {/* ── Snapshot ── */}
      <button type="button" onClick={onSnapshot} className={BTN}
              aria-label="Download chart as PNG" title="Download this chart as a PNG">
        <Camera className="h-3 w-3" aria-hidden />
      </button>
    </div>
  )
}
