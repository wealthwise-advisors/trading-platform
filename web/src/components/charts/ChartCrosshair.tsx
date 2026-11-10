// One vertical line through every chart row and a value box in each of them,
// wherever the mouse is -- what thinkorswim does and Plotly's hover cannot.
//
// Its own component with its own state: following the mouse must not re-render
// CandlestickChart and redraw the plot on every pixel. pointer-events are off
// throughout, so panning, zooming and marker hovers go straight to Plotly.

import { useEffect, useRef, useState, type RefObject } from "react"
import { nearestBarIndex, readoutLines, type ReadoutLine, type ReadoutRow } from "@/lib/chartReadout"
import { strengthLines, swingAt, swingStrength, type SwingSpan } from "@/lib/swingStrength"
import type { OHLCVRecord } from "@/lib/types"

interface PlotAxis {
  _offset: number
  _length: number
  d2c: (v: string) => number
  c2p: (v: number) => number
  p2c: (v: number) => number
  p2d: (v: number) => number
}
type PlotLayout = Record<string, PlotAxis | undefined>

const BOX_WIDTH = 190
/** Wide enough for "13 green candles  +8,087 (51%)" on one line. */
const SWING_BOX_WIDTH = 268
/** Section headings in the swing box. */
const HEADING_PURPLE = "#c4b5fd"
const LINE_HEIGHT = 13
const BOX_CHROME = 8
const TIME_LABELS = 22

interface Reading {
  x: number
  top: number
  height: number
  boxes: { axis: string; title: string; top: number; lines: ReadoutLine[]; onRight: boolean; titleColor?: string;
           width?: number }[]
}

function layoutKey(axis: string) {
  return axis === "y" ? "yaxis" : `yaxis${axis.slice(1)}`
}

export function ChartCrosshair({ hostRef, bars, rows, volumeAxis, interval, swingSpans = [] }: {
  hostRef: RefObject<HTMLDivElement | null>
  bars: OHLCVRecord[]
  rows: ReadoutRow[]
  volumeAxis?: string
  interval?: string
  /** The swings on the chart; the one under the cursor gets a buyers-vs-sellers box. */
  swingSpans?: SwingSpan[]
}) {
  const [reading, setReading] = useState<Reading | null>(null)
  // The latest props without re-binding the mouse listeners on each render.
  const latest = useRef({ bars, rows, volumeAxis, swingSpans })
  useEffect(() => { latest.current = { bars, rows, volumeAxis, swingSpans } })
  // A swing's box lines, worked out once per swing per dataset, not per pixel.
  const swingCache = useRef<{ bars: OHLCVRecord[] | null; byKey: Map<string, ReadoutLine[]> }>({ bars: null, byKey: new Map() })
  // Bar times in the axis's own units, worked out once per dataset.
  const times = useRef<{ bars: OHLCVRecord[] | null; ms: number[] }>({ bars: null, ms: [] })

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const clear = () => setReading(null)

    const move = (e: MouseEvent) => {
      // A held button is a pan or a zoom box; the boxes would ride along.
      if (e.buttons) return clear()
      const gd = host.querySelector(".js-plotly-plot") as unknown as { _fullLayout?: PlotLayout } | null
      const full = gd?._fullLayout
      const xa = full?.xaxis
      const { bars, rows, volumeAxis, swingSpans } = latest.current
      if (!full || !xa || !bars.length || !rows.length) return clear()

      const rect = host.getBoundingClientRect()
      const px = e.clientX - rect.left
      const py = e.clientY - rect.top
      const axes = rows.map((r) => full[layoutKey(r.axis)])
      if (axes.some((a) => !a)) return clear()
      const first = axes[0]!
      const last = axes[axes.length - 1]!
      const top = first._offset
      const bottom = last._offset + last._length
      if (px < xa._offset || px > xa._offset + xa._length || py < top || py > bottom) return clear()

      if (times.current.bars !== bars) times.current = { bars, ms: bars.map((b) => xa.d2c(b.t)) }
      const i = nearestBarIndex(times.current.ms, xa.p2c(px - xa._offset))
      const bar = bars[i]
      const x = xa.c2p(times.current.ms[i]) + xa._offset
      const flip = x - xa._offset < BOX_WIDTH + 12

      const boxes: Reading["boxes"] = rows.map((row, r) => {
        const lines = readoutLines(row, bar, i, volumeAxis)
        // Under the cursor's height on price, as the reference has it.
        if (r === 0 && py <= first._offset + first._length) {
          lines.splice(1, 0, { label: "Y", value: first.p2d(py - first._offset).toFixed(2) })
        }
        const axis = axes[r]!
        const h = (lines.length + 1) * LINE_HEIGHT + BOX_CHROME
        // Kept inside the chart: a row can be shorter than its box. The bottom
        // row may cover the time labels, so that it does not cover the row above.
        const boxTop = Math.max(top, Math.min(axis._offset + 1, bottom + TIME_LABELS - h))
        // A price box taller than its row goes on the other side of the line,
        // so that it does not cover the indicator rows' boxes.
        const fits = h <= axis._length
        const roomOnOtherSide = flip ? x - xa._offset > BOX_WIDTH + 12 : xa._offset + xa._length - x > BOX_WIDTH + 12
        const onRight = r === 0 && !fits && roomOnOtherSide ? !flip : flip
        return { axis: row.axis, title: row.title, top: boxTop, lines, onRight }
      })
      // The swing under the cursor: who pushed harder over its 10 Leg Dev and
      // 3 Leg Dev stretches. Top of the price row, on the side the price box
      // is not on, so the two never cover each other.
      const sw = swingAt(swingSpans, bar.t)
      if (sw) {
        if (swingCache.current.bars !== bars) swingCache.current = { bars, byKey: new Map() }
        const key = `${sw.swing}|${sw.tenLeg.from}|${sw.tenLeg.to}|${sw.threeLeg?.to ?? ""}`
        let lines = swingCache.current.byKey.get(key)
        if (!lines) {
          // 10 Leg, a dotted rule, then 3 Leg.
          lines = [
            ...strengthLines(`10 Leg Dev (${sw.tenLeg.label})`, swingStrength(bars, sw.tenLeg.from, sw.tenLeg.to),
                             { from: sw.tenLeg.fromPrice, to: sw.tenLeg.toPrice }),
            ...(sw.threeLeg
              ? [{ label: "", value: "", kind: "divider" as const },
                 ...strengthLines(`3 Leg Dev (${sw.threeLeg.label})`, swingStrength(bars, sw.threeLeg.from, sw.threeLeg.to),
                                  { from: sw.threeLeg.fromPrice, to: sw.threeLeg.toPrice })]
              : []),
          ]
          swingCache.current.byKey.set(key, lines)
        }
        const priceOnRight = boxes[0]?.onRight ?? flip
        boxes.push({ axis: "swing", title: `Swing ${sw.swing}`, top: first._offset + 1, lines, onRight: !priceOnRight,
                     titleColor: sw.color, width: SWING_BOX_WIDTH })
      }
      setReading({ x, top, height: bottom - top, boxes })
    }

    host.addEventListener("mousemove", move)
    host.addEventListener("mouseleave", clear)
    return () => {
      host.removeEventListener("mousemove", move)
      host.removeEventListener("mouseleave", clear)
    }
  }, [hostRef, interval])

  if (!reading) return null
  return (
    <div className="absolute inset-0 z-10 overflow-hidden" style={{ pointerEvents: "none" }} data-testid="chart-crosshair">
      <div className="absolute" data-testid="chart-crosshair-line"
           style={{ left: reading.x, top: reading.top, height: reading.height, width: 1, background: "#a3a3c2" }} />
      {reading.boxes.map((box) => (
        <div key={box.axis} data-testid={`chart-readout-${box.axis}`}
             className="absolute rounded-sm font-mono"
             style={{
               top: box.top, width: box.width ?? BOX_WIDTH,
               left: box.onRight ? reading.x + 8 : reading.x - (box.width ?? BOX_WIDTH) - 8,
               padding: BOX_CHROME / 2, fontSize: 11, lineHeight: `${LINE_HEIGHT}px`,
               background: "rgba(10,10,16,0.96)", border: "1px solid rgba(163,163,194,0.35)", color: "#e5e7eb",
             }}>
          {/* A titled box with sections (the swing box) gets a solid rule
              under its title; the study boxes keep their compact form. */}
          <div className="font-semibold truncate" title={box.title}
               style={box.titleColor ? { color: box.titleColor, borderBottom: "2px solid rgba(163,163,194,0.55)",
                                         paddingBottom: 3, marginBottom: 4 } : undefined}>
            {box.title}
          </div>
          {box.lines.map((l, n) =>
            l.kind === "divider" ? (
              <div key={n} style={{ borderTop: "1px dotted rgba(163,163,194,0.6)", margin: "5px 0" }} />
            ) : l.kind === "heading" ? (
              <div key={n} className="font-semibold whitespace-nowrap" style={{ color: HEADING_PURPLE }}>{l.label}</div>
            ) : (
              <div key={n} className="flex justify-between gap-2 whitespace-nowrap" style={{ color: l.color }}>
                <span className="overflow-hidden">{l.bullet ? <span style={{ color: "#9ca3af" }}>• </span> : null}{l.label}</span>
                <span style={l.valueColor ? { color: l.valueColor, fontWeight: 600 } : undefined}>{l.value}</span>
              </div>
            ))}
        </div>
      ))}
    </div>
  )
}
