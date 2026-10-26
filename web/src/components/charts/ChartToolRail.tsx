/**
 * The vertical drawing rail down the left edge of the chart, as the reference
 * has it.
 *
 * EVERY TOOL HERE IS REAL. The drawing tools map to a Plotly dragmode the
 * chart already supports natively -- `drawline`, `drawrect`, `drawcircle`,
 * `drawopenpath`, `zoom`, `pan` -- so selecting one changes what the mouse
 * does on the plot, and the shape you draw is a real Plotly shape that
 * persists and can be dragged afterwards. Horizontal line and note are
 * PLACEMENT tools: pick one, then click the chart where it should go (until
 * 2026-10-26 both dropped at the last bar's close on the far right edge,
 * where a user saw nothing happen). Undo and clear act immediately.
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
  /** What `dragmode` becomes. Absent for the placement tools and actions. */
  mode?: DrawMode
  /** Placed by a single click on the chart rather than drawn by a drag. */
  place?: boolean
  hint: string
  /** What to do next, shown over the chart while the tool is active. */
  howTo?: string
}

const I = "h-[15px] w-[15px]"

export const TOOLS: ToolSpec[] = [
  { id: "select", label: "Cross", icon: <MousePointer2 className={I} aria-hidden />,
    mode: "select", hint: "Crosshair — read values without moving the chart",
    howTo: "Hover to read values — the chart will not move" },
  { id: "pan", label: "Pan", icon: <Hand className={I} aria-hidden />,
    mode: "pan", hint: "Pan — drag the chart around" },
  { id: "zoom", label: "Zoom", icon: <ZoomIn className={I} aria-hidden />,
    mode: "zoom", hint: "Zoom — drag a box to zoom into it",
    howTo: "Drag a box over the bars to zoom into them — double-click to zoom back out" },
  { id: "drawline", label: "Trend line", icon: <TrendingUp className={I} aria-hidden />,
    mode: "drawline", hint: "Trend line — drag from one point to another",
    howTo: "Drag from one point to another to draw a trend line" },
  { id: "hline", label: "Horizontal line", icon: <Minus className={I} aria-hidden />,
    place: true, hint: "Horizontal line — click the chart at the price you want",
    howTo: "Click the chart at the price for the level" },
  { id: "drawrect", label: "Rectangle", icon: <Square className={I} aria-hidden />,
    mode: "drawrect", hint: "Rectangle — mark a zone or a range",
    howTo: "Drag on the chart to draw a rectangle" },
  { id: "drawcircle", label: "Ellipse", icon: <Circle className={I} aria-hidden />,
    mode: "drawcircle", hint: "Ellipse — circle an area of interest",
    howTo: "Drag on the chart to draw an ellipse" },
  { id: "drawopenpath", label: "Freehand", icon: <PenLine className={I} aria-hidden />,
    mode: "drawopenpath", hint: "Freehand — draw a path with the mouse down",
    howTo: "Hold the mouse down and draw" },
  { id: "text", label: "Note", icon: <Type className={I} aria-hidden />,
    place: true, hint: "Note — click the chart where the note should go",
    howTo: "Click the chart where the note should go" },
  // Plotly's "eraseshape" is a modebar BUTTON, not a dragmode -- there is no
  // click-a-shape-to-delete mode to switch the mouse into. So this undoes the
  // last drawing, which is the action a user reaches for the eraser to
  // perform, and it is honest about being an undo rather than a hover-erase.
  { id: "erase", label: "Undo drawing", icon: <Eraser className={I} aria-hidden />,
    hint: "Remove the last drawing you added" },
  { id: "clear", label: "Clear all", icon: <Trash2 className={I} aria-hidden />,
    hint: "Remove every drawing on this chart" },
]

export function ChartToolRail({ active, onPick, hasDrawings = true }: {
  active: string
  onPick: (tool: ToolSpec) => void
  /** False greys out undo and clear, which have nothing to act on. */
  hasDrawings?: boolean
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
        const idle = (t.id === "erase" || t.id === "clear") && !hasDrawings
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
              aria-pressed={t.mode || t.place ? on : undefined}
              disabled={idle}
              onClick={() => onPick(t)}
              className={`flex h-7 w-7 items-center justify-center rounded transition-colors
                          ${on
                            ? "bg-[color:var(--raise-4)] text-[#38bdf8]"
                            : "text-muted-foreground hover:bg-[color:var(--raise-3)] hover:text-foreground"}
                          disabled:opacity-35 disabled:hover:bg-transparent disabled:cursor-not-allowed`}
            >
              {t.icon}
            </button>
          </span>
        )
      })}
    </div>
  )
}
