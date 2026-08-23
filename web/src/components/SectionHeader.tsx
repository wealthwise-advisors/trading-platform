// The bar at the top of each data panel on the Market Grid.
//
// One component for all three panels (Live state / Consolidated tape / Recent
// trades) so the eye can tell instantly that they are three views of the same
// session rather than three unrelated widgets. Before this, each panel had
// grown its own header markup and they had drifted apart.

import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

export function LiveBadge({ on }: { on: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded px-1.5 py-0.5",
        "text-[10px] font-bold tracking-[0.1em] uppercase",
        on
          ? "bg-emerald-500/12 text-emerald-300 ring-1 ring-emerald-400/30"
          : "bg-white/5 text-slate-500 ring-1 ring-white/10",
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
  title, meta, live, right,
}: {
  title: string
  /** Quiet caption beside the title -- counts, timestamps, scope. */
  meta?: ReactNode
  /** Omit entirely to draw no badge; pass a boolean to draw Live/Idle. */
  live?: boolean
  /** Controls pinned to the right edge. */
  right?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-4 py-2.5
                    border-b border-white/8 bg-[#0a1020]">
      <h3 className="text-[13px] font-bold uppercase tracking-[0.09em]
                     text-violet-300 whitespace-nowrap">
        {title}
      </h3>
      {live !== undefined && <LiveBadge on={live} />}
      {meta && (
        <span className="text-xs text-slate-500 font-normal min-w-0">{meta}</span>
      )}
      {right && <div className="ml-auto flex items-center gap-2">{right}</div>}
    </div>
  )
}
