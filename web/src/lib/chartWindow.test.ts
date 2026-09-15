import { describe, expect, it } from "vitest"
import {
  DEFAULT_WINDOW_BARS, DEFAULT_WINDOW_MS, barStepMs, defaultAggregationSpanMs, defaultWindowMs,
} from "./chartWindow"

const pad = (n: number) => String(n).padStart(2, "0")

/**
 * Session bars from 09:30: `perDay` of them, `minutes` apart, on `days`
 * consecutive calendar days from 5 Jan 2026. Real date arithmetic, so a long
 * run crosses month ends as real data does.
 */
function sessionBars(minutes: number, perDay: number, days: number): string[] {
  const out: string[] = []
  for (let d = 0; d < days; d++) {
    const day = new Date(Date.UTC(2026, 0, 5 + d))
    const date = `${day.getUTCFullYear()}-${pad(day.getUTCMonth() + 1)}-${pad(day.getUTCDate())}`
    for (let i = 0; i < perDay; i++) {
      const m = 9 * 60 + 30 + i * minutes
      out.push(`${date}T${pad(Math.floor(m / 60))}:${pad(m % 60)}:00`)
    }
  }
  return out
}

describe("barStepMs", () => {
  it("reads the bar size, ignoring the overnight gap", () => {
    expect(barStepMs(sessionBars(5, 78, 2))).toBe(5 * 60_000)
    expect(barStepMs(sessionBars(240, 2, 3))).toBe(240 * 60_000)
  })
})

describe("defaultWindowMs", () => {
  it("stays two hours for every bar size up to 1h, as the chart always opened", () => {
    for (const [minutes, perDay] of [[1, 390], [5, 78], [15, 26], [45, 9], [60, 7]] as const) {
      expect(defaultWindowMs(sessionBars(minutes, perDay, 3))).toBe(DEFAULT_WINDOW_MS)
    }
  })

  it("opens 2h and 4h bars on their last forty bars, gaps included", () => {
    for (const [minutes, perDay] of [[120, 4], [240, 2]] as const) {
      const t = sessionBars(minutes, perDay, 30)
      const expected = new Date(t[t.length - 1]).getTime() - new Date(t[t.length - DEFAULT_WINDOW_BARS]).getTime()
      expect(Number.isFinite(expected)).toBe(true)
      expect(defaultWindowMs(t)).toBe(expected)
      expect(expected).toBeGreaterThan(DEFAULT_WINDOW_MS)
    }
  })

  it("shows everything when there are fewer than forty", () => {
    const t = sessionBars(240, 2, 5)
    expect(defaultWindowMs(t)).toBe(new Date(t[t.length - 1]).getTime() - new Date(t[0]).getTime())
  })

  it("falls back to two hours with too few bars to measure", () => {
    expect(defaultWindowMs([])).toBe(DEFAULT_WINDOW_MS)
    expect(defaultWindowMs(["2026-01-05T09:30:00"])).toBe(DEFAULT_WINDOW_MS)
  })
})

describe("defaultAggregationSpanMs", () => {
  it("is the same two hours as before for every bar size up to 1h", () => {
    for (const [minutes, perDay] of [[1, 390], [5, 78], [45, 9], [60, 7]] as const) {
      expect(defaultAggregationSpanMs(sessionBars(minutes, perDay, 3))).toBe(DEFAULT_WINDOW_MS)
    }
  })

  it("is exactly forty bars for 2h and 4h, not the gap-filled clock span", () => {
    for (const [minutes, perDay] of [[120, 4], [240, 2]] as const) {
      const t = sessionBars(minutes, perDay, 30)
      expect(defaultAggregationSpanMs(t)).toBe(DEFAULT_WINDOW_BARS * minutes * 60_000)
      // The clock window is far wider, because it includes every overnight gap.
      expect(defaultWindowMs(t)).toBeGreaterThan(defaultAggregationSpanMs(t))
    }
  })

  it("counts only the bars there are when there are fewer than forty", () => {
    expect(defaultAggregationSpanMs(sessionBars(240, 2, 5))).toBe(10 * 240 * 60_000)
  })
})
