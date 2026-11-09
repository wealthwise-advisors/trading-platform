// One vertical line through every chart row and a value box in each of them,
// wherever the mouse is -- what thinkorswim does and Plotly's hover cannot.
//
// Its own component with its own state: following the mouse must not re-render
// CandlestickChart and redraw the plot on every pixel. pointer-events are off
// throughout, so panning, zooming and marker hovers go straight to Plotly.

import { useEffect, useRef, useState, type RefObject } from "react"
import { nearestBarIndex, readoutLines, type ReadoutLine, type ReadoutRow } from "@/lib/chartReadout"
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

const BOX_WIDTH = 214
const LINE_HEIGHT = 15
const BOX_CHROME = 8
const TIME_LABELS = 22

interface Reading {
  x: number
  top: number
  height: number
  flip: boolean
  boxes: { axis: string; title: string; top: number; lines: ReadoutLine[] }[]
}

function layoutKey(axis: string) {
  return axis === "y" ? "yaxis" : `yaxis${axis.slice(1)}`
}

export function ChartCrosshair({ hostRef, bars, rows, volumeAxis, interval }: {
  hostRef: RefObject<HTMLDivElement | null>
  bars: OHLCVRecord[]
  rows: ReadoutRow[]
  volumeAxis?: string
  interval?: string
}) {
  const [reading, setReading] = useState<Reading | null>(null)
  // The latest props without re-binding the mouse listeners on each render.
  const latest = useRef({ bars, rows, volumeAxis })
  useEffect(() => { latest.current = { bars, rows, volumeAxis } })
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
      const { bars, rows, volumeAxis } = latest.current
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

      const boxes = rows.map((row, r) => {
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
        return { axis: row.axis, title: row.title, top: boxTop, lines }
      })
      setReading({ x, top, height: bottom - top, flip, boxes })
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
               top: box.top, width: BOX_WIDTH,
               left: reading.flip ? reading.x + 8 : reading.x - BOX_WIDTH - 8,
               padding: BOX_CHROME / 2, fontSize: 12, lineHeight: `${LINE_HEIGHT}px`,
               background: "rgba(10,10,16,0.96)", border: "1px solid rgba(163,163,194,0.35)", color: "#e5e7eb",
             }}>
          <div className="font-semibold whitespace-nowrap overflow-hidden">{box.title}</div>
          {box.lines.map((l) => (
            <div key={l.label} className="flex justify-between gap-2 whitespace-nowrap" style={{ color: l.color }}>
              <span className="overflow-hidden">{l.label}</span>
              <span>{l.value}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
