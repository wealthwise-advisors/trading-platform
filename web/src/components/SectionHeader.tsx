// The bar at the top of each data panel on the Market Grid.
//
// One component for all three panels (Live state / Consolidated tape / Recent
// trades) so the eye can tell instantly that they are three views of the same
// session rather than three unrelated widgets. Before this, each panel had
// grown its own header markup and they had drifted apart.

import type { ReactNode } from "react"
import { ChevronDown, ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

export function LiveBadge({ on }: { on: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded px-1.5 py-0.5",
        "text-[10px] font-bold tracking-[0.1em] uppercase",
        on
          ? "bg-emerald-500/12 text-emerald-800 dark:text-emerald-300 ring-1 ring-emerald-400/30"
          : "bg-[color:var(--raise-3)] text-muted-foreground/75 ring-1 ring-[color:var(--hairline-mid)]",
      )}
    >
      {/* Static, not pulsing. A throbbing dot is looping attention-seeking
          motion: it never stops, it cannot be paused, and it competes with the
          numbers beside it -- which are the thing actually worth watching.
          Colour alone carries the state. */}
      <span
        className={cn("h-1.5 w-1.5 rounded-full",
                      on ? "bg-emerald-400 shadow-[0_0_6px_1px] shadow-emerald-500/50"
                         : "bg-slate-600")}
      />
      {on ? "Live" : "Idle"}
    </span>
  )
}

export function SectionHeader({
  title, meta, live, right, tools, collapsed, onToggle,
}: {
  title: string
  /** Quiet caption beside the title -- counts, timestamps, scope. */
  meta?: ReactNode
  /** Omit entirely to draw no badge; pass a boolean to draw Live/Idle. */
  live?: boolean
  /** Controls pinned to the right edge. */
  right?: ReactNode
  /**
   * Icon-only controls at the very end of the row -- a settings gear, a full
   * screen toggle. Separate from `right` so the panel's own controls always
   * sit outermost, in the same place on every panel, however much `right`
   * carries.
   */
  tools?: ReactNode
  /**
   * Draws a disclosure chevron before the title. Omit both and none is drawn:
   * a panel that cannot be folded should not advertise that it can.
   */
  collapsed?: boolean
  onToggle?: () => void
}) {
  const foldable = collapsed !== undefined && !!onToggle
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-4 py-2.5
                    border-b border-[color:var(--hairline-soft)] bg-[var(--surface-2)]">
      {foldable && (
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={!collapsed}
          aria-label={`${collapsed ? "Show" : "Hide"} ${title}`}
          className="-ml-1 grid h-5 w-5 shrink-0 place-items-center rounded
                     text-muted-foreground hover:bg-[color:var(--raise-3)] hover:text-foreground"
        >
          {collapsed ? <ChevronRight size={14} strokeWidth={2.4} />
                     : <ChevronDown size={14} strokeWidth={2.4} />}
        </button>
      )}
      <h3 className="text-[13px] font-bold uppercase tracking-[0.09em]
                     text-violet-800 dark:text-violet-300 whitespace-nowrap">
        {title}
      </h3>
      {live !== undefined && <LiveBadge on={live} />}
      {meta && (
        <span className="text-xs text-muted-foreground/75 font-normal min-w-0">{meta}</span>
      )}
      {(right || tools) && (
        <div className="ml-auto flex items-center gap-2">
          {right}
          {tools && <div className="flex items-center gap-1">{tools}</div>}
        </div>
      )}
    </div>
  )
}
