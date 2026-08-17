// Pure clock arithmetic for the digital time field.
//
// Split out of components/ui/time-field.tsx so that file exports only its
// component (the fast-refresh rule the linter asks for), and -- more usefully --
// so the stepping rules can be unit tested directly instead of only by clicking.
//
// Everything here speaks 24-hour "HH:MM", which is the format the API, the
// session filter and the VWAP anchor all use. The 12-hour reading exists only
// for display.

export function parse(value: string): { h: number; m: number } {
  const [hh, mm] = (value || "00:00").split(":")
  const h = Math.min(23, Math.max(0, parseInt(hh, 10) || 0))
  const m = Math.min(59, Math.max(0, parseInt(mm, 10) || 0))
  return { h, m }
}

export const pad = (n: number) => String(n).padStart(2, "0")

/** 24h -> the three things a person actually reads. */
export function display(h: number, m: number) {
  const period = h < 12 ? "AM" : "PM"
  const h12 = h % 12 === 0 ? 12 : h % 12
  return { h12, mm: pad(m), period }
}

const fmt = (h: number, m: number) => `${pad(((h % 24) + 24) % 24)}:${pad(((m % 60) + 60) % 60)}`

/**
 * Nudge the hour, staying inside the current half of the day.
 *
 * 11 AM stepping up gives 12 AM, not 12 PM: AM/PM is the period button's job
 * and nothing else's, so the hour arrows can never flip it behind your back.
 */
export function stepHour(value: string, delta: number): string {
  const { h, m } = parse(value)
  const base = h < 12 ? 0 : 12
  return fmt(base + ((((h - base + delta) % 12) + 12) % 12), m)
}

/**
 * Nudge the minute by exactly `delta` minutes -- one per click.
 *
 * This stepped by 5 at first, on the assumption that session boundaries land on
 * five-minute marks. They do not always, and a stepper labelled with a single
 * arrow that moves five is simply wrong: 6:20 has to be able to reach 6:21.
 * Rolling past 59 or below 0 carries the hour, which is what a clock does.
 */
export function stepMinute(value: string, delta: number): string {
  const { h, m } = parse(value)
  const total = h * 60 + m + delta
  const wrapped = ((total % 1440) + 1440) % 1440
  return fmt(Math.floor(wrapped / 60), wrapped % 60)
}

/** Same clock time, other half of the day. */
export function togglePeriod(value: string): string {
  const { h, m } = parse(value)
  return fmt((h + 12) % 24, m)
}

/**
 * Add whole minutes to a naive "YYYY-MM-DDTHH:MM[:SS]" timestamp.
 *
 * Deliberately routed through Date.UTC rather than `new Date(iso)`. These
 * timestamps carry no zone: they are market wall-clock. Parsing one with the
 * local constructor applies the viewer's offset, which would shift every label
 * by hours depending on who is looking -- the same class of bug that made
 * timestamps read differently on two machines earlier in this project. UTC
 * arithmetic treats the fields as literal and gives the day/month rollover for
 * free.
 */
export function addMinutesNaive(iso: string, minutes: number): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(iso)
  if (!m) return iso
  const [, y, mo, d, hh, mm] = m
  const t = Date.UTC(+y, +mo - 1, +d, +hh, +mm) + minutes * 60_000
  const dt = new Date(t)
  const p = (n: number) => String(n).padStart(2, "0")
  return `${dt.getUTCFullYear()}-${p(dt.getUTCMonth() + 1)}-${p(dt.getUTCDate())}` +
         ` ${p(dt.getUTCHours())}:${p(dt.getUTCMinutes())}`
}

/**
 * A bar labelled by when it CLOSES rather than when it opens.
 *
 * Bars are stored and computed on their OPEN timestamp -- that is the
 * convention the engine, the shared clock and the VWAP anchor all use, and none
 * of that changes here. But an open-labelled final bar reads as though the
 * session stopped early: a 09:30-17:00 session ends with a bar labelled 16:59,
 * which looks like it cut off a minute short when in fact it covers 16:59-17:00.
 *
 * Labelling by close makes the last row read 17:00, exactly the configured end.
 * Display only.
 */
export function barCloseLabel(iso: string, timeframeMinutes: number): string {
  return addMinutesNaive(iso, timeframeMinutes)
}

/**
 * A bar labelled by when it OPENED, in the same shape barCloseLabel produces.
 *
 * The point is the SHAPE. Jump compares a bar's label against a time the user
 * typed, as strings, and the typed side is built by addMinutesNaive -- so it
 * reads "2026-08-13 14:20", space separated and without seconds. Passing the
 * raw ISO timestamp instead compares "2026-08-13T14:20:00" against that, and
 * because "T" sorts after " " every bar on the target's own date counts as
 * LATER than the target. The jump then falls back to the previous day and shows
 * a bar from a different session entirely, which is exactly what it did.
 *
 * Anything compared against a typed time has to come through here.
 */
export function barOpenLabel(iso: string): string {
  return addMinutesNaive(iso, 0)
}

/**
 * "Now" in Eastern, in the same shape as a bar label.
 *
 * Bar timestamps are naive Eastern and every helper above does plain string
 * arithmetic on that basis, so anything compared against a bar label has to be
 * produced in the same frame. Reading the local clock instead is wrong for any
 * user outside Eastern, which is the actual situation here -- the machine that
 * reported the 18:00 case is on Central, an hour behind the tape, so a local
 * clock would have called 18:00 "the future" a full hour later than it is.
 *
 * Built from Intl with an explicit zone rather than a fixed -4/-5 offset, so it
 * stays correct across DST without a table to maintain.
 */
export function nowEasternLabel(at: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York",
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).formatToParts(at)
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "00"
  // Intl can render midnight as hour 24 under hour12:false.
  const hour = get("hour") === "24" ? "00" : get("hour")
  return `${get("year")}-${get("month")}-${get("day")} ${hour}:${get("minute")}`
}
