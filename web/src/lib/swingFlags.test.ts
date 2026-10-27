import { describe, expect, it } from "vitest"
import { flaggedSwings, swingFlagText, swingMoment, type PocAverageAnswer } from "./swingFlags"

describe("swingMoment", () => {
  it("is the swing bar's CLOSE: open + the chart's bar length", () => {
    expect(swingMoment("2026-10-23T09:35:00", 5)).toBe("2026-10-23T09:40:00")
    expect(swingMoment("2026-10-23T23:30:00", 60)).toBe("2026-10-24T00:30:00")
  })
  it("keeps a timestamp with no seconds readable", () => {
    expect(swingMoment("2026-10-23T09:35", 1)).toBe("2026-10-23T09:36:00")
  })
})

describe("flaggedSwings", () => {
  const pts = [
    { t: "2026-10-23T09:35:00", label: "A" },
    { t: "2026-10-23T10:00:00", label: "B" },
    { t: "2026-10-23T10:20:00", label: "c" },
  ]
  const answer: PocAverageAnswer = {
    timeframes: ["5m", "15m"],
    moments: [
      { t: "2026-10-23T09:40:00", average: 7689.17, pocs: { "5m": 7689.54, "15m": 7688.8 }, matches: ["5m"] },
      { t: "2026-10-23T10:05:00", average: 7690.2, pocs: { "5m": 7691.1, "15m": 7689.3 }, matches: [] },
      { t: "2026-10-23T10:25:00", average: null, pocs: {}, matches: [] },
    ],
  }

  it("flags only swings where some timeframe's POC is on the average", () => {
    const f = flaggedSwings(pts, 5, answer)
    expect([...f.keys()]).toEqual(["2026-10-23T09:35:00"])
    expect(f.get("2026-10-23T09:35:00")!.matches).toEqual([{ tf: "5m", poc: 7689.54 }])
    expect(f.get("2026-10-23T09:35:00")!.average).toBe(7689.17)
  })

  it("is empty without an answer yet", () => {
    expect(flaggedSwings(pts, 5, undefined).size).toBe(0)
  })
})

describe("swingFlagText", () => {
  it("names the average and every timeframe on it, for the hover popup", () => {
    expect(swingFlagText({
      average: 7689.17,
      matches: [{ tf: "5m", poc: 7689.54 }, { tf: "15m", poc: 7689.02 }],
    })).toBe("⚑ POC Average 7689.17 — on it: 5m 7689.54, 15m 7689.02")
  })
})
