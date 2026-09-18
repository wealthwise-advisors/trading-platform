/**
 * What the chart is showing, and where it currently stands.
 *
 * Three things the reference has above and inside the price panel, and this
 * app did not have at all:
 *
 *   1. the instrument line -- symbol, description, interval, exchange
 *   2. the OHLC quote for the last bar, with its change
 *
 * The indicator readout used to be a third item here, painted over the plot's
 * top-left corner. It is a dropdown now -- ChartLegendMenu, on this same row
 * -- because a reading you glance at occasionally had been given permanent
 * space in front of the candles it described.
 *
 * NOTHING HERE IS FABRICATED. Every number is the last real point of the
 * series the chart draws, and a series with no reading prints an em dash
 * rather than a zero.
 *
 * Plain DOM, not Plotly annotations: a Plotly layout cannot reflow, cannot be
 * themed by the stylesheet, and cannot hold a collapse control.
 */

import { Crosshair } from "lucide-react"
import type { OHLCVRecord } from "@/lib/types"

/** "5m" -> "5"; "1h", "1d", "1w" unchanged. */
function intervalLabel(interval: string): string {
  const m = /^(\d+)m$/.exec(interval.trim())
  return m ? m[1] : interval
}

const px = (n: number | null | undefined, digits = 2) =>
  n == null ? "—" : n.toLocaleString(undefined, {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  })

interface ChartHeaderProps {
  symbol: string
  /** The instrument's full name, when the catalogue knows it. */
  description?: string | null
  /** Venue, when the catalogue knows it. */
  exchange?: string | null
  interval: string
  bars: OHLCVRecord[]
  /**
   * The chart's own controls -- Indicators, Save, full screen -- rendered at
   * the right end of the instrument line.
   *
   * They arrive as a node rather than being built here because they are
   * driven by CandlestickChart's state (which studies are on, which menu is
   * open, which element goes full screen). Lifting that state up to place
   * three buttons would be a large change for a small one; passing the
   * already-built node down puts them on this row without either component
   * learning anything about the other.
   */
  actions?: React.ReactNode
}

export function ChartHeader({
  symbol, description, exchange, interval, bars, actions,
}: ChartHeaderProps) {
  const last = bars.length ? bars[bars.length - 1] : null
  const prev = bars.length > 1 ? bars[bars.length - 2] : null
  // Change against the PREVIOUS BAR'S CLOSE, which is what a quote line means
  // by "change". Against this bar's own open it would be the candle body, a
  // different number wearing the same label.
  const change = last && prev ? last.c - prev.c : null
  const changePct = change != null && prev && prev.c !== 0 ? (change / prev.c) * 100 : null
  const dir = change == null ? "flat" : change > 0 ? "up" : change < 0 ? "down" : "flat"
  const changeColor =
    dir === "up" ? "var(--gain)" : dir === "down" ? "var(--loss)" : "var(--muted-foreground)"

  return (
    <div className="shrink-0 px-1 pb-1">
      {/* The instrument line, with the chart's controls at its right end.
          ONE ROW: the controls used to sit on a line of their own below the
          study checkboxes, which cost the plot a whole row of height and put
          three buttons a long way from the chart they act on.
          The description and the exchange are omitted rather than guessed when
          the catalogue has not got them -- a symbol with an invented venue
          beside it is worse than a symbol alone. */}
      <div className="flex items-start justify-between gap-3">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-[13px] min-w-0">
        <Crosshair className="h-3.5 w-3.5 shrink-0 self-center text-muted-foreground" aria-hidden />
        <span className="font-semibold tracking-tight text-foreground">{symbol}</span>
        {description && (
          <>
            <span className="text-muted-foreground/75">·</span>
            <span className="text-muted-foreground">{description}</span>
          </>
        )}
        <span className="text-muted-foreground/75">·</span>
        {/* "5", not "5m" -- the reference writes an intraday interval as a
            bare number of minutes, as trading terminals do. Anything that is
            not plain minutes (1h, 1d, 1w) keeps its unit, because there the
            unit is the whole meaning. */}
        <span className="text-muted-foreground">{intervalLabel(interval)}</span>
        {exchange && (
          <>
            <span className="text-muted-foreground/75">·</span>
            <span className="text-muted-foreground">{exchange}</span>
          </>
        )}
      </div>
        {actions && (
          <div className="shrink-0 flex items-center gap-1.5 text-xs">{actions}</div>
        )}
      </div>

      {/* The quote line. tabular-nums so the figures do not jitter as the
          last bar updates. */}
      <div className="mt-0.5 flex flex-wrap items-baseline gap-x-2.5 text-[12px] tabular-nums">
        {last ? (
          <>
            <Quote label="O" value={px(last.o)} />
            <Quote label="H" value={px(last.h)} />
            <Quote label="L" value={px(last.l)} />
            <Quote label="C" value={px(last.c)} />
            <span style={{ color: changeColor }}>
              {change == null ? "—" : `${change > 0 ? "+" : ""}${px(change)}`}
              {changePct != null && ` (${changePct > 0 ? "+" : ""}${changePct.toFixed(2)}%)`}
            </span>
          </>
        ) : (
          <span className="text-muted-foreground">No bars loaded</span>
        )}
      </div>

    </div>
  )
}

function Quote({ label, value }: { label: string; value: string }) {
  return (
    <span>
      <span className="text-muted-foreground">{label}</span>{" "}
      <span className="text-foreground">{value}</span>
    </span>
  )
}
