/**
 * The vertical drawing rail down the left edge of the chart, as the reference
 * has it.
 *
 * EVERY TOOL HERE IS REAL. The drawing tools map to a Plotly dragmode the
 * chart already supports natively -- `drawline`, `drawrect`, `drawcircle`,
 * `drawopenpath`, `zoom`, `pan` -- so selecting one changes what the mouse
 * does on the plot, and the shape you draw is a real Plotly shape that
 * persists and can be dragged afterwards. The other four (horizontal line,
 * note, undo, clear) are actions that add or remove a shape immediately.
 * Nothing on this rail is a painted-on button that does nothing when clicked.
 *
 * WHAT IS NOT HERE, AND WHY. The reference's rail also carries a magnet
 * (snap-to-OHLC), a lock and per-tool style pickers. Those are not Plotly
 * dragmodes -- they need a hit-test against the bar data and a shape-style
 * editor of our own, which is a bigger piece of work than the rail itself.
 * Rather than draw three dead buttons to make the column look longer, the
 * rail carries the tools that work. The Trash at the bottom is real: it
 * clears every shape the user has drawn.
 */
import {
  MousePointer2, Minus, TrendingUp, Square, Circle, PenLine,
  Type, Eraser, ZoomIn, Hand, Trash2,
} from "lucide-react"

/** Plotly's dragmode strings, plus the two selection-ish modes. */
export type DrawMode =
  | "pan" | "zoom" | "select"
  | "drawline" | "drawrect" | "drawcircle" | "drawopenpath"

export interface ToolSpec {
  id: DrawMode | "hline" | "text" | "erase" | "clear"
  label: string
  icon: React.ReactNode
  /** What `dragmode` becomes. Absent for the actions (text, clear). */
  mode?: DrawMode
  hint: string
}

const I = "h-[15px] w-[15px]"

export const TOOLS: ToolSpec[] = [
  { id: "select", label: "Cross", icon: <MousePointer2 className={I} aria-hidden />,
    mode: "select", hint: "Crosshair — read values without moving the chart" },
  { id: "pan", label: "Pan", icon: <Hand className={I} aria-hidden />,
    mode: "pan", hint: "Pan — drag the chart around" },
  { id: "zoom", label: "Zoom", icon: <ZoomIn className={I} aria-hidden />,
    mode: "zoom", hint: "Zoom — drag a box to zoom into it" },
  { id: "drawline", label: "Trend line", icon: <TrendingUp className={I} aria-hidden />,
    mode: "drawline", hint: "Trend line — drag from one point to another" },
  { id: "hline", label: "Horizontal line", icon: <Minus className={I} aria-hidden />,
    hint: "Horizontal line — drops a level at the last close, then drag it" },
  { id: "drawrect", label: "Rectangle", icon: <Square className={I} aria-hidden />,
    mode: "drawrect", hint: "Rectangle — mark a zone or a range" },
  { id: "drawcircle", label: "Ellipse", icon: <Circle className={I} aria-hidden />,
    mode: "drawcircle", hint: "Ellipse — circle an area of interest" },
  { id: "drawopenpath", label: "Freehand", icon: <PenLine className={I} aria-hidden />,
    mode: "drawopenpath", hint: "Freehand — draw a path with the mouse down" },
  { id: "text", label: "Note", icon: <Type className={I} aria-hidden />,
    hint: "Note — pin a text label to the chart" },
  // Plotly's "eraseshape" is a modebar BUTTON, not a dragmode -- there is no
  // click-a-shape-to-delete mode to switch the mouse into. So this undoes the
  // last drawing, which is the action a user reaches for the eraser to
  // perform, and it is honest about being an undo rather than a hover-erase.
  { id: "erase", label: "Undo drawing", icon: <Eraser className={I} aria-hidden />,
    hint: "Remove the last drawing you added" },
  { id: "clear", label: "Clear all", icon: <Trash2 className={I} aria-hidden />,
    hint: "Remove every drawing on this chart" },
]

export function ChartToolRail({ active, onPick }: {
  active: string
  onPick: (tool: ToolSpec) => void
}) {
  return (
    <div
      role="toolbar"
      aria-orientation="vertical"
      aria-label="Chart drawing tools"
      className="flex shrink-0 flex-col items-center gap-0.5 border-r border-[color:var(--hairline-soft)]
                 bg-[var(--surface-1)] px-1 py-1.5"
    >
      {TOOLS.map((t, i) => {
        const on = active === t.id
        return (
          <span key={t.id} className="contents">
            {/* A hairline before the eraser and the bin: they act on what is
                already drawn rather than drawing something, and grouping says
                so without a label. */}
            {(t.id === "erase" || t.id === "clear") && i > 0 && (
              <span className="my-0.5 h-px w-5 bg-[color:var(--hairline-soft)]" aria-hidden />
            )}
            <button
              type="button"
              title={t.hint}
              aria-label={t.label}
              aria-pressed={t.mode ? on : undefined}
              onClick={() => onPick(t)}
              className={`flex h-7 w-7 items-center justify-center rounded transition-colors
                          ${on
                            ? "bg-[color:var(--raise-4)] text-[#38bdf8]"
                            : "text-muted-foreground hover:bg-[color:var(--raise-3)] hover:text-foreground"}`}
            >
              {t.icon}
            </button>
          </span>
        )
      })}
    </div>
  )
}
