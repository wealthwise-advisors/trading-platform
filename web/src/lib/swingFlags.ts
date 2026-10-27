/**
 * Swing flags on the Chart page: a swing where some timeframe's POC sits on
 * the POC Average (same whole number) is flagged ⚑ -- sir, 2026-10-27.
 *
 * The numbers come from POST /api/poc-average, which computes them from the
 * same bars Market Grid holds (src/analysis/poc_average.py). This file only
 * turns swing points into the moments to ask about, and the answer back into
 * flags and hover text.
 */

/** One moment's answer from /api/poc-average. */
export interface PocAverageMoment {
  t: string
  average: number | null
  pocs: Record<string, number>
  matches: string[]
}

export interface PocAverageAnswer {
  timeframes: string[]
  moments: PocAverageMoment[]
}

export interface SwingFlag {
  average: number
  /** Every timeframe whose POC is on the average, with that POC. */
  matches: { tf: string; poc: number }[]
}

/**
 * The moment a swing point is judged at: its bar's CLOSE, the same moment a
 * Consolidated tape row stands for. `t` is the bar's naive Eastern open time.
 */
export function swingMoment(t: string, barMinutes: number): string {
  const ms = Date.parse(`${t.length === 16 ? `${t}:00` : t}Z`) + barMinutes * 60_000
  return new Date(ms).toISOString().slice(0, 19)
}

/** Swing open time -> its flag, for the swings that have one. */
export function flaggedSwings(
  points: readonly { t: string }[], barMinutes: number, answer: PocAverageAnswer | undefined,
): Map<string, SwingFlag> {
  const out = new Map<string, SwingFlag>()
  if (!answer) return out
  const byMoment = new Map(answer.moments.map((m) => [m.t.slice(0, 19), m]))
  for (const p of points) {
    const m = byMoment.get(swingMoment(p.t, barMinutes))
    if (!m || m.average == null || m.matches.length === 0) continue
    out.set(p.t, {
      average: m.average,
      matches: m.matches.map((tf) => ({ tf, poc: m.pocs[tf] })),
    })
  }
  return out
}

/** The line the hover popup adds for a flagged swing. */
export function swingFlagText(f: SwingFlag): string {
  const on = f.matches.map((m) => `${m.tf} ${m.poc.toFixed(2)}`).join(", ")
  return `⚑ POC Average ${f.average.toFixed(2)} — on it: ${on}`
}
