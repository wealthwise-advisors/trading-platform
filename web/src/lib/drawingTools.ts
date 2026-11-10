/**
 * The drawing tools that start as a dragged line and become something else:
 * a measurement, a price channel, an arrow. Fibonacci works the same way and
 * lives in ./fibonacci.
 */

import type { OHLCVRecord } from "./types"

interface LineLike {
  x0?: unknown
  x1?: unknown
  y0?: unknown
  y1?: unknown
}

const ACCENT = "#38bdf8"

function ends(line: LineLike) {
  const y0 = Number(line.y0), y1 = Number(line.y1)
  const x0 = String(line.x0), x1 = String(line.x1)
  return { x0, x1, y0, y1, ok: Number.isFinite(y0) && Number.isFinite(y1) && line.x0 != null && line.x1 != null }
}

/** "+12.50 (+0.17%) · 15 bars" for a drag from (x0, y0) to (x1, y1). */
export function measureText(line: LineLike, times: ReadonlyArray<string>): string {
  const { x0, x1, y0, y1 } = ends(line)
  const d = y1 - y0
  const sign = d >= 0 ? "+" : "-"
  const pct = y0 !== 0 ? (d / y0) * 100 : 0
  const [a, b] = [x0, x1].sort()
  const n = times.filter((t) => t > a && t <= b).length
  const pts = Math.abs(d).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return `${sign}${pts} (${sign}${Math.abs(pct).toFixed(2)}%) · ${n} bar${n === 1 ? "" : "s"}`
}

export function measureShape(line: LineLike, times: ReadonlyArray<string>): Record<string, unknown> | null {
  const e = ends(line)
  if (!e.ok) return null
  return {
    type: "line", xref: "x", yref: "y", x0: e.x0, x1: e.x1, y0: e.y0, y1: e.y1,
    line: { color: ACCENT, width: 1.5, dash: "dot" },
    label: { text: measureText(line, times), textposition: "end", font: { color: ACCENT, size: 11 } },
    editable: true,
  }
}

/**
 * A price channel: the dragged line and a parallel one through the bar
 * furthest from it, on whichever side the bars between the ends mostly lie.
 */
export function channelShapes(line: LineLike, bars: ReadonlyArray<OHLCVRecord>, id: string | number): Record<string, unknown>[] | null {
  const e = ends(line)
  if (!e.ok) return null
  const a = e.x0 <= e.x1 ? e : { x0: e.x1, x1: e.x0, y0: e.y1, y1: e.y0 }
  const t0 = Date.parse(a.x0), t1 = Date.parse(a.x1)
  const at = (t: string) => (t1 === t0 ? a.y0 : a.y0 + ((Date.parse(t) - t0) / (t1 - t0)) * (a.y1 - a.y0))
  let above = 0, below = 0
  for (const bar of bars) {
    if (bar.t < a.x0 || bar.t > a.x1) continue
    const y = at(bar.t)
    above = Math.max(above, bar.h - y)
    below = Math.min(below, bar.l - y)
  }
  const offset = above >= -below ? above : below
  const style = { type: "line", name: `channel-${id}`, xref: "x", yref: "y", editable: true }
  const main = { ...style, x0: a.x0, x1: a.x1, y0: a.y0, y1: a.y1, line: { color: ACCENT, width: 1.5 } }
  if (offset === 0) return [main]
  return [main, { ...style, x0: a.x0, x1: a.x1, y0: a.y0 + offset, y1: a.y1 + offset,
                  line: { color: ACCENT, width: 1.5, dash: "dash" } }]
}

/** An arrow from the start of the drag to its end, as a note with no text. */
export function arrowNote(line: LineLike): Record<string, unknown> | null {
  const e = ends(line)
  if (!e.ok) return null
  return {
    x: e.x1, y: e.y1, ax: e.x0, ay: e.y0, xref: "x", yref: "y", axref: "x", ayref: "y",
    text: "", showarrow: true, arrowhead: 2, arrowsize: 1.4, arrowwidth: 2, arrowcolor: ACCENT,
  }
}
