import { describe, expect, it } from "vitest"
import { arrowNote, channelShapes, measureShape, measureText } from "./drawingTools"
import type { OHLCVRecord } from "./types"

const T = (m: number) => `2026-11-09T10:${String(m).padStart(2, "0")}:00`
const times = [0, 1, 2, 3, 4, 5].map(T)

describe("measure", () => {
  it("points, percent and bars, either way round", () => {
    expect(measureText({ x0: T(0), x1: T(3), y0: 7500, y1: 7512.5 }, times)).toBe("+12.50 (+0.17%) · 3 bars")
    expect(measureText({ x0: T(3), x1: T(0), y0: 7512.5, y1: 7500 }, times)).toBe("-12.50 (-0.17%) · 3 bars")
  })

  it("one bar is singular", () => {
    expect(measureText({ x0: T(0), x1: T(1), y0: 1, y1: 2 }, times)).toContain("1 bar")
  })

  it("is drawn as a labelled line", () => {
    const s = measureShape({ x0: T(0), x1: T(2), y0: 10, y1: 11 }, times)!
    expect(s.type).toBe("line")
    expect((s.label as { text: string }).text).toContain("+1.00")
  })

  it("a broken drag draws nothing", () => {
    expect(measureShape({ x0: T(0), y0: 1, y1: 2 }, times)).toBeNull()
  })
})

describe("channel", () => {
  const bar = (m: number, h: number, l: number): OHLCVRecord => ({ t: T(m), o: l, h, l, c: h, v: 1 })

  it("a line along the lows gets a parallel through the highest bar above it", () => {
    const bars = [bar(0, 102, 100), bar(1, 106, 101), bar(2, 103, 102)]
    const [main, parallel] = channelShapes({ x0: T(0), x1: T(2), y0: 100, y1: 102 }, bars, 1)!
    expect(main.y0).toBe(100)
    expect(parallel.y0).toBe(105)
    expect(parallel.y1).toBe(107)
    expect(main.name).toBe(parallel.name)
  })

  it("a line along the highs gets one below", () => {
    const bars = [bar(0, 110, 108), bar(1, 109, 104), bar(2, 110, 109)]
    const [, parallel] = channelShapes({ x0: T(0), x1: T(2), y0: 110, y1: 110 }, bars, 1)!
    expect(parallel.y0).toBe(104)
  })

  it("drawn right to left, it is the same channel", () => {
    const bars = [bar(0, 102, 100), bar(1, 106, 101), bar(2, 103, 102)]
    const [main, parallel] = channelShapes({ x0: T(2), x1: T(0), y0: 102, y1: 100 }, bars, 1)!
    expect([main.x0, main.y0, parallel.y0]).toEqual([T(0), 100, 105])
  })

  it("no bars to measure against: just the line", () => {
    expect(channelShapes({ x0: T(0), x1: T(2), y0: 1, y1: 2 }, [], 1)).toHaveLength(1)
  })
})

describe("arrow", () => {
  it("points from the start of the drag to its end", () => {
    expect(arrowNote({ x0: T(0), x1: T(2), y0: 1, y1: 2 })).toMatchObject({ ax: T(0), ay: 1, x: T(2), y: 2, showarrow: true })
  })
})
