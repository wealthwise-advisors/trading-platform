import { describe, expect, it } from "vitest"
import { cvdDivergences, cvdSession } from "./cvdDivergence"
import type { ZigZagPoint } from "./types"

const pt = (t: string, price: number, type: "H" | "L"): ZigZagPoint =>
  ({ t, price, type, swing: 1, sub: 0, label: "1" })

// Five bars; the swing points sit on bars 1 and 3.
const T = ["2026-11-24T10:10:00", "2026-11-24T10:15:00", "2026-11-24T10:30:00", "2026-11-24T10:45:00", "2026-11-24T10:50:00"]
const AVG = [600, 600, 600, 600, 600]

describe("cvdDivergences — sir's four kinds", () => {
  it("his example: higher low in price, lower low in CVD -> Hidden Bullish, strength 3.75 (strong)", () => {
    // Swing Low 1: 7,210.00, CVD +1,400. Swing Low 2: 7,214.50, CVD -850.
    const cvd = [0, 1400, 0, -850, 0]
    const [d] = cvdDivergences([pt(T[1], 7210, "L"), pt(T[3], 7214.5, "L")], T, cvd, AVG)
    expect(d.kind).toBe("Hidden Bullish")
    expect(d.dPrice).toBe(4.5)
    expect(d.dCvd).toBe(-2250)
    expect(d.strength).toBe(3.75)
    expect(d.strong).toBe(true)
  })

  it.each([
    ["L", 7200, 7190, -900, 0, "Regular Bullish"],
    ["H", 7300, 7290, 0, 1200, "Hidden Bearish"],
    ["H", 7300, 7310, 1200, 0, "Regular Bearish"],
  ] as const)("%s %d -> %d with CVD %d -> %d is %s", (type, p1, p2, c1, c2, kind) => {
    const cvd = [0, c1, 0, c2, 0]
    const out = cvdDivergences([pt(T[1], p1, type), pt(T[3], p2, type)], T, cvd, AVG)
    expect(out.map((d) => d.kind)).toEqual([kind])
  })

  it("price and CVD moving the same way is no divergence", () => {
    expect(cvdDivergences([pt(T[1], 7200, "L"), pt(T[3], 7210, "L")], T, [0, 100, 0, 2000, 0], AVG)).toEqual([])
  })

  it("weak ones (strength under 1.5) are skipped, 1.5 to 3 kept but not strong", () => {
    const pts = [pt(T[1], 7210, "L"), pt(T[3], 7214, "L")]
    expect(cvdDivergences(pts, T, [0, 0, 0, -600, 0], AVG)).toEqual([])            // 1.0
    const [mid] = cvdDivergences(pts, T, [0, 0, 0, -1200, 0], AVG)                 // 2.0
    expect(mid.strength).toBe(2)
    expect(mid.strong).toBe(false)
  })

  it("two points in different CVD sessions are not compared", () => {
    const t = ["2026-11-24T07:50:00", "2026-11-24T08:10:00"]
    expect(cvdDivergences([pt(t[0], 7210, "L"), pt(t[1], 7214, "L")], t, [3000, -3000], [600, 600])).toEqual([])
  })
})

describe("cvdSession", () => {
  it("6 PM, midnight and 8 AM Eastern start sessions; 4-5 PM stays in the day one", () => {
    expect(cvdSession("2026-11-24T17:59:00")).toBe(cvdSession("2026-11-24T08:00:00"))
    expect(cvdSession("2026-11-24T18:00:00")).not.toBe(cvdSession("2026-11-24T17:59:00"))
    expect(cvdSession("2026-11-25T00:00:00")).not.toBe(cvdSession("2026-11-24T23:59:00"))
    expect(cvdSession("2026-11-24T07:59:00")).not.toBe(cvdSession("2026-11-24T08:00:00"))
  })

  it("undoes the chart's time zone: 7:00 AM Central is 8:00 AM Eastern", () => {
    expect(cvdSession("2026-11-24T07:00:00", -60)).toBe(cvdSession("2026-11-24T08:00:00"))
  })
})
