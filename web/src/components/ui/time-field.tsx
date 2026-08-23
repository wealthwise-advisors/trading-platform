// Digital-clock time field with an explicit AM/PM segment.
//
// Replaces <input type="time">. The native control renders as a 24-hour
// spinner in most locales here, so "18:00" has to be converted in your head to
// know it means 6 PM -- and getting that wrong silently shifts a whole session
// window, which for an overnight range like 18:00-17:00 is the difference
// between "yesterday evening through this afternoon" and something nonsensical.
//
// The value handed in and out is unchanged: 24-hour "HH:MM". Only the display
// and the way it is edited differ, so every caller, the request payload and the
// VWAP session anchor all keep working exactly as before.

import { useId } from "react"

import { parse, display, pad, stepHour, stepMinute, togglePeriod } from "@/lib/clock"

interface TimeFieldProps {
  /** 24-hour "HH:MM". */
  value: string
  onChange: (next: string) => void
  disabled?: boolean
  /** Accessible name, e.g. "Session start". */
  label?: string
  title?: string
  className?: string
  /** Render AM and PM as two visible buttons instead of one toggle.
   *  A toggle is fine where space is tight, but it only shows the CURRENT
   *  period -- you have to know that clicking it means "switch". Segmented
   *  shows both states at once, so setting a time is one deliberate click on
   *  the half you want rather than a guess about what the button does. */
  segmented?: boolean
}

export function TimeField({
  value, onChange, disabled = false, label, title, className = "", segmented = false,
}: TimeFieldProps) {
  const uid = useId()
  const { h, m } = parse(value)
  const { h12, mm, period } = display(h, m)

  const Stepper = ({ onUp, onDown, name }: { onUp: () => void; onDown: () => void; name: string }) => (
    <span className="flex flex-col justify-center -my-0.5">
      <button type="button" disabled={disabled} aria-label={`${name} up`} onClick={onUp}
              className="leading-none text-[9px] px-1 text-muted-foreground hover:text-foreground disabled:opacity-30">▲</button>
      <button type="button" disabled={disabled} aria-label={`${name} down`} onClick={onDown}
              className="leading-none text-[9px] px-1 text-muted-foreground hover:text-foreground disabled:opacity-30">▼</button>
    </span>
  )

  return (
    <div
      className={`flex items-center gap-1 rounded-md border border-input bg-transparent px-2 py-1.5
                  ${disabled ? "opacity-50" : "hover:border-primary/35"} ${className}`}
      title={title}
      role="group"
      aria-label={label}
    >
      {/* The reading, in one glance, in the form people actually say it. */}
      <span className="font-mono text-base tabular-nums tracking-tight select-none">
        {pad(h12)}
      </span>
      <Stepper name={`${label ?? "time"} hour`}
               onUp={() => onChange(stepHour(value, 1))}
               onDown={() => onChange(stepHour(value, -1))} />

      <span className="font-mono text-base select-none -mx-0.5">:</span>

      <span className="font-mono text-base tabular-nums tracking-tight select-none">{mm}</span>
      <Stepper name={`${label ?? "time"} minute`}
               onUp={() => onChange(stepMinute(value, 1))}
               onDown={() => onChange(stepMinute(value, -1))} />

      {/* Always spelled out -- never inferred from a 24-hour number. */}
      {segmented ? (
        <span className="ml-1.5 flex gap-1" role="group"
              aria-label={`${label ?? "time"} AM or PM`}>
          {(["AM", "PM"] as const).map((p) => (
            <button
              key={p}
              type="button"
              disabled={disabled}
              aria-pressed={period === p}
              onClick={() => { if (period !== p) onChange(togglePeriod(value)) }}
              title={`Set ${label ?? "time"} to ${p}`}
              className={`ampm-seg${period === p ? " ampm-seg-on" : ""}`}
            >
              {p}
            </button>
          ))}
        </span>
      ) : (
        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange(togglePeriod(value))}
          aria-label={`${label ?? "time"} AM or PM, currently ${period}`}
          title="Switch between AM and PM"
          className="ml-1 rounded px-1.5 py-0.5 text-xs font-semibold tracking-wide
                     border border-primary/40 text-primary hover:bg-primary/10
                     disabled:opacity-40 disabled:hover:bg-transparent"
        >
          {period}
        </button>
      )}

      {/* Keeps the real 24-hour value in the DOM: existing tests and any
          form-serialisation keep finding a time input with the same value. */}
      <input type="hidden" id={uid} value={`${pad(h)}:${pad(m)}`} readOnly />
    </div>
  )
}
