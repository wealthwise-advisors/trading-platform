import { describe, expect, it } from "vitest"
import {
  xWindowMs,
  DEFAULT_WINDOW_BARS, DEFAULT_WINDOW_MS, barStepMs, chartRunKey, defaultAggregationSpanMs, defaultWindowMs,
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

describe("chartRunKey", () => {
  const a = { t: "2026-11-09T09:30:00" }, b = { t: "2026-11-09T09:31:00" }

  it("is unchanged when live bars are added", () => {
    expect(chartRunKey([a, b], "1m")).toBe(chartRunKey([a], "1m"))
  })

  it("changes with the timeframe or the start of the data", () => {
    expect(chartRunKey([a], "1m")).not.toBe(chartRunKey([a], "5m"))
    expect(chartRunKey([a], "1m")).not.toBe(chartRunKey([b], "1m"))
  })

  it("copes with no bars", () => expect(chartRunKey([], "1m")).toBe("1m|"))
})

describe("xWindowMs", () => {
  const t = Array.from({ length: 20 }, (_, i) => `2026-11-11T${String(9 + Math.floor((30 + i * 5) / 60)).padStart(2, "0")}:${String((30 + i * 5) % 60).padStart(2, "0")}:00`)
  const ms = (s: string) => new Date(s).getTime()
  const step = 5 * 60_000

  it("adds right space after the last candle when the view reaches it", () => {
    expect(xWindowMs(t, null, 60 * 60_000, 3)).toEqual([ms(t[19]) - 60 * 60_000, ms(t[19]) + 3 * step])
  })

  it("a view panned into the middle ends exactly where it was left", () => {
    const view = { start: ms(t[2]), end: ms(t[8]) }
    expect(xWindowMs(t, view, 60 * 60_000, 3)).toEqual([ms(t[2]), ms(t[8])])
  })

  it("the space is one bar interval each, not the average gap across a break", () => {
    const withBreak = [...t, "2026-11-12T09:30:00", "2026-11-12T09:35:00"]
    const [, end] = xWindowMs(withBreak, null, 60 * 60_000, 2)!
    expect(end).toBe(ms("2026-11-12T09:35:00") + 2 * step)
  })

  it("a view dragged past the first bar stops there and keeps its width", () => {
    const width = 20 * 60_000
    const view = { start: ms(t[0]) - 3 * 3_600_000, end: ms(t[0]) - 3 * 3_600_000 + width }
    expect(xWindowMs(t, view, 60 * 60_000, 3)).toEqual([ms(t[0]), ms(t[0]) + width])
  })
})
