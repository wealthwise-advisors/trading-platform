import { describe, expect, it } from "vitest"
import { innerTicks } from "./chartStyle"

describe("oscillator rows print their numbers inside the row, not on its edges", () => {
  it("a 0-100 row gets 20, 50, 80", () => expect(innerTicks([0, 100])).toEqual([20, 50, 80]))
  it("an auto-ranged row stays inside its own range", () => {
    const t = innerTicks([24.1, 58])
    expect(t).toEqual([31, 41, 51])
    expect(Math.min(...t)).toBeGreaterThan(24.1)
    expect(Math.max(...t)).toBeLessThan(58)
  })
})
