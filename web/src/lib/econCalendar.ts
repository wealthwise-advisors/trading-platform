/**
 * The economic calendar on the chart (upgrade plan, Feature 8): which events to draw and
 * the next high-impact one. Times are Eastern wall-clock strings, like the bars, so they
 * compare as plain timestamps; the chart shifts both by the chosen zone together.
 */
export interface EconEvent {
  uid: string
  source: "BEA" | "FOMC" | "BLS" | "manual" | string
  title: string
  /** Eastern wall-clock, "2026-11-18T14:00". */
  at: string
  impact: "high" | "medium" | "low"
  note: string
}

const ms = (s: string) => new Date(s).getTime()

/** High and medium events between the first and last bar (low ones would crowd the chart). */
export function eventsInRange(list: EconEvent[], first: string, last: string): EconEvent[] {
  const a = ms(first), b = ms(last)
  return list.filter((e) => e.impact !== "low" && ms(e.at) >= a && ms(e.at) <= b)
}

const SHORT: [RegExp, string][] = [
  [/^FOMC/, "FOMC"], [/^Gross Domestic Product|^GDP/, "GDP"], [/^Personal Income and Outlays/, "PCE"],
  [/^Consumer Price Index/, "CPI"], [/^Employment Situation/, "Jobs"], [/^Producer Price Index/, "PPI"],
  [/^U\.S\. International Trade/, "Trade"],
]

export function shortLabel(e: EconEvent): string {
  const name = SHORT.find(([re]) => re.test(e.title))?.[1] ?? e.title.split(/[,(]/)[0].slice(0, 14)
  return `${name} ${e.at.slice(11, 16)}`
}

/** The soonest high-impact event within 24 hours of `nowEt` (Eastern wall-clock), or null. */
export function nextHighImpact(list: EconEvent[], nowEt: string): { event: EconEvent; minutes: number } | null {
  const now = ms(nowEt)
  const ahead = list.filter((e) => e.impact === "high" && ms(e.at) > now && ms(e.at) - now <= 24 * 3600_000)
    .sort((x, y) => ms(x.at) - ms(y.at))
  return ahead.length ? { event: ahead[0], minutes: Math.round((ms(ahead[0].at) - now) / 60_000) } : null
}

/** Now, as an Eastern wall-clock string. */
export function nowEastern(): string {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date()).map((x) => [x.type, x.value]))
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:${p.second}`
}

export interface ChartMark { at: string; impact: "high" | "medium"; label: string; titles: string[] }

/** One mark per minute: releases at the same time share a line and a label. */
export function chartMarks(list: EconEvent[], first: string, last: string): ChartMark[] {
  const by = new Map<string, EconEvent[]>()
  for (const e of eventsInRange(list, first, last)) by.set(e.at, [...(by.get(e.at) ?? []), e])
  return [...by].sort(([x], [y]) => ms(x) - ms(y)).map(([at, es]) => ({
    at,
    impact: es.some((e) => e.impact === "high") ? "high" : "medium",
    label: `${[...new Set(es.map((e) => shortLabel(e).slice(0, -6)))].join(", ")} ${at.slice(11, 16)}`,
    titles: es.map((e) => e.title),
  }))
}
