/**
 * The economic calendar (upgrade plan, Feature 8): official US release dates and times,
 * Eastern, grouped by day. Dates and times only -- official schedules publish no forecasts
 * or actual values. Events added by hand cover anything the schedules miss.
 */
import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { nowEastern, type EconEvent } from "@/lib/econCalendar"

const IMPACT_STYLE: Record<EconEvent["impact"], string> = {
  high: "bg-amber-500/15 text-amber-800 dark:text-amber-200 ring-amber-400/40",
  medium: "bg-sky-500/15 text-sky-800 dark:text-sky-200 ring-sky-400/40",
  low: "bg-[color:var(--raise-3)] text-muted-foreground ring-[color:var(--hairline-mid)]",
}
const sel = "h-8 rounded-lg border border-input bg-transparent px-2 text-sm"

function addDays(isoDay: string, n: number): string {
  const d = new Date(`${isoDay}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

export function CalendarPage() {
  const qc = useQueryClient()
  const today = nowEastern().slice(0, 10)
  const [span, setSpan] = useState(14)
  const [impact, setImpact] = useState("")
  const end = addDays(today, span)
  const q = useQuery({ queryKey: ["calendar", today, end, impact], queryFn: () => api.calendar(today, end, impact || undefined) })
  const [title, setTitle] = useState("")
  const [at, setAt] = useState("")
  const [imp, setImp] = useState("medium")
  const add = useMutation({
    mutationFn: () => api.addCalendarEvent({ title, at, impact: imp }),
    onSuccess: () => { setTitle(""); setAt(""); void qc.invalidateQueries({ queryKey: ["calendar"] }) },
  })
  const del = useMutation({
    mutationFn: (uid: string) => api.deleteCalendarEvent(uid),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["calendar"] }),
  })
  const byDay = useMemo(() => {
    const m = new Map<string, EconEvent[]>()
    for (const e of q.data?.events ?? []) m.set(e.at.slice(0, 10), [...(m.get(e.at.slice(0, 10)) ?? []), e])
    return [...m]
  }, [q.data])
  const sources = Object.entries(q.data?.sources ?? {})

  return (
    <div className="mx-auto max-w-4xl space-y-3 p-3">
      <Card className="p-3 border border-[color:var(--hairline-soft)]">
        <div className="flex flex-wrap items-end gap-3">
          <h1 className="mr-2 text-base font-semibold">Economic calendar</h1>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">Show
            <select className={sel} value={span} onChange={(e) => setSpan(Number(e.target.value))} aria-label="Range">
              <option value={1}>today and tomorrow</option><option value={7}>the next 7 days</option>
              <option value={14}>the next 14 days</option><option value={60}>the next 60 days</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">Impact
            <select className={sel} value={impact} onChange={(e) => setImpact(e.target.value)} aria-label="Impact">
              <option value="">all</option><option value="high">high only</option>
              <option value="medium">medium only</option><option value="low">low only</option>
            </select>
          </label>
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">
          Official US schedules (BEA, the Federal Reserve, BLS), times in ET. Dates and times only:
          official schedules do not publish forecasts or results.
        </p>
        {sources.length > 0 && (
          <ul className="mt-1 text-[11px]" aria-label="Sources">
            {sources.map(([name, s]) => (
              <li key={name} className={s.ok ? "text-muted-foreground" : "text-[var(--loss)]"}>
                {name}: {s.ok ? `${s.events} events, checked ${s.fetched_at.slice(0, 16).replace("T", " ")}` : s.error}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="p-3 border border-[color:var(--hairline-soft)]" data-testid="calendar-list">
        {q.isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {q.error && <p role="alert" className="text-sm text-[var(--loss)]">{(q.error as Error).message}</p>}
        {q.data && byDay.length === 0 && <p className="text-sm text-muted-foreground">No events in this range.</p>}
        {byDay.map(([d, list]) => (
          <section key={d} className="mb-3">
            <h2 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {new Date(`${d}T12:00:00`).toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" })}
            </h2>
            <ul>
              {list.map((e) => (
                <li key={e.uid} className="flex items-center gap-3 border-t border-[color:var(--hairline-soft)] py-1.5 text-sm">
                  <span className="w-12 tabular-nums">{e.at.slice(11, 16)}</span>
                  <span className={`w-16 rounded px-1.5 py-0.5 text-center text-[10px] font-bold uppercase ring-1 ${IMPACT_STYLE[e.impact]}`}>
                    {e.impact}
                  </span>
                  <span className="flex-1">{e.title}{e.note && <span className="text-muted-foreground"> - {e.note}</span>}</span>
                  <span className="text-xs text-muted-foreground">{e.source}</span>
                  {e.source === "manual" && (
                    <button type="button" className="text-xs underline" aria-label={`Delete ${e.title}`}
                            onClick={() => del.mutate(e.uid)}>Delete</button>
                  )}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </Card>

      <Card className="p-3 border border-[color:var(--hairline-soft)]">
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Add an event</div>
        <div className="flex flex-wrap items-end gap-2">
          <Input className="w-64" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="What is released" aria-label="Event title" />
          <Input className="w-52" type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} aria-label="Event time (ET)" />
          <select className={sel} value={imp} onChange={(e) => setImp(e.target.value)} aria-label="Event impact">
            <option value="high">high</option><option value="medium">medium</option><option value="low">low</option>
          </select>
          <Button size="sm" disabled={!title.trim() || !at || add.isPending} onClick={() => add.mutate()}>Add</Button>
        </div>
        {add.error && <p role="alert" className="mt-1 text-xs text-[var(--loss)]">{(add.error as Error).message}</p>}
      </Card>
    </div>
  )
}
