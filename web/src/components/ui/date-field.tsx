/**
 * A date field with a calendar popover, replacing the browser's native picker.
 *
 * The native control renders differently in every browser and cannot be themed --
 * it was the one control in the config panel that ignored the app's styling. This
 * one is built from the Radix Popover already in the project plus Tailwind, so it
 * costs no new dependency.
 *
 * IT IS A PRESENTATION CHANGE ONLY. The value in and out is the same
 * `YYYY-MM-DD` string the native input produced, so every caller, every request
 * and every stored config is untouched.
 *
 * Dates are handled in UTC throughout, the same choice `lib/dayRange.ts` makes and
 * for the same reason: `new Date("2026-08-12")` in a negative-offset zone lands on
 * the 11th, which would silently shift a range by a day.
 */

import * as React from "react"
import { Popover as PopoverPrimitive } from "radix-ui"
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"] as const
const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December"] as const

function parseISO(iso: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null
  const d = new Date(`${iso}T00:00:00Z`)
  return Number.isNaN(d.getTime()) ? null : d
}

function toISO(d: Date): string {
  return d.toISOString().slice(0, 10)
}

/** "17 Aug 2026" — unambiguous, unlike 08/17 vs 17/08. */
function pretty(iso: string): string {
  const d = parseISO(iso)
  if (!d) return iso || "Select date"
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()].slice(0, 3)} ${d.getUTCFullYear()}`
}

/** Every cell of the grid: leading blanks, then each day of the month. */
function monthGrid(year: number, month: number): (Date | null)[] {
  const first = new Date(Date.UTC(year, month, 1))
  const days = new Date(Date.UTC(year, month + 1, 0)).getUTCDate()
  const cells: (Date | null)[] = Array(first.getUTCDay()).fill(null)
  for (let d = 1; d <= days; d++) cells.push(new Date(Date.UTC(year, month, d)))
  return cells
}

interface Props {
  value: string
  onChange: (iso: string) => void
  /** Announced to screen readers, since the trigger shows only the date. */
  label: string
  disabled?: boolean
  className?: string
}

export function DateField({ value, onChange, label, disabled, className }: Props) {
  const [open, setOpen] = React.useState(false)
  const selected = parseISO(value)
  // The month on show. Starts at the selected date, and follows it when the value
  // is changed from outside -- a preset that moves the range a year back should
  // not leave the calendar sitting on the old month.
  const [view, setView] = React.useState<Date>(() => selected ?? new Date())
  React.useEffect(() => {
    if (selected) setView(selected)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])

  const todayISO = toISO(new Date())
  const year = view.getUTCFullYear()
  const month = view.getUTCMonth()
  const shift = (months: number) =>
    setView(new Date(Date.UTC(year, month + months, 1)))

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
      <PopoverPrimitive.Trigger asChild>
        <button
          type="button"
          disabled={disabled}
          aria-label={label}
          className={cn(
            "flex h-9 w-full items-center gap-2 rounded-lg border border-input",
            "bg-transparent px-2.5 text-sm transition-colors",
            "hover:border-violet-500/40 focus:outline-none focus-visible:ring-2",
            "focus-visible:ring-violet-500/40 disabled:opacity-50",
            className,
          )}
        >
          <CalendarDays className="h-4 w-4 shrink-0 text-violet-400" aria-hidden />
          <span className="min-w-0 flex-1 truncate text-left tabular-nums">
            {pretty(value)}
          </span>
          <ChevronRight
            className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                          open && "rotate-90")}
            aria-hidden
          />
        </button>
      </PopoverPrimitive.Trigger>

      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align="start"
          sideOffset={6}
          className="z-50 w-[260px] rounded-xl border border-white/10 bg-[#0d1420] p-3
                     shadow-2xl shadow-black/60"
        >
          <div className="mb-2 flex items-center justify-between">
            <button type="button" onClick={() => shift(-1)} aria-label="Previous month"
                    className="rounded-lg p-1 text-muted-foreground hover:bg-white/[0.06] hover:text-foreground">
              <ChevronLeft className="h-4 w-4" aria-hidden />
            </button>
            <span className="text-sm font-semibold">{MONTHS[month]} {year}</span>
            <button type="button" onClick={() => shift(1)} aria-label="Next month"
                    className="rounded-lg p-1 text-muted-foreground hover:bg-white/[0.06] hover:text-foreground">
              <ChevronRight className="h-4 w-4" aria-hidden />
            </button>
          </div>

          <div className="grid grid-cols-7 gap-0.5 text-center">
            {WEEKDAYS.map((w) => (
              <span key={w} className="py-1 text-[10px] font-medium uppercase text-muted-foreground">
                {w}
              </span>
            ))}
            {monthGrid(year, month).map((d, i) => {
              if (!d) return <span key={`blank-${i}`} />
              const iso = toISO(d)
              const isSelected = iso === value
              const isToday = iso === todayISO
              return (
                <button
                  key={iso}
                  type="button"
                  onClick={() => { onChange(iso); setOpen(false) }}
                  aria-current={isSelected ? "date" : undefined}
                  className={cn(
                    "rounded-md py-1.5 text-sm tabular-nums transition-colors",
                    "hover:bg-white/[0.08]",
                    isSelected && "bg-violet-500 text-white hover:bg-violet-500",
                    !isSelected && isToday && "ring-1 ring-violet-500/50",
                  )}
                >
                  {d.getUTCDate()}
                </button>
              )
            })}
          </div>

          <button
            type="button"
            onClick={() => { onChange(todayISO); setOpen(false) }}
            className="mt-2 w-full rounded-lg border border-white/10 py-1.5 text-xs
                       text-muted-foreground transition-colors
                       hover:border-violet-500/40 hover:text-violet-300"
          >
            Today
          </button>
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  )
}
