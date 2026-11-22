import { describe, expect, it } from "vitest"
import { efficiencyNote } from "./research"

describe("walk-forward efficiency, in words", () => {
  it("names each band", () => {
    expect(efficiencyNote(null)).toMatch(/no money/)
    expect(efficiencyNote(0.8)).toMatch(/mostly carried over/)
    expect(efficiencyNote(0.2)).toMatch(/Only part/)
    expect(efficiencyNote(-0.3)).toMatch(/did not carry over/)
  })
})
