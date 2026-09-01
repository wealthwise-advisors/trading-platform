/**
 * The chart setup table, shown as its own column on Backtest and Market Grid.
 *
 * It is a reference, not a control. Picking a timeframe already moves the date
 * range to its row; this shows what the whole table says, so the number in the
 * day stepper is never a surprise and the reader can see why 1h reaches back
 * twenty-five days when 1m reaches back two.
 *
 * Rows the specification did not cover are marked. A number someone chose and
 * a number we interpolated should not look identical to whoever reads this
 * next -- see chartSetup.ts.
 */
import { CHART_SETUP, CHART_SETUP_ORDER, isSpecified } from "@/lib/chartSetup"

interface Props {
  /** Timeframe(s) currently selected. Backtest passes one, Market Grid many. */
  active: readonly string[]
}

export function ChartSetupPanel({ active }: Props) {
  return (
    <div>
      <div
        className="grid gap-x-2 gap-y-1"
        style={{ gridTemplateColumns: "auto 1fr auto" }}
        role="table"
        aria-label="Days of history charted per timeframe"
      >
        {CHART_SETUP_ORDER.map((tf) => {
          const on = active.includes(tf)
          const days = CHART_SETUP[tf]
          const derived = !isSpecified(tf)
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
              {/* A leader rule, so a row reads across even when the two
                  columns are far apart. Decorative, hence aria-hidden. */}
              <span
                aria-hidden
                className="self-center h-px bg-white/8"
              />
              <span role="cell" className="font-mono text-[11px] tabular-nums">
                {days}D
                {derived && (
                  <span
                    className="ml-1 text-muted-foreground/50"
                    title="Interpolated from the intervals either side — not a specified value"
                  >
                    *
                  </span>
                )}
              </span>
            </div>
          )
        })}
      </div>

      <p className="mt-2 text-[10px] leading-snug text-muted-foreground/60">
        Selecting a timeframe moves the range to its row. The dates and the day
        stepper stay yours after that.
        <br />
        <span aria-hidden>*</span> interpolated, not specified
      </p>
    </div>
  )
}
