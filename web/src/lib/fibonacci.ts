/**
 * The Fibonacci retracement drawing: a dragged line becomes one horizontal
 * level per ratio, as thinkorswim's FibonacciRetracements tool draws them.
 *
 * Drag from the swing's start to its end. 0% sits at the END of the drag and
 * 100% at its start, so a drag from a low up to a high reads 61.8% as the
 * level a pullback from that high would reach.
 *
 * The levels share one `name`, so that undo removes the whole drawing at once
 * rather than one line at a time.
 */

export const FIB_RATIOS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1] as const

const FIB_COLORS: Record<number, string> = {
  0: "#9ca3af", 0.236: "#f472b6", 0.382: "#fb923c", 0.5: "#facc15",
  0.618: "#4ade80", 0.786: "#38bdf8", 1: "#9ca3af",
}

export const FIB_PREFIX = "fib-"

export interface FibLevel {
  ratio: number
  price: number
}

export function fibLevels(start: number, end: number): FibLevel[] {
  return FIB_RATIOS.map((ratio) => ({ ratio, price: end + (start - end) * ratio }))
}

export function fibLabel(level: FibLevel): string {
  const pct = (level.ratio * 100).toFixed(1).replace(/\.0$/, "")
  return `${pct}%  ${level.price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

interface LineLike {
  x0?: unknown
  x1?: unknown
  y0?: unknown
  y1?: unknown
}

/**
 * The level lines for a dragged line, from the earlier of its two times to
 * `extendTo` (the last bar) when that is later, so the levels reach the price
 * that is still to come. Null for anything that is not a usable drag.
 */
export function fibShapes(drag: LineLike, id: string | number, extendTo?: string): Record<string, unknown>[] | null {
  const y0 = Number(drag.y0), y1 = Number(drag.y1)
  if (!Number.isFinite(y0) || !Number.isFinite(y1) || y0 === y1) return null
  const xs = [String(drag.x0), String(drag.x1)].sort()
  const right = extendTo && extendTo > xs[1] ? extendTo : xs[1]
  return fibLevels(y0, y1).map((lv) => ({
    type: "line", name: `${FIB_PREFIX}${id}`,
    xref: "x", x0: xs[0], x1: right, yref: "y", y0: lv.price, y1: lv.price,
    line: { color: FIB_COLORS[lv.ratio], width: 1 },
    label: { text: fibLabel(lv), textposition: "start", font: { color: FIB_COLORS[lv.ratio], size: 10 } },
    editable: true,
  }))
}

/**
 * How many shapes at the end of the list make up the last drawing: every
 * trailing shape sharing its name, or just the one.
 */
export function lastDrawingSize(shapes: ReadonlyArray<{ name?: unknown }>): number {
  if (!shapes.length) return 0
  const name = shapes[shapes.length - 1].name
  if (typeof name !== "string" || !name) return 1
  let n = 0
  for (let i = shapes.length - 1; i >= 0 && shapes[i].name === name; i--) n++
  return n
}
