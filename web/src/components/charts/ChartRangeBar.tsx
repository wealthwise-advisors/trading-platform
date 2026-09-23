/**
 * The strip along the bottom of the chart: range buttons, a date jump, the
 * clock, and the price-scale modes.
 *
 * WHY THE RANGE BUTTONS MOVED HERE. Plotly's own rangeselector was already on
 * this chart, floating above the price row, with six buttons. The reference
 * puts nine along the bottom. Rather than leave two range controls on one
 * chart -- which would drift apart the moment one of them set a window the
 * other did not know about -- the Plotly selector is gone and this bar is the
 * single control. It drives the same `visibleRange` state the user's own
 * zoom and pan write, so a button press and a mouse drag are the same kind of
 * action to everything downstream.
 *
 * WHAT "%" IS NOT DOING HERE. The reference has a percent mode beside log and
 * auto. A real percent scale re-bases every series to its first visible bar
 * and redraws the candles as relative moves -- it changes the DATA, not the
 * axis, and it has to agree with the volume profile, the VWAP bands and the
 * swing overlay about what a price means. That is a genuine feature, not a
 * toggle, so it is absent rather than present-and-lying. Log and Auto are
 * both real: log switches the price axis type, Auto returns the window and
 * the scale to the chart's own defaults.
 */
import { useEffect, useState } from "react"
import { CalendarDays, Clock } from "lucide-react"

/** Range presets, in the reference's order. `days: null` means "everything". */
const RANGES: Array<{ id: string; label: string; days: number | null }> = [
  { id: "1D", label: "1D", days: 1 },
  { id: "5D", label: "5D", days: 5 },
  { id: "1M", label: "1M", days: 30 },
  { id: "3M", label: "3M", days: 90 },
  { id: "6M", label: "6M", days: 180 },
  { id: "YTD", label: "YTD", days: -1 },      // handled specially: Jan 1 of the last bar's year
  { id: "1Y", label: "1Y", days: 365 },
  { id: "5Y", label: "5Y", days: 365 * 5 },
  { id: "All", label: "All", days: null },
]

const DAY_MS = 86_400_000

export function ChartRangeBar({
  firstBarMs, lastBarMs, activeRange, logScale,
  onRange, onToggleLog, onAuto,
}: {
  firstBarMs: number | null
  lastBarMs: number | null
  activeRange: string | null
  logScale: boolean
  onRange: (id: string, start: number, end: number) => void
  onToggleLog: () => void
  onAuto: () => void
}) {
  // A clock, ticking, with the browser's UTC offset spelled out the way the
  // reference does it. It is the VIEWER's clock, not the exchange's -- the
  // session-hours note in the sidebar already says the run is anchored to
  // exchange time, and two different clocks labelled the same way would be
  // worse than one labelled honestly.
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(id)
  }, [])

  const offsetLabel = (() => {
    // getTimezoneOffset is minutes BEHIND UTC, so the sign is inverted.
    const mins = -now.getTimezoneOffset()
    const sign = mins < 0 ? "-" : "+"
    const h = Math.floor(Math.abs(mins) / 60)
    const m = Math.abs(mins) % 60
    return `UTC${sign}${h}${m ? `:${String(m).padStart(2, "0")}` : ""}`
  })()

  const pick = (r: typeof RANGES[number]) => {
    if (firstBarMs == null || lastBarMs == null) return
    if (r.days === null) { onRange(r.id, firstBarMs, lastBarMs); return }
    if (r.id === "YTD") {
      const end = new Date(lastBarMs)
      const jan1 = new Date(end.getFullYear(), 0, 1).getTime()
      onRange(r.id, Math.max(firstBarMs, jan1), lastBarMs)
      return
    }
    onRange(r.id, Math.max(firstBarMs, lastBarMs - r.days * DAY_MS), lastBarMs)
  }

  /** Jump to a date: show that day, clamped to the data that exists. */
  const jumpTo = (value: string) => {
    if (!value || firstBarMs == null || lastBarMs == null) return
    const [y, m, d] = value.split("-").map(Number)
    if (!y || !m || !d) return
    const start = new Date(y, m - 1, d).getTime()
    onRange("", Math.max(firstBarMs, start), Math.min(lastBarMs, start + DAY_MS))
  }

  const dateValue = lastBarMs != null ? new Date(lastBarMs).toISOString().slice(0, 10) : ""
  const hasBars = firstBarMs != null && lastBarMs != null

  return (
    <div className="flex flex-wrap items-center gap-1 border-t border-[color:var(--hairline-soft)]
                    px-1.5 py-1 text-[11px]">
      <div role="group" aria-label="Visible range" className="flex items-center gap-0.5">
        {RANGES.map((r) => (
          <button
            key={r.id}
            type="button"
            disabled={!hasBars}
            aria-pressed={activeRange === r.id}
            onClick={() => pick(r)}
            title={`Show the last ${r.label}`}
            className={`rounded px-1.5 py-0.5 transition-colors disabled:opacity-35 ${
              activeRange === r.id
                ? "bg-[color:var(--raise-4)] text-[#38bdf8] font-medium"
                : "text-muted-foreground hover:bg-[color:var(--raise-3)] hover:text-foreground"
            }`}
          >
            {r.label}
          </button>
        ))}
      </div>

      {/* Jump to a date. A native date input rather than a drawn calendar:
          it is keyboard-accessible and localised for free. */}
      <label className="relative ml-0.5 inline-flex items-center"
             title="Jump to a date">
        <CalendarDays className="pointer-events-none h-3.5 w-3.5 text-muted-foreground" aria-hidden />
        <input
          type="date"
          defaultValue={dateValue}
          disabled={!hasBars}
          onChange={(e) => jumpTo(e.target.value)}
          aria-label="Jump to a date"
          className="w-[1.4rem] cursor-pointer bg-transparent text-transparent outline-none
                     [color-scheme:dark] disabled:opacity-35"
        />
      </label>

      <span className="ml-auto flex items-center gap-1 text-muted-foreground tabular-nums">
        <Clock className="h-3 w-3" aria-hidden />
        {now.toLocaleTimeString(undefined, { hour12: false })}
        <span className="text-muted-foreground/70">({offsetLabel})</span>
      </span>

      <span className="mx-1 h-4 w-px bg-[color:var(--hairline-soft)]" aria-hidden />

      {/* Percent is deliberately not a button -- see the note at the top. */}
      <button type="button" onClick={onToggleLog} aria-pressed={logScale}
              title="Logarithmic price scale"
              className={`rounded px-1.5 py-0.5 ${
                logScale
                  ? "bg-[color:var(--raise-4)] text-[#38bdf8] font-medium"
                  : "text-muted-foreground hover:bg-[color:var(--raise-3)] hover:text-foreground"}`}>
        log
      </button>
      <button type="button" onClick={onAuto}
              title="Reset the window and the price scale to their defaults"
              className="rounded px-1.5 py-0.5 text-muted-foreground
                         hover:bg-[color:var(--raise-3)] hover:text-foreground">
        auto
      </button>
    </div>
  )
}
