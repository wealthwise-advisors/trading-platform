import { describe, expect, it } from "vitest"
import { FIB_RATIOS, fibLabel, fibLevels, fibShapes, lastDrawingSize } from "./fibonacci"

describe("fibLevels", () => {
  it("a drag from a low of 100 up to a high of 200", () => {
    const prices = Object.fromEntries(fibLevels(100, 200).map((l) => [l.ratio, l.price]))
    expect(prices[0]).toBe(200)
    expect(prices[0.5]).toBe(150)
    expect(prices[0.618]).toBeCloseTo(138.2)
    expect(prices[1]).toBe(100)
  })

  it("a drag down measures the other way", () => {
    expect(fibLevels(200, 100).find((l) => l.ratio === 0.618)!.price).toBeCloseTo(161.8)
  })

  it("thinkorswim's standard ratios", () => {
    expect(FIB_RATIOS).toEqual([0, 0.236, 0.382, 0.5, 0.618, 0.786, 1])
  })
})

describe("fibLabel", () => {
  it.each([
    [{ ratio: 0.618, price: 7568.25 }, "61.8%  7,568.25"],
    [{ ratio: 0.5, price: 7500 }, "50%  7,500.00"],
    [{ ratio: 0, price: 1 }, "0%  1.00"],
  ])("%o", (level, want) => expect(fibLabel(level)).toBe(want))
})

describe("fibShapes", () => {
  const drag = { x0: "2026-11-09T11:00:00", x1: "2026-11-09T10:00:00", y0: 100, y1: 200 }

  it("one level line per ratio, all one drawing", () => {
    const shapes = fibShapes(drag, 7)!
    expect(shapes).toHaveLength(7)
    expect(new Set(shapes.map((s) => s.name))).toEqual(new Set(["fib-7"]))
    expect(shapes.map((s) => s.y0)).toEqual(fibLevels(100, 200).map((l) => l.price))
    expect(shapes.every((s) => s.y0 === s.y1)).toBe(true)
  })

  it("runs from the earlier time, and on to the last bar", () => {
    const [s] = fibShapes(drag, 1, "2026-11-09T15:59:00")!
    expect([s.x0, s.x1]).toEqual(["2026-11-09T10:00:00", "2026-11-09T15:59:00"])
  })

  it("never ends before the drag does", () => {
    const [s] = fibShapes(drag, 1, "2026-11-09T09:00:00")!
    expect(s.x1).toBe("2026-11-09T11:00:00")
  })

  it("a flat or broken drag draws nothing", () => {
    expect(fibShapes({ ...drag, y1: 100 }, 1)).toBeNull()
    expect(fibShapes({ ...drag, y1: "x" }, 1)).toBeNull()
  })
})

describe("lastDrawingSize", () => {
  it("a Fibonacci drawing is undone whole", () => {
    expect(lastDrawingSize([{ name: "fib-1" }, { name: "fib-2" }, { name: "fib-2" }])).toBe(2)
  })

  it("anything else one shape at a time", () => {
    expect(lastDrawingSize([{ name: "fib-1" }, {}])).toBe(1)
    expect(lastDrawingSize([{}, {}])).toBe(1)
    expect(lastDrawingSize([])).toBe(0)
  })
})
