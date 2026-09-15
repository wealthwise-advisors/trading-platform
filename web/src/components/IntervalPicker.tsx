// The interval control in the Backtest panel, modelled on thinkorswim's
// interval selector.
//
// A button showing the current interval opens a popup with two tabs. Time frame
// lists every interval as "days : interval" -- read off lib/chartSetup.ts, the
// same table that already moves the start date when an interval is picked.
// Favorites holds the starred rows. "Customize list..." reorders and hides rows.
//
// Picking a row does exactly what the dropdown this replaces did: it reports
// the interval, and the caller sets both the interval and its lookback range.
// Stars, order and hidden rows are per browser and never reach the config or a
// request -- see lib/intervalPicker.ts for why.

import { useEffect, useMemo, useState } from "react"
import { Popover } from "radix-ui"
import { Check, ChevronDown, ChevronUp, Clock, Star } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { daysFor } from "@/lib/chartSetup"
import {
  defaultLayout, favouriteRows, loadFavourites, loadLayout, moveInterval,
  rangeLabel, saveFavourites, saveLayout, toggleFavourite, toggleHidden, visibleRows,
} from "@/lib/intervalPicker"
import { cn } from "@/lib/utils"

/** The row's accessible name: the interval, then its lookback when it has one. */
function rowName(tf: string): string {
  const days = daysFor(tf)
  return days == null ? tf : `${tf}, ${days} days`
}

function IntervalRow({
  tf, selected, starred, onPick, onStar,
}: {
  tf: string
  selected: boolean
  starred: boolean
  onPick: (tf: string) => void
  onStar: (tf: string) => void
}) {
  const range = rangeLabel(tf)
  return (
    <li className={cn("flex items-center gap-1 rounded-md", selected && "bg-violet-500/15")}>
      <button
        type="button"
        aria-label={rowName(tf)}
        aria-current={selected ? "true" : undefined}
        onClick={() => onPick(tf)}
        className="flex min-w-0 flex-1 items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-sm
                   hover:bg-white/5 outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
      >
        <span aria-hidden className="w-9 shrink-0 rounded bg-white/[0.06] px-1 py-px text-center
                                     text-[11px] font-semibold tabular-nums text-violet-200">
          {tf}
        </span>
        {/* TOS reads range first: "2 D : 1m". An interval with no specified day
            count shows its name alone rather than a number nobody chose. */}
        <span aria-hidden className="flex-1 tabular-nums">{range ? `${range} : ${tf}` : tf}</span>
        {selected && <Check aria-hidden className="h-3.5 w-3.5 text-violet-300" />}
      </button>
      <button
        type="button"
        aria-label={`${starred ? "Unstar" : "Star"} ${tf}`}
        aria-pressed={starred}
        onClick={() => onStar(tf)}
        className={cn("fav-btn", starred && "fav-btn-on")}
      >
        <Star size={15} strokeWidth={2} fill={starred ? "currentColor" : "none"} />
      </button>
    </li>
  )
}

export function IntervalPicker({
  value, onChange,
}: {
  value: string
  onChange: (tf: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [view, setView] = useState<"list" | "customize">("list")
  const [favs, setFavs] = useState<string[]>(() => loadFavourites())
  const [layout, setLayout] = useState(() => loadLayout())
  // Opens on Favorites once there are some -- that is what the tab is for --
  // and on the full list until then, so a first visit never lands on an empty tab.
  const [tab, setTab] = useState(() => (loadFavourites().length ? "favorites" : "timeframe"))

  useEffect(() => { saveFavourites(favs) }, [favs])
  useEffect(() => { saveLayout(layout) }, [layout])

  const rows = useMemo(() => visibleRows(layout), [layout])
  const favRows = useMemo(() => favouriteRows(layout, favs), [layout, favs])

  function pick(tf: string) {
    onChange(tf)
    setOpen(false)
  }
  const star = (tf: string) => setFavs((f) => toggleFavourite(f, tf))

  const renderRows = (list: string[]) => (
    <ul className="max-h-72 space-y-0.5 overflow-y-auto">
      {list.map((tf) => (
        <IntervalRow key={tf} tf={tf} selected={tf === value}
                     starred={favs.includes(tf)} onPick={pick} onStar={star} />
      ))}
    </ul>
  )

  return (
    <Popover.Root
      open={open}
      onOpenChange={(v) => { setOpen(v); if (!v) setView("list") }}
    >
      <Popover.Trigger asChild>
        {/* Same box as the dropdown it replaces, so the panel does not shift. */}
        <button
          type="button"
          aria-label={`Interval: ${value}`}
          className="flex h-8 w-full items-center justify-between gap-1.5 rounded-lg border border-input
                     bg-transparent py-2 pr-2 pl-2.5 text-sm whitespace-nowrap transition-colors outline-none
                     select-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50
                     dark:bg-input/30 dark:hover:bg-input/50"
        >
          <span className="flex items-center gap-2">
            <Clock aria-hidden className="h-3.5 w-3.5 text-violet-400/70" />
            {value}
          </span>
          <ChevronDown aria-hidden className="size-4 text-muted-foreground" />
        </button>
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          aria-label="Interval picker"
          side="bottom"
          align="start"
          sideOffset={4}
          className="z-50 w-(--radix-popover-trigger-width) min-w-64 rounded-xl border border-white/10
                     bg-[#0d1420] p-1.5 text-popover-foreground shadow-2xl shadow-black/60 ring-1
                     ring-black/40 outline-none"
        >
          {view === "list" ? (
            <>
              <Tabs value={tab} onValueChange={setTab} className="gap-1.5">
                <TabsList className="w-full">
                  <TabsTrigger value="favorites" className="flex-1">
                    <Star aria-hidden className="h-3.5 w-3.5" /> Favorites
                  </TabsTrigger>
                  <TabsTrigger value="timeframe" className="flex-1">
                    <Clock aria-hidden className="h-3.5 w-3.5" /> Time frame
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="favorites">
                  {favRows.length ? renderRows(favRows) : (
                    <p className="px-2 py-4 text-center text-xs text-muted-foreground">
                      No favorites yet. Star an interval on the Time frame tab to keep it here.
                    </p>
                  )}
                </TabsContent>

                <TabsContent value="timeframe">
                  {rows.length ? renderRows(rows) : (
                    <p className="px-2 py-4 text-center text-xs text-muted-foreground">
                      Every interval is hidden. Use Customize list to show them again.
                    </p>
                  )}
                </TabsContent>
              </Tabs>

              <div className="mt-1.5 border-t border-white/8 pt-1.5">
                <button
                  type="button"
                  onClick={() => setView("customize")}
                  className="rounded px-2 py-1 text-xs text-muted-foreground hover:text-foreground
                             outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
                >
                  Customize list…
                </button>
              </div>
            </>
          ) : (
            <div>
              <div className="flex items-center justify-between px-2 py-1">
                <span className="text-sm font-semibold">Customize list</span>
                <button
                  type="button"
                  onClick={() => setView("list")}
                  className="rounded px-2 py-0.5 text-xs font-semibold text-violet-300 hover:text-violet-200
                             outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
                >
                  Done
                </button>
              </div>
              <p className="px-2 pb-1.5 text-[11px] text-muted-foreground">
                Reorder or hide rows. Intervals and day counts come from the app and cannot be edited here.
              </p>
              <ul className="max-h-72 space-y-0.5 overflow-y-auto">
                {layout.order.map((tf, i) => {
                  const shown = !layout.hidden.includes(tf)
                  const range = rangeLabel(tf)
                  return (
                    <li key={tf} className="flex items-center gap-1.5 rounded-md px-2 py-1 hover:bg-white/5">
                      <label className="flex min-w-0 flex-1 items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={shown}
                          aria-label={`Show ${tf} in the list`}
                          onChange={() => setLayout((l) => toggleHidden(l, tf))}
                        />
                        <span className="tabular-nums">{tf}</span>
                        <span className="text-[11px] text-muted-foreground">{range ?? "no day count"}</span>
                      </label>
                      <button
                        type="button"
                        aria-label={`Move ${tf} up`}
                        disabled={i === 0}
                        onClick={() => setLayout((l) => ({ ...l, order: moveInterval(l.order, tf, -1) }))}
                        className="rounded p-0.5 hover:bg-white/10 disabled:opacity-30
                                   outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
                      >
                        <ChevronUp aria-hidden className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        aria-label={`Move ${tf} down`}
                        disabled={i === layout.order.length - 1}
                        onClick={() => setLayout((l) => ({ ...l, order: moveInterval(l.order, tf, 1) }))}
                        className="rounded p-0.5 hover:bg-white/10 disabled:opacity-30
                                   outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
                      >
                        <ChevronDown aria-hidden className="h-4 w-4" />
                      </button>
                    </li>
                  )
                })}
              </ul>
              <div className="mt-1.5 border-t border-white/8 pt-1.5">
                <button
                  type="button"
                  onClick={() => setLayout(defaultLayout())}
                  className="rounded px-2 py-1 text-xs text-muted-foreground hover:text-foreground
                             outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
                >
                  Reset to default order
                </button>
              </div>
            </div>
          )}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
