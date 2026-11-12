import { describe, expect, it } from "vitest"
import { pointLines, pointsAt, swingStarts, type SwingPointInfo } from "./swingPoints"

const P: SwingPointInfo[] = [
  { t: "2026-11-11T10:05:00", level: "3 Leg", label: "ii", type: "L", price: 7601.25 },
  { t: "2026-11-11T10:05:00", level: "10 Leg", label: "3", type: "L", price: 7601.25 },
  { t: "2026-11-11T10:09:00", level: "3 Leg", label: "iii", type: "H", price: 7612 },
]

describe("pointsAt", () => {
  it("finds the points on the hovered bar", () => {
    expect(pointsAt(P, "2026-11-11T10:05:00", []).map((p) => p.label)).toEqual(["ii", "3"])
  })

  it("nothing on a bar without a point", () => {
    expect(pointsAt(P, "2026-11-11T10:06:00", [])).toEqual([])
  })

  it("on merged candles, a point anywhere in the hovered candle counts", () => {
    const candles = ["2026-11-11T10:04:00", "2026-11-11T10:08:00"]
    expect(pointsAt(P, "2026-11-11T10:10:00", candles).map((p) => p.label)).toEqual(["iii"])
  })
})

describe("pointLines", () => {
  it("names each point, 10 Leg first, with high or low and the price", () => {
    const lines = pointLines(pointsAt(P, "2026-11-11T10:05:00", []))
    expect(lines[0]).toMatchObject({ kind: "heading", label: "Swing point on this candle" })
    expect(lines.slice(1).map((l) => `${l.label} | ${l.value}`)).toEqual([
      "10 Leg point 3 | Low 7601.25",
      "3 Leg point ii | Low 7601.25",
    ])
  })

  it("no lines when the candle has no point", () => expect(pointLines([])).toEqual([]))
})

describe("swingStarts", () => {
  const Z = [
    { t: "2026-11-11T09:45:00", price: 7593.25, type: "L", swing: 1, label: "0" },
    { t: "2026-11-11T10:05:00", price: 7620, type: "H", swing: 1, label: "1" },
    { t: "2026-11-11T10:20:00", price: 7610, type: "L", swing: 1, label: "2" },
    { t: "2026-11-11T11:00:00", price: 7590, type: "L", swing: 2, label: "1" },
    { t: "2026-11-11T11:20:00", price: 7600, type: "H", swing: 2, label: "2" },
  ]

  it("the first swing starts at 0 and climbs when its 1 is a high", () => {
    expect(swingStarts(Z)[0]).toEqual({ swing: 1, t: "2026-11-11T09:45:00", price: 7593.25, type: "L", up: true })
  })

  it("a later swing starts at its point 1, falling when 1 is a low", () => {
    expect(swingStarts(Z)[1]).toEqual({ swing: 2, t: "2026-11-11T11:00:00", price: 7590, type: "L", up: false })
  })
})
