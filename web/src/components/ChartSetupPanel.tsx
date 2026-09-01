/**
 * The chart setup table, shown as its own column on Backtest and Market Grid.
 *
 * A reference, not a control. Picking a timeframe already loads its row; this
 * shows the whole table so the number in the day stepper is never a surprise
 * and the reader can see why 1h reaches back twenty-five days when 1m reaches
 * back two.
 *
 * A timeframe with no specified entry shows a dash, not a number. Selecting it
 * leaves the date range alone, and the dash is what says so -- a filled-in
 * value there would look exactly like the eight that were specified while
 * being something we made up. See chartSetup.ts.
 *
 * This panel is separate from the Volume Profile settings and touches none of
 * them; Volume Profile keeps its own column.
 */
import { ALL_CHART_TIMEFRAMES, daysFor, isSpecified } from "@/lib/chartSetup"

interface Props {
  /** Timeframe(s) currently selected. Backtest passes one, Market Grid many. */
  active: readonly string[]
}

export function ChartSetupPanel({ active }: Props) {
  const anyUnset = ALL_CHART_TIMEFRAMES.some((tf) => !isSpecified(tf))

  return (
    <div>
      <div
        className="grid gap-x-2 gap-y-1"
        style={{ gridTemplateColumns: "auto 1fr auto" }}
        role="table"
        aria-label="Days of history loaded per timeframe"
      >
        {ALL_CHART_TIMEFRAMES.map((tf) => {
          const on = active.includes(tf)
          const days = daysFor(tf)
          return (
            <div
              key={tf}
              role="row"
              className={
                "contents " +
                (on ? "[&>*]:text-foreground" : "[&>*]:text-muted-foreground/70")
              }
            >
              <span
                role="cell"
                className={
                  "font-mono text-[11px] tabular-nums " +
                  (on ? "font-semibold text-primary" : "")
                }
              >
                {tf}
              </span>
              {/* A leader rule, so a row reads across when the two columns are
                  far apart. Decorative, hence aria-hidden. */}
              <span aria-hidden className="self-center h-px bg-white/8" />
              {days == null ? (
                <span
                  role="cell"
                  className="font-mono text-[11px] tabular-nums text-muted-foreground/40"
                  title="No day count specified for this timeframe — selecting it leaves the date range unchanged"
                >
                  —
                </span>
              ) : (
                <span role="cell" className="font-mono text-[11px] tabular-nums">
                  {days}D
                </span>
              )}
            </div>
          )
        })}
      </div>

      <p className="mt-2 text-[10px] leading-snug text-muted-foreground/60">
        Selecting a timeframe loads its row. The dates and the day stepper stay
        yours after that.
        {anyUnset && (
          <>
            <br />
            <span aria-hidden>—</span> no value specified; the range is left
            unchanged
          </>
        )}
      </p>
    </div>
  )
}
