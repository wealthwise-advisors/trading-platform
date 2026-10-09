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
      {/* ONE LINE: badge, instrument, interval, venue, then the quote.
          The reference puts all of it on a single row, and it fits -- the
          quote was on a second line only because it grew there.

          No chevron beside the name, which the reference draws: here it would
          be a dropdown that opens nothing. The instrument is changed in the
          config panel, and a control that looks interactive and is not is
          worse than no control.

          The description and the exchange are omitted rather than guessed
          when the catalogue has not got them -- a symbol with an invented
          venue beside it is worse than a symbol alone. */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-x-2.5 gap-y-1 flex-wrap min-w-0">
          {/* The instrument's initials, as the reference marks it. Derived
              from the symbol, never a logo we do not have. */}
          <span className="chart-badge grid place-items-center rounded-full text-[11px]
                           font-bold tracking-tight"
                aria-hidden>
            {symbol.slice(0, 2).toUpperCase()}
          </span>
          <span className="text-[15px] font-semibold tracking-tight text-foreground">{symbol}</span>
          {description && (
            <span className="text-[13px] text-muted-foreground truncate">{description}</span>
          )}

          <span className="h-4 w-px bg-[color:var(--hairline-firm)]" aria-hidden />

          {/* "5", not "5m" -- the reference writes an intraday interval as a
              bare number of minutes, as trading terminals do. Anything that is
              not plain minutes (1h, 1d, 1w) keeps its unit, because there the
              unit is the whole meaning. */}
          {/* data-testid: the interval the chart is actually DRAWN at, which is
              the run's timeframe, not the one staged in the config panel. The
              e2e test for the toolbar pills reads it here rather than scraping
              body text -- the sidebar names the same instrument, so a text
              search found that first and compared the wrong thing. */}
          <span className="text-[13px] text-muted-foreground" data-testid="chart-interval">
            {intervalLabel(interval)}
          </span>
          {exchange && (
            <>
              <span className="text-muted-foreground/60" aria-hidden>&bull;</span>
              <span className="text-[13px] text-muted-foreground">{exchange}</span>
            </>
          )}

          {/* The quote, on the same line. tabular-nums so the figures do not
              jitter as the last bar updates. */}
          {last ? (
            <span className="flex items-baseline gap-x-3 flex-wrap text-[13px] tabular-nums ml-1">
              <Quote label="O" value={px(last.o)} />
              <Quote label="H" value={px(last.h)} />
              <Quote label="L" value={px(last.l)} />
              <Quote label="C" value={px(last.c)} />
              <span className="font-medium" style={{ color: changeColor }}>
                {change == null ? "—" : `${change > 0 ? "+" : ""}${px(change)}`}
                {changePct != null && ` (${changePct > 0 ? "+" : ""}${changePct.toFixed(2)}%)`}
              </span>
            </span>
          ) : (
            <span className="text-[13px] text-muted-foreground">No bars loaded</span>
          )}
        </div>

        {actions && (
          <div className="shrink-0 flex items-center gap-1.5 text-xs">{actions}</div>
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
