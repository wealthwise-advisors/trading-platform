import { describe, expect, it } from "vitest"
import { swingName, titleLevel, titleWidthPx, type PlacedTitle } from "./swingHeaders"

describe("titleWidthPx", () => {
  it("measures the longest line, ignoring markup", () => {
    const html = '<b>Swing 5</b>  <span style="color:#0f0">▲ BUYERS 63%</span><br>10 Leg Dev (A to C) | 3 Leg Dev (a to k)'
    expect(titleWidthPx(html)).toBeCloseTo("10 Leg Dev (A to C) | 3 Leg Dev (a to k)".length * 5.6 + 10)
  })
})

describe("titleLevel", () => {
  const W = 230

  it("titles far enough apart share the base row", () => {
    const placed: PlacedTitle[] = [{ xPx: 100, widthPx: W, level: 0 }]
    expect(titleLevel(placed, 100 + W + 20, W)).toBe(0)
  })

  it("a title moves up only when it would really overlap", () => {
    const placed: PlacedTitle[] = [{ xPx: 100, widthPx: W, level: 0 }]
    expect(titleLevel(placed, 100 + W - 30, W)).toBe(1)
  })

  it("narrow titles close together still fit on one row", () => {
    const placed: PlacedTitle[] = [{ xPx: 100, widthPx: 60, level: 0 }]
    expect(titleLevel(placed, 180, 60)).toBe(0)
  })

  it("a dense run alternates between two rows, never climbs", () => {
    const placed: PlacedTitle[] = []
    for (const x of [0, 120, 240, 360, 480]) placed.push({ xPx: x, widthPx: W, level: titleLevel(placed, x, W) })
    expect(placed.map((p) => p.level).every((l) => l === 0 || l === 1)).toBe(true)
  })

  it("the first title always sits on the base row", () => expect(titleLevel([], 50, W)).toBe(0))
})

describe("swingName", () => {
  it("names swings with capital letters", () => {
    expect([1, 2, 3, 26, 27, 28].map(swingName)).toEqual(["A", "B", "C", "Z", "AA", "AB"])
  })
})
