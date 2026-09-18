/**
 * What the chart is showing, and where it currently stands.
 *
 * Three things the reference has above and inside the price panel, and this
 * app did not have at all:
 *
 *   1. the instrument line -- symbol, description, interval, exchange
 *   2. the OHLC quote for the last bar, with its change
 *   3. the indicator readout -- EMA 9, EMA 21, VWAP and the band pair
 *
 * NOTHING HERE IS FABRICATED. Every number is the last real point of the
 * series the chart draws, and a series with no reading prints an em dash
 * rather than a zero. The band row is labelled "VWAP Bands +/-2sigma" and NOT
 * "BB 20 2" as the reference does, because these are not Bollinger bands:
 * api/serializers.py computes them as the session VWAP plus and minus two
 * standard deviations, which is a different calculation with a different
 * meaning. Copying the reference's label onto them would be the one kind of
 * mismatch that actually misleads a trader.
 *
 * Plain DOM, not Plotly annotations: a Plotly layout cannot reflow, cannot be
 * themed by the stylesheet, and cannot hold a collapse control.
 */

import { useState } from "react"
import { ChevronDown, ChevronUp, Crosshair } from "lucide-react"
import type { IndicatorSeries, OHLCVRecord } from "@/lib/types"

/** The last non-null reading of a series, or null when it has none. */
function lastOf(xs?: (number | null)[]): number | null {
  if (!xs) return null
  for (let i = xs.length - 1; i >= 0; i--) if (xs[i] != null) return xs[i] as number
  return null
}

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
  indicators: IndicatorSeries
}

export function ChartHeader({
  symbol, description, exchange, interval, bars,
}: Omit<ChartHeaderProps, "indicators">) {
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
      {/* The instrument line. The description and the exchange are omitted
          rather than guessed when the catalogue has not got them -- a symbol
          with an invented venue beside it is worse than a symbol alone. */}
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-[13px]">
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


/**
 * The indicator readout, overlaying the top-left of the price panel.
 *
 * Positioned rather than stacked: the reference draws it INSIDE the plot, and
 * in the flow above it this block cost the chart roughly 85px of height --
 * which on a 927px window is the difference between three readable oscillator
 * rows and three squashed ones. pointer-events-none on the wrapper so it
 * cannot swallow a drag on the chart beneath; the button re-enables them for
 * itself.
 */
export function IndicatorReadout({
  indicators, topOffset = 40, showBollinger = false,
}: {
  indicators: IndicatorSeries
  /** Whether the Bollinger row is drawn. It follows the chart's own toggle:
   *  a readout for a line that is not on the chart is a number with nothing
   *  to point at. */
  showBollinger?: boolean
  /** Pixels from the plot's top edge. The caller passes the Plotly top margin,
   *  because that band holds the range selector and the ZigZag swing headers
   *  and this block has to start below both. A fixed guess put it on top of
   *  them. */
  topOffset?: number
}) {
  const [open, setOpen] = useState(true)

  const rows: [string, string][] = [
    ["EMA 9", px(lastOf(indicators.ema9))],
    ["EMA 21", px(lastOf(indicators.ema21))],
    ["VWAP", px(lastOf(indicators.vwap))],
    // Two numbers on one row: the band pair is one indicator, not two.
    ["VWAP Bands ±2σ",
      `${px(lastOf(indicators.vwap_upper))}  ${px(lastOf(indicators.vwap_lower))}`],
  ]

  // "BB 20 2" -- the name the reference uses, now on the thing it actually
  // names: a 20-bar simple moving average with 2-sigma envelopes, computed
  // server-side. Basis, upper, lower, in that order.
  if (showBollinger) {
    rows.push(["BB 20 2",
      `${px(lastOf(indicators.bb_middle))}  ${px(lastOf(indicators.bb_upper))}  ${px(lastOf(indicators.bb_lower))}`])
  }

  return (
    <div className="pointer-events-none absolute left-2 z-10" style={{ top: topOffset }}>
      <div className="pointer-events-auto inline-flex flex-col items-start gap-0.5
                      rounded-md bg-[color:var(--chart-readout-scrim)] px-1.5 py-0.5
                      backdrop-blur-[2px]">
        {open && (
          <dl className="grid grid-cols-[auto_auto] gap-x-4 text-[11px] tabular-nums">
            {rows.map(([name, value]) => (
              <div key={name} className="contents">
                <dt className="text-muted-foreground">{name}</dt>
                <dd className="text-right text-foreground">{value}</dd>
              </div>
            ))}
          </dl>
        )}
        {/* BELOW the values, as the reference draws it -- the chevron is the
            handle you pull the block closed with, not a heading over it. */}
        <button type="button"
                onClick={() => setOpen((v) => !v)}
                aria-expanded={open}
                aria-label={open ? "Hide indicator values" : "Show indicator values"}
                className="rounded border border-[color:var(--hairline-soft)]
                           bg-[color:var(--raise-2)] px-1 text-muted-foreground
                           hover:text-foreground">
          {open ? <ChevronUp className="h-3 w-3" aria-hidden />
                : <ChevronDown className="h-3 w-3" aria-hidden />}
        </button>
      </div>
    </div>
  )
}
