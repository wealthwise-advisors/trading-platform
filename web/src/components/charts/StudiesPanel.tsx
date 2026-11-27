// Every chart study behind ONE "Studies" button (user, 2026-11-27): groups, then the
// studies in each, then each study's own settings -- step by step, instead of two rows
// of buttons over the chart. The chart gets that height back.
//
// The checkboxes keep their "Show …" names and the gears their "… settings" names, so
// keyboard users, screen readers and the tests find the same controls as before.
import { useEffect, useRef } from "react"
import { ChevronDown, Settings, X } from "lucide-react"
import { cn } from "@/lib/utils"

export interface StudyItem {
  key: string
  label: string
  /** The checkbox's accessible name ("Show VWAP"). */
  aria: string
  checked: boolean
  onChange: (on: boolean) => void
  disabled?: boolean
  title?: string
  /** The study's settings: its gear's accessible name and what it opens. */
  gear?: { label: string; onClick: () => void }
  /** Studies that belong under this one (RSI → RSI(2), RSI(13)). */
  children?: StudyItem[]
  /** Extra controls shown under the item when it is on (CVD bars / line). */
  extra?: React.ReactNode
  /** A short status line (how many divergences). */
  note?: string | null
}

export interface StudyGroup { title: string; items: StudyItem[] }

function countOn(items: StudyItem[]): number {
  return items.reduce((n, i) => n + (i.children ? countOn(i.children) : i.checked ? 1 : 0), 0)
}

function Row({ item, depth }: { item: StudyItem; depth: number }) {
  const parent = !!item.children?.length
  return (
    <div className={cn(depth > 0 && "ml-4 border-l border-[color:var(--hairline-soft)] pl-3")}>
      <div className="study-row">
        <label className={cn("flex min-w-0 flex-1 items-center gap-2.5", item.disabled ? "opacity-50" : "cursor-pointer")}
               title={item.title}>
          <input type="checkbox" className="study-switch" checked={item.checked} disabled={item.disabled}
                 aria-label={item.aria} onChange={(e) => item.onChange(e.target.checked)} />
          <span className={cn("truncate", parent ? "font-semibold" : "font-medium")}>{item.label}</span>
        </label>
        {item.gear && (
          <button type="button" aria-label={item.gear.label} title={item.gear.label} onClick={item.gear.onClick}
                  className="grid h-7 w-7 shrink-0 place-items-center rounded-md text-muted-foreground
                             transition-colors hover:bg-[color:var(--raise-4)] hover:text-foreground">
            <Settings className="h-3.5 w-3.5" aria-hidden />
          </button>
        )}
      </div>
      {item.note && <p className="ml-11 -mt-1 mb-1 text-[11px] font-semibold text-amber-300">{item.note}</p>}
      {item.extra && item.checked && <div className="ml-11 mb-1.5">{item.extra}</div>}
      {item.children?.map((c) => <Row key={c.key} item={c} depth={depth + 1} />)}
    </div>
  )
}

/** The toolbar button: "Studies", with how many are on. */
export function StudiesButton({ open, onClick, active }: { open: boolean; onClick: () => void; active: number }) {
  return (
    <button type="button" onClick={onClick} aria-expanded={open} aria-haspopup="dialog"
            className={cn("studies-btn", open && "studies-btn-open")}>
      <span>Studies</span>
      <span className="studies-count" aria-label={`${active} on`}>{active}</span>
      <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} aria-hidden />
    </button>
  )
}

export function studiesOn(groups: StudyGroup[]): number {
  return groups.reduce((n, g) => n + countOn(g.items), 0)
}

export function StudiesPanel({ groups, onClose, className }: {
  groups: StudyGroup[]
  onClose: () => void
  className?: string
}) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const away = (e: MouseEvent) => {
      const t = e.target as HTMLElement
      if (box.current && !box.current.contains(t) && !t.closest(".studies-btn")) onClose()
    }
    document.addEventListener("mousedown", away)
    return () => document.removeEventListener("mousedown", away)
  }, [onClose])
  return (
    <div ref={box} role="dialog" aria-label="Studies" onKeyDown={(e) => { if (e.key === "Escape") onClose() }}
         className={cn("studies-panel", className)}>
      <div className="flex items-center justify-between border-b border-[color:var(--hairline-soft)] px-4 py-3">
        <div>
          <div className="text-sm font-semibold">Studies</div>
          <div className="text-[11px] text-muted-foreground">{studiesOn(groups)} on · the gear opens a study's settings</div>
        </div>
        <button type="button" onClick={onClose} aria-label="Close studies"
                className="grid h-7 w-7 place-items-center rounded-md text-muted-foreground hover:bg-[color:var(--raise-4)] hover:text-foreground">
          <X className="h-4 w-4" aria-hidden />
        </button>
      </div>
      <div className="max-h-[70vh] overflow-y-auto px-3 py-2">
        {groups.filter((g) => g.items.length).map((g) => (
          <details key={g.title} open className="study-group">
            <summary>
              <span>{g.title}</span>
              <span className="text-[11px] font-normal text-muted-foreground">{countOn(g.items)} on</span>
            </summary>
            <div className="pb-2">{g.items.map((i) => <Row key={i.key} item={i} depth={0} />)}</div>
          </details>
        ))}
      </div>
    </div>
  )
}
