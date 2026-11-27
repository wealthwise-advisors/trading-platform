// Every chart study behind ONE "Studies" button (user, 2026-11-27): groups, then the
// studies in each, then each study's own settings OPENED IN PLACE under it -- step by
// step, setting inside setting, no pop-up of their own.
//
// The checkboxes keep their "Show …" names and the gears their "… settings" names, so
// keyboard users, screen readers and the tests find the same controls as before.
import { useEffect, useRef } from "react"
import { createPortal } from "react-dom"
import { ChevronDown, ChevronRight, X } from "lucide-react"
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
  /** A one-line summary of the current settings, shown under the name. */
  summary?: string
  /** The study's settings, opened under it by its "… settings" button. */
  settings?: React.ReactNode
  settingsLabel?: string
  /** Studies that belong under this one (RSI → RSI(2), RSI(13)). */
  children?: StudyItem[]
  /** Extra controls shown under the item when it is on (CVD bars / line). */
  extra?: React.ReactNode
  /** A short status line (how many divergences). */
  note?: string | null
  /** A setting, not a study: no on/off switch, not counted as "on". */
  noSwitch?: boolean
}

export interface StudyGroup { title: string; items: StudyItem[] }
/** How the CVD row is drawn: bars (sir, 2026-11-27) or the original line. */
export type CvdStyle = "bars" | "line"

function countOn(items: StudyItem[]): number {
  return items.reduce((n, i) => n + (i.children ? countOn(i.children) : i.checked && !i.noSwitch ? 1 : 0), 0)
}

function Row({ item, depth, expanded, onExpand }: {
  item: StudyItem; depth: number; expanded: string | null; onExpand: (k: string | null) => void
}) {
  const parent = !!item.children?.length
  const open = expanded === item.key
  return (
    <div className={cn(depth > 0 && "ml-4 border-l border-[color:var(--hairline-soft)] pl-3")}>
      <div className={cn("study-row", open && "study-row-open")}>
        <label className={cn("flex min-w-0 flex-1 items-center gap-2.5", item.disabled ? "opacity-50" : "cursor-pointer")}
               title={item.title}>
          {!item.noSwitch && (
            <input type="checkbox" className="study-switch" checked={item.checked} disabled={item.disabled}
                   aria-label={item.aria} onChange={(e) => item.onChange(e.target.checked)} />
          )}
          <span className="min-w-0">
            <span className={cn("block truncate", parent ? "font-semibold" : "font-medium")}>{item.label}</span>
            {item.summary && <span className="block truncate text-[11px] text-muted-foreground">{item.summary}</span>}
          </span>
        </label>
        {item.settings && (
          <button type="button" aria-label={item.settingsLabel ?? `${item.label} settings`} aria-expanded={open}
                  title={open ? "Close the settings" : "Open the settings"}
                  onClick={() => onExpand(open ? null : item.key)}
                  className={cn("study-open", open && "study-open-on")}>
            <span>Settings</span>
            {open ? <ChevronDown className="h-3.5 w-3.5" aria-hidden /> : <ChevronRight className="h-3.5 w-3.5" aria-hidden />}
          </button>
        )}
      </div>
      {item.note && <p className="ml-11 -mt-1 mb-1 text-[11px] font-semibold text-amber-300">{item.note}</p>}
      {item.extra && item.checked && <div className="ml-11 mb-1.5">{item.extra}</div>}
      {open && item.settings && (
        <div className="study-settings" role="group" aria-label={item.settingsLabel ?? `${item.label} settings`}>
          {item.settings}
        </div>
      )}
      {item.children?.map((c) => <Row key={c.key} item={c} depth={depth + 1} expanded={expanded} onExpand={onExpand} />)}
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

export function StudiesPanel({ groups, expanded, onExpand, onClose, className, title = "Studies", inline = false }: {
  groups: StudyGroup[]
  title?: string
  /** Sits in the page (Market Grid columns): no outside-click close. */
  inline?: boolean
  expanded: string | null
  onExpand: (key: string | null) => void
  onClose: () => void
  className?: string
}) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (inline) return
    const away = (e: MouseEvent) => {
      const t = e.target as HTMLElement
      // Native colour pickers and selects open outside the panel's box.
      if (!t.isConnected || t.closest(".studies-btn")) return
      if (box.current && !box.current.contains(t)) onClose()
    }
    document.addEventListener("mousedown", away)
    return () => document.removeEventListener("mousedown", away)
  }, [onClose, inline])
  return (
    <div ref={box} role="dialog" aria-label={title} onKeyDown={(e) => { if (e.key === "Escape") onClose() }}
         className={cn("studies-panel", className)}>
      <div className="flex items-center justify-between border-b border-[color:var(--hairline-soft)] px-4 py-3">
        <div>
          <div className="text-sm font-semibold">{title}</div>
          <div className="text-[11px] text-muted-foreground">{studiesOn(groups)} on{inline ? "" : " · Settings opens each one in place"}</div>
        </div>
        <button type="button" onClick={onClose} aria-label={`Close ${title.toLowerCase()}`}
                className="grid h-7 w-7 place-items-center rounded-md text-muted-foreground hover:bg-[color:var(--raise-4)] hover:text-foreground">
          <X className="h-4 w-4" aria-hidden />
        </button>
      </div>
      <div className="studies-body">
        {/* Always open: a folded group showed a heading with nothing under it (user, 2026-11-27). */}
        {groups.filter((g) => g.items.length).map((g) => (
          <section key={g.title} className="study-group" aria-label={g.title}>
            <div className="study-group-head">
              <span>{g.title}</span>
              {g.items.some((i) => !i.noSwitch) && (
                <span className="text-[11px] font-normal normal-case tracking-normal text-muted-foreground">{countOn(g.items)} on</span>
              )}
            </div>
            <div className="pb-2">
              {g.items.map((i) => <Row key={i.key} item={i} depth={0} expanded={expanded} onExpand={onExpand} />)}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}

// ── The settings window (user, 2026-11-27: "like thinkorswim, but more professional") ──
// A proper window, not a dropdown: the studies on the left, grouped, each with its
// switch; the selected one's page on the right -- what it is, then its settings in
// sections, then Reset. The controls keep their names ("Show VWAP", "VWAP settings").

function flatten(items: StudyItem[]): StudyItem[] {
  return items.flatMap((i) => [i, ...flatten(i.children ?? [])])
}

function WindowRow({ item, depth, selected, onSelect }: {
  item: StudyItem; depth: number; selected: string | null; onSelect: (k: string) => void
}) {
  const on = selected === item.key
  return (
    <>
      <div className={cn("sw-row", on && "sw-row-on")} style={{ paddingLeft: 10 + depth * 18 }}>
        {item.noSwitch ? <span className="sw-switch-gap" aria-hidden /> : (
          <input type="checkbox" className="study-switch" checked={item.checked} disabled={item.disabled}
                 aria-label={item.aria} onChange={(e) => item.onChange(e.target.checked)} />
        )}
        <button type="button" className="sw-pick" aria-current={on ? "true" : undefined}
                aria-label={item.settings ? (item.settingsLabel ?? `${item.label} settings`) : `${item.label} details`}
                onClick={() => onSelect(item.key)}>
          <span className={cn("block truncate", item.children?.length ? "font-semibold" : "font-medium")}>{item.label}</span>
          {item.summary && <span className="block truncate text-[11px] text-muted-foreground">{item.summary}</span>}
        </button>
        {item.settings && <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />}
      </div>
      {item.children?.map((c) => <WindowRow key={c.key} item={c} depth={depth + 1} selected={selected} onSelect={onSelect} />)}
    </>
  )
}

export function SettingsWindow({ title, groups, selected, onSelect, onClose, descriptions = {} }: {
  title: string
  groups: StudyGroup[]
  selected: string | null
  onSelect: (key: string | null) => void
  onClose: () => void
  descriptions?: Record<string, string>
}) {
  const all = groups.flatMap((g) => flatten(g.items))
  const current = all.find((i) => i.key === selected) ?? all.find((i) => i.settings) ?? all[0]
  const closeRef = useRef<HTMLButtonElement>(null)
  useEffect(() => { closeRef.current?.focus() }, [])
  const desc = current ? descriptions[current.key] ?? current.title : undefined
  // At the page's top level: inside the chart card a blur or transform would trap a fixed window.
  return createPortal(
    <div className="sw-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div role="dialog" aria-modal="true" aria-label={title} className="sw-window"
           onKeyDown={(e) => { if (e.key === "Escape") onClose() }}>
        <header className="sw-head">
          <div>
            <div className="text-[15px] font-semibold">{title}</div>
            <div className="text-[11px] text-muted-foreground">{studiesOn(groups)} on · changes apply at once and are remembered</div>
          </div>
          <button ref={closeRef} type="button" onClick={onClose} aria-label={`Close ${title.toLowerCase()}`} className="sw-close">
            <X className="h-4 w-4" aria-hidden />
          </button>
        </header>
        <div className="sw-body">
          <nav className="sw-list" aria-label={`${title} list`}>
            {groups.filter((g) => g.items.length).map((g) => (
              <section key={g.title} aria-label={g.title}>
                <div className="sw-group">
                  <span>{g.title}</span>
                  {g.items.some((i) => !i.noSwitch) && <span className="sw-group-n">{countOn(g.items)} on</span>}
                </div>
                {g.items.map((i) => <WindowRow key={i.key} item={i} depth={0} selected={current?.key ?? null} onSelect={onSelect} />)}
              </section>
            ))}
          </nav>
          {current && (
            <section className="sw-page" aria-label={`${current.label} page`}>
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-[17px] font-semibold leading-tight">{current.label}</h3>
                {!current.noSwitch && (
                  <span className={cn("sw-state", current.checked && "sw-state-on")}>{current.checked ? "On" : "Off"}</span>
                )}
              </div>
              {desc && <p className="sw-desc">{desc}</p>}
              {current.note && <p className="text-[12px] font-semibold text-amber-300">{current.note}</p>}
              {current.extra && current.checked && <div>{current.extra}</div>}
              {current.settings ? (
                <div className="sw-settings" role="group" aria-label={current.settingsLabel ?? `${current.label} settings`}>
                  {current.settings}
                </div>
              ) : current.children?.length ? (
                <p className="text-[12px] text-muted-foreground">Pick one of its studies on the left: {current.children.map((c) => c.label).join(", ")}.</p>
              ) : (
                <p className="text-[12px] text-muted-foreground">No settings: switch it on or off on the left.</p>
              )}
            </section>
          )}
        </div>
        <footer className="sw-foot">
          <button type="button" className="btn-solid sw-done" onClick={onClose}>Done</button>
        </footer>
      </div>
    </div>,
    document.body,
  )
}
