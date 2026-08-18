import { describe, it, expect } from "vitest"
import { bandAgreement, agreeingLabels, wholePart } from "./bandAgreement"

// The numbers below are the real tape values from 2026-08-14 07:30 CT that
// prompted this feature, so the test fails if the rule ever stops matching
// what was actually on screen.
//
//            Upper+1.0  Lower-1.0  Upper+2.0  Lower-2.0
//   30m       7827.98    7823.37    7830.28    7821.07
//   45m       7827.99    7823.58    7830.19    7821.37
//   1h        7827.74    7823.62    7829.80    7821.56
const LABELS = ["30m", "45m", "1h"]
const ROWS = [
  [7827.98, 7823.37, 7830.28, 7821.07],
  [7827.99, 7823.58, 7830.19, 7821.37],
  [7827.74, 7823.62, 7829.8, 7821.56],
]

describe("wholePart", () => {
  it("keeps only the digits before the decimal", () => {
    expect(wholePart(7830.28)).toBe(7830)
    expect(wholePart(7829.8)).toBe(7829)
    expect(wholePart(7830)).toBe(7830)
  })

  it("truncates toward zero rather than flooring", () => {
    expect(wholePart(-1.7)).toBe(-1)
  })
})

describe("bandAgreement on the real tape row", () => {
  const agreement = bandAgreement(ROWS, LABELS)

  it("finds all three timeframes agreeing on Upper +1σ = 7827", () => {
    expect(agreement[0].get(7827)).toEqual(["30m", "45m", "1h"])
  })

  it("finds all three agreeing on Lower -1σ = 7823", () => {
    expect(agreement[1].get(7823)).toEqual(["30m", "45m", "1h"])
  })

  it("finds only 30m and 45m agreeing on Upper +2σ = 7830", () => {
    expect(agreement[2].get(7830)).toEqual(["30m", "45m"])
  })

  it("leaves the 1h Upper +2σ alone — 7829 stands by itself", () => {
    expect(agreement[2].get(7829)).toEqual(["1h"])
    expect(agreeingLabels(agreement, 2, 7829.8, "1h")).toEqual([])
  })

  it("reports the OTHER timeframes for a highlighted cell", () => {
    expect(agreeingLabels(agreement, 2, 7830.28, "30m")).toEqual(["45m"])
    expect(agreeingLabels(agreement, 0, 7827.98, "30m")).toEqual(["45m", "1h"])
  })
})

describe("edge cases", () => {
  it("never highlights when only one timeframe is shown", () => {
    const a = bandAgreement([[7827.98, 7823.37]], ["30m"])
    expect(agreeingLabels(a, 0, 7827.98, "30m")).toEqual([])
  })

  it("ignores nulls — a pane with no VWAP yet cannot agree", () => {
    const a = bandAgreement([[null, 7823.37], [7827.99, 7823.58]], ["30m", "45m"])
    expect(a[0].size).toBe(1)
    expect(agreeingLabels(a, 0, null, "30m")).toEqual([])
  })

  it("ignores NaN rather than letting it group with itself", () => {
    const a = bandAgreement([[NaN], [NaN]], ["30m", "45m"])
    expect(a[0].size).toBe(0)
  })

  it("does not treat adjacent whole numbers as agreeing", () => {
    // 0.02 apart, but across a whole-number boundary.
    const a = bandAgreement([[7829.99], [7830.01]], ["30m", "45m"])
    expect(agreeingLabels(a, 0, 7829.99, "30m")).toEqual([])
  })

  it("handles ragged rows without crashing", () => {
    const a = bandAgreement([[7827.1, 7823.1], [7827.2]], ["30m", "45m"])
    expect(a[0].get(7827)).toEqual(["30m", "45m"])
    expect(a[1].get(7823)).toEqual(["30m"])
  })

  it("scales to more levels and timeframes than the example", () => {
    const rows = [
      [7827.1, 7823.1, 7830.1, 7821.1, 7833.1, 7818.1],
      [7827.9, 7823.9, 7830.9, 7821.9, 7834.9, 7818.9],
    ]
    const a = bandAgreement(rows, ["30m", "1h"])
    expect(a).toHaveLength(6)
    expect(agreeingLabels(a, 4, 7833.1, "30m")).toEqual([])   // 7833 vs 7834
    expect(agreeingLabels(a, 5, 7818.1, "30m")).toEqual(["1h"])
  })
})
