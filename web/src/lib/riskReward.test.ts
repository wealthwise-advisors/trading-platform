import { describe, expect, it } from "vitest"
import { riskReward } from "./riskReward"

const ES = { tickSize: 0.25, tickValue: 12.5 }

describe("risk / reward", () => {
  it("a long on ES: dollars from ticks, ratio and share of the account", () => {
    const r = riskReward({ entry: 6900, stop: 6895, target: 6915, contracts: 2, account: 100_000, ...ES })!
    expect(r.riskTicks).toBe(20)
    expect(r.rewardTicks).toBe(60)
    expect(r.risk).toBe(500)                // 20 ticks x $12.50 x 2
    expect(r.reward).toBe(1500)
    expect(r.ratio).toBe(3)
    expect(r.riskPct).toBeCloseTo(0.5)
    expect(r.side).toBe("long")
  })
  it("a short is the mirror", () => {
    const r = riskReward({ entry: 6900, stop: 6904, target: 6890, contracts: 1, account: 50_000, ...ES })!
    expect(r.side).toBe("short")
    expect(r.risk).toBe(200)
    expect(r.reward).toBe(500)
    expect(r.ratio).toBe(2.5)
  })
  it("off-tick prices round to whole ticks, as the exchange would", () => {
    const r = riskReward({ entry: 6900, stop: 6899.1, target: 6901, contracts: 1, account: 0, ...ES })!
    expect(r.riskTicks).toBe(4)
    expect(r.riskPct).toBeNull()             // no account size given
  })
  it("a stop and target on the same side, or missing numbers, give no answer", () => {
    expect(riskReward({ entry: 6900, stop: 6905, target: 6910, contracts: 1, account: 1, ...ES })).toBeNull()
    expect(riskReward({ entry: 6900, stop: 6900, target: 6910, contracts: 1, account: 1, ...ES })).toBeNull()
    expect(riskReward({ entry: NaN, stop: 6895, target: 6910, contracts: 1, account: 1, ...ES })).toBeNull()
    expect(riskReward({ entry: 6900, stop: 6895, target: 6910, contracts: 0, account: 1, ...ES })).toBeNull()
  })
})
