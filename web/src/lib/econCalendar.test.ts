import { describe, expect, it } from "vitest"
import { chartMarks, eventsInRange, nextHighImpact, shortLabel, type EconEvent } from "./econCalendar"

const ev = (at: string, impact: EconEvent["impact"] = "high", title = "FOMC statement"): EconEvent =>
  ({ uid: at, source: "FOMC", title, at, impact, note: "" })

describe("economic events on the chart", () => {
  it("keeps the events inside the bars, low impact left off", () => {
    const list = [ev("2026-11-18T14:00"), ev("2026-11-19T08:30", "low"), ev("2026-11-25T08:30"), ev("2026-11-19T10:00", "medium")]
    expect(eventsInRange(list, "2026-11-18T09:30:00", "2026-11-20T16:00:00").map((e) => e.at))
      .toEqual(["2026-11-18T14:00", "2026-11-19T10:00"])
  })
  it("a short label for the top of the line", () => {
    expect(shortLabel(ev("2026-11-18T14:00", "high", "FOMC statement and economic projections"))).toBe("FOMC 14:00")
    expect(shortLabel({ ...ev("2026-11-26T08:30", "high", "Gross Domestic Product, 3rd Quarter 2026"), source: "BEA" })).toBe("GDP 08:30")
    expect(shortLabel({ ...ev("2026-11-26T08:30", "high", "Personal Income and Outlays, October 2026"), source: "BEA" })).toBe("PCE 08:30")
  })
})

describe("the next high-impact event", () => {
  const list = [ev("2026-11-22T13:00"), ev("2026-11-22T15:00", "medium"), ev("2026-11-23T08:30")]
  it("the soonest high one ahead, with minutes to go", () => {
    expect(nextHighImpact(list, "2026-11-22T13:30:00")).toEqual({ event: list[2], minutes: 1140 })
  })
  it("nothing beyond 24 hours", () => {
    expect(nextHighImpact(list, "2026-11-21T14:00:00")).toEqual({ event: list[0], minutes: 1380 })
    expect(nextHighImpact(list, "2026-11-21T08:00:00")).toBeNull()                    // 29 h ahead
    expect(nextHighImpact([ev("2026-11-30T08:30")], "2026-11-22T08:00:00")).toBeNull()
  })
})

describe("events at the same minute", () => {
  it("share one line and one label, the highest impact winning", () => {
    const a = { ...ev("2026-11-25T08:30", "high", "GDP (Second Estimate), 3rd Quarter 2026"), source: "BEA" }
    const b = { ...ev("2026-11-25T08:30", "medium", "U.S. International Trade in Goods and Services, October 2026"), source: "BEA" }
    const c = ev("2026-11-25T14:00")
    const g = chartMarks([a, b, c], "2026-11-25T00:00:00", "2026-11-26T00:00:00")
    expect(g).toEqual([
      { at: "2026-11-25T08:30", impact: "high", label: "GDP, Trade 08:30", titles: [a.title, b.title] },
      { at: "2026-11-25T14:00", impact: "high", label: "FOMC 14:00", titles: ["FOMC statement"] },
    ])
  })
})
