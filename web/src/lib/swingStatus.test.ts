import { describe, expect, it } from "vitest"
import { statusLines, swingStatus } from "./swingStatus"
import type { ZigZagPoint } from "./types"

const P = (t: string, price: number, type: "H" | "L", swing: number, label: string, structure?: string): ZigZagPoint =>
  ({ t, price, type, swing, sub: 0, label, structure })

describe("swingStatus", () => {
  it("an up swing is protected by its last even low", () => {
    const st = swingStatus([P("09:30", 100, "L", 1, "0"), P("10:00", 110, "H", 1, "1", "H"),
                            P("10:30", 105, "L", 1, "2", "HL"), P("11:00", 115, "H", 1, "3", "HH")])!
    expect(st).toMatchObject({ name: "A", up: true, protectedPrice: 105, protectedLabel: "point 2" })
    expect(st.lastOdd?.price).toBe(115)
  })

  it("before any even point, the swing's start protects it", () => {
    const st = swingStatus([P("09:30", 100, "L", 1, "0"), P("10:00", 110, "H", 1, "1")])!
    expect(st).toMatchObject({ protectedPrice: 100, protectedLabel: "start" })
  })

  it("a later down swing starts from the top of the swing before it", () => {
    const st = swingStatus([P("09:30", 100, "L", 1, "0"), P("10:00", 110, "H", 1, "1"),
                            P("10:30", 95, "L", 2, "1")])!
    expect(st).toMatchObject({ name: "B", up: false, protectedPrice: 110, protectedLabel: "start" })
  })

  it("says in words what ends the swing and what the next point needs", () => {
    const st = swingStatus([P("09:30", 100, "L", 1, "0"), P("10:00", 110, "H", 1, "1", "H"),
                            P("10:30", 105, "L", 1, "2", "HL")])!
    expect(statusLines(st)).toEqual([
      "<b>Swing A ▲ up</b>",
      "Last 10 Leg point: 2 (HL) · Low 105.00",
      "Swing ends on a close at or below 105.00 (point 2)",
      "Next high must close above 110.00",
    ])
  })

  it("no points, no panel", () => expect(swingStatus([])).toBeNull())
})
