/**
 * The results tab strip, sized to the space it actually has.
 *
 * WHAT WAS WRONG. The strip used to be a fixed split: ten tabs in the row and
 * four -- Candlestick Patterns, Chart Patterns, Strategy Optimizer, Elliott
 * Wave -- hard-coded into the "..." menu. So:
 *
 *   - Closing the market rail freed hundreds of pixels and the four never came
 *     back, because nothing measured anything. The split was a list, not a fit.
 *   - With the rail open the ten did not fit either; Trading Journal was
 *     clipped at the right edge with nothing to say it was there.
 *   - The menu opened DOWNWARD from a strip that sits at the bottom of the
 *     column. It rendered below the fold and under the status bar, so the
 *     button looked dead. It was open -- you just could not see it.
 *
 * WHAT IT DOES NOW. Every tab is rendered in order. Each one's natural width is
 * measured once, and on every resize the strip shows as many as fit and moves
 * ONLY the rest behind "...". Close the rail and they come back; open it and
 * they fold away again. When everything fits, there is no "..." at all. The
 * menu opens upward, above the strip, where there is room.
 *
 * Every tab stays a real TabsTrigger -- the folded ones are hidden, not
 * removed -- so the panel, the header's deep links and Radix's aria wiring are
 * identical whichever side of the fold a tab is on.
 *
 * Chart never folds. It is the app's primary view.
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react"
import { MoreHorizontal } from "lucide-react"

import { Button } from "@/components/ui/button"
import { TabsList, TabsTrigger } from "@/components/ui/tabs"

export interface StripTab {
  value: string
  /** Icon and label, as the trigger renders them. */
  content: React.ReactNode
  /** Plain label for the overflow menu and its accessible name. */
  label: string
  /** Icon alone, for the overflow menu row. */
  icon: React.ReactNode
}

/** The "..." button's width plus the gap before it, reserved when it shows. */
const MORE_RESERVE = 44

export function ResultsTabStrip({
  tabs, value, onSelect,
}: {
  tabs: StripTab[]
  value: string
  onSelect: (tab: string) => void
}) {
  const rowRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  // Natural width of each trigger, by value. Measured while it is visible and
  // kept while it is folded, because a hidden element measures as zero.
  const widths = useRef(new Map<string, number>())
  const [fit, setFit] = useState(tabs.length)

  const measure = useCallback(() => {
    const row = rowRef.current
    const list = listRef.current
    if (!row || !list) return

    for (const el of Array.from(list.querySelectorAll<HTMLElement>("[role='tab']"))) {
      const v = el.dataset.stripValue
      if (v && el.offsetParent !== null) widths.current.set(v, el.getBoundingClientRect().width)
    }
    // Every width must be known before a split can be computed. On first mount
    // all tabs are visible, so this only waits a frame at most.
    if (tabs.some((t) => !widths.current.has(t.value))) return

    const cs = getComputedStyle(list)
    const gap = parseFloat(cs.columnGap || cs.gap || "0") || 0
    const pad = (parseFloat(cs.paddingLeft) || 0) + (parseFloat(cs.paddingRight) || 0)
    const avail = row.clientWidth

    const span = (k: number) => {
      let w = pad
      for (let i = 0; i < k; i++) w += widths.current.get(tabs[i].value)! + (i ? gap : 0)
      return w
    }

    if (span(tabs.length) <= avail) { setFit(tabs.length); return }
    let k = tabs.length - 1
    while (k > 1 && span(k) + MORE_RESERVE > avail) k--
    setFit(Math.max(1, k))
  }, [tabs])

  // Measure before paint so the first frame is already split correctly, then
  // follow the row's width -- which is exactly what the rail toggle changes.
  useLayoutEffect(() => { measure() }, [measure])
  useEffect(() => {
    const row = rowRef.current
    if (!row) return
    const ro = new ResizeObserver(() => measure())
    ro.observe(row)
    return () => ro.disconnect()
  }, [measure])

  const folded = tabs.slice(fit)

  return (
    <div ref={rowRef} className="flex flex-1 min-w-0 items-center gap-2">
      <TabsList ref={listRef} className="tabs-scroll">
        {tabs.map((t, i) => (
          <TabsTrigger key={t.value} value={t.value} data-strip-value={t.value}
                       hidden={i >= fit}>
            {t.content}
          </TabsTrigger>
        ))}
      </TabsList>
      {folded.length > 0 && (
        <OverflowMenu tabs={folded} value={value} onSelect={onSelect} />
      )}
    </div>
  )
}

function OverflowMenu({
  tabs, value, onSelect,
}: { tabs: StripTab[]; value: string; onSelect: (tab: string) => void }) {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  // Lit when the open panel is one of the folded tabs, so the strip never
  // looks like nothing is selected while a folded panel is on screen.
  const active = tabs.some((t) => t.value === value)

  useEffect(() => {
    if (!open) return
    const away = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false)
    }
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false) }
    document.addEventListener("mousedown", away)
    document.addEventListener("keydown", esc)
    return () => {
      document.removeEventListener("mousedown", away)
      document.removeEventListener("keydown", esc)
    }
  }, [open])

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
        // UPWARD: bottom-full, not mt-1. The strip is the last thing in its
        // column, so a menu opening down lands below the fold and under the
        // status bar -- which is how this button came to look like it did
        // nothing at all.
        <div role="menu"
             className="absolute right-0 bottom-full z-50 mb-1 w-52 overflow-hidden rounded-lg
                        border border-[color:var(--hairline-mid)] bg-[var(--surface-1)] py-1 shadow-xl">
          {tabs.map((t) => (
            <button
              key={t.value}
              type="button"
              role="menuitem"
              aria-current={t.value === value ? "true" : undefined}
              onClick={() => { setOpen(false); onSelect(t.value) }}
              className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs
                          hover:bg-[color:var(--raise-3)] text-foreground
                          ${t.value === value ? "font-medium" : ""}`}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
