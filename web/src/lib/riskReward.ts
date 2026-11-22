/**
 * Risk / reward of a planned trade (upgrade plan, Feature 5), from the contract's own
 * tick: what the stop costs, what the target pays, the ratio, and the risk as a share
 * of the account. Prices off the tick grid round to whole ticks, as an order would.
 */
export interface RRInput {
  entry: number; stop: number; target: number
  contracts: number; account: number
  tickSize: number; tickValue: number
}

export interface RR {
  side: "long" | "short"
  riskTicks: number; rewardTicks: number
  risk: number; reward: number
  ratio: number
  /** Percent of the account the stop risks; null without an account size. */
  riskPct: number | null
}

export function riskReward(i: RRInput): RR | null {
  const nums = [i.entry, i.stop, i.target, i.contracts, i.tickSize, i.tickValue]
  if (nums.some((n) => !Number.isFinite(n)) || i.contracts <= 0 || i.tickSize <= 0) return null
  const long = i.stop < i.entry && i.target > i.entry
  const short = i.stop > i.entry && i.target < i.entry
  if (!long && !short) return null
  const riskTicks = Math.round(Math.abs(i.entry - i.stop) / i.tickSize)
  const rewardTicks = Math.round(Math.abs(i.target - i.entry) / i.tickSize)
  if (!riskTicks) return null
  const risk = riskTicks * i.tickValue * i.contracts
  const reward = rewardTicks * i.tickValue * i.contracts
  return {
    side: long ? "long" : "short", riskTicks, rewardTicks, risk, reward,
    ratio: Math.round((reward / risk) * 100) / 100,
    riskPct: i.account > 0 ? (risk / i.account) * 100 : null,
  }
}
