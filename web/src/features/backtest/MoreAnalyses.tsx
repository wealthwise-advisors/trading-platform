/**
 * The overflow menu beside the results tab strip.
 *
 * WHY IT EXISTS. The reference draws eight tabs and they fit the strip. The
 * app had nine, and at the reference width the ninth -- Elliott Wave -- was
 * clipped off the right edge with only an edge fade to say so. Deleting a
 * working analysis to make the row shorter was not on the table: twelve
 * modules and eight wave structures sit behind that tab. So the ninth moves
 * here, which is where a ninth item belongs once a row of eight is the design.
 *
 * It is still the same tab. Selecting an entry writes the same resultsTab the
 * strip writes, so the panel, the deep links from the header sections, and the
 * Tabs roving focus all behave exactly as they did.
 *
 * Hand-built rather than pulled from a library, matching AccountMenu in
 * components/HeaderNav.tsx: the project has Radix for selects, dialogs and
 * tabs but no menu primitive, and one small menu is not worth a dependency.
 */

import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  MoreHorizontal, Waves, LineChart, Activity, Shapes, Sparkles,
} from "lucide-react"

export interface OverflowTab {
  value: string
  label: string
  icon: React.ReactNode
}

/** What did not fit in the strip. The list is the contract.
 *
 *  Grew when the reference's trading dock -- Positions, Orders, Order History,
 *  Balance History, Trading Journal -- was added to the strip. Five new tabs
 *  do not fit beside the eight that were already there, so the four analyses
 *  a trader reaches for least often moved here to join Elliott Wave. None was
 *  deleted and none changed: each is the same panel, selected the same way. */
export const OVERFLOW_TABS: OverflowTab[] = [
  { value: "equity", label: "Equity Curve", icon: <LineChart className="h-3.5 w-3.5 shrink-0" aria-hidden /> },
  { value: "candles", label: "Candlestick Patterns", icon: <Activity className="h-3.5 w-3.5 shrink-0" aria-hidden /> },
  { value: "chartpatterns", label: "Chart Patterns", icon: <Shapes className="h-3.5 w-3.5 shrink-0" aria-hidden /> },
  { value: "optimizer", label: "Strategy Optimizer", icon: <Sparkles className="h-3.5 w-3.5 shrink-0" aria-hidden /> },
  { value: "elliottwave", label: "Elliott Wave", icon: <Waves className="h-3.5 w-3.5 shrink-0" aria-hidden /> },
]

export function MoreAnalyses({
  value, onSelect,
}: { value: string; onSelect: (tab: string) => void }) {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  // Lit when one of its entries is the open panel, so the strip never looks
  // like nothing is selected while an overflow analysis is on screen.
  const active = OVERFLOW_TABS.some((t) => t.value === value)

  useEffect(() => {
    const away = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", away)
    return () => document.removeEventListener("mousedown", away)
  }, [])

  return (
    <div ref={box} className="relative shrink-0">
      <Button
        type="button"
        size="sm"
        variant={active ? "default" : "secondary"}
        className="h-7 px-2"
        aria-haspopup="menu"
        aria-expanded={open}
        title="More analyses"
        onClick={() => setOpen((v) => !v)}
      >
        <MoreHorizontal className="h-4 w-4" aria-hidden />
        <span className="sr-only">More analyses</span>
      </Button>
      {open && (
        <div role="menu"
             className="absolute right-0 z-50 mt-1 w-48 overflow-hidden rounded-lg
                        border border-[color:var(--hairline-mid)] bg-[var(--surface-1)] py-1 shadow-xl">
          {OVERFLOW_TABS.map((t) => (
            <button
              key={t.value}
              type="button"
              role="menuitem"
              aria-current={t.value === value ? "true" : undefined}
              onClick={() => { setOpen(false); onSelect(t.value) }}
              className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs
                          hover:bg-[color:var(--raise-3)]
                          ${t.value === value ? "text-foreground font-medium" : "text-foreground"}`}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
