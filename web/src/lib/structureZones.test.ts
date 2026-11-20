import { describe, expect, it } from "vitest"
import { avgWord, priceZone } from "./structureZones"

describe("avgWord", () => {
  it.each([["above", "High"], ["below", "Low"], ["equal", "Neutral"]] as const)("%s -> %s", (side, word) => {
    expect(avgWord(side)).toBe(word)
  })
})

describe("priceZone -- where the price sits, in sir's words", () => {
  const lv = { vah: 7450, val: 7400, vwap: 7430 }
  it.each([
    [7455, "Buy / Reversal"], [7450, "Buy / Reversal"], [7440, "Breakout"], [7430, "Breakout"],
    [7420, "No trade"], [7400, "Short / Reversal"], [7390, "Short / Reversal"],
  ] as const)("close %s -> %s", (close, word) => {
    expect(priceZone(close, lv)!.word).toBe(word)
  })
  it("a missing level gives no zone", () => {
    expect(priceZone(7420, { vah: 7450, val: null, vwap: 7430 })).toBeNull()
    expect(priceZone(null, lv)).toBeNull()
  })
})
