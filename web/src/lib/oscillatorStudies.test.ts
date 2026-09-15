import { describe, expect, it } from "vitest"
import {
  OSC_ORDER, OSC_STUDIES, activeOscillatorRows, levelLines, oscillatorRowHeights,
} from "./oscillatorStudies"

const ALL_ON = { rsi2: true, stoch: true, rsi13: true, mfi: true }

describe("pending decisions stay undecided", () => {
  it("level lines are exactly what the chart drew before: 94/2, 80/20, 70/30", () => {
    expect(OSC_STUDIES.rsi2.levels).toEqual({ overbought: 94, oversold: 2 })
    expect(OSC_STUDIES.stoch.levels).toEqual({ overbought: 80, oversold: 20 })
    expect(OSC_STUDIES.rsi13.levels).toEqual({ overbought: 70, oversold: 30 })
  })

  it("the Stochastic panel is still a Stochastic, not StochRSI", () => {
    expect(OSC_STUDIES.stoch.label).toBe("Stochastic")
  })

  it("MFI is listed but unavailable, with a reason and no levels", () => {
    expect(OSC_STUDIES.mfi.available).toBe(false)
    expect(OSC_STUDIES.mfi.levels).toBeNull()
    expect(OSC_STUDIES.mfi.pending).toMatch(/not built yet/)
  })
})

describe("activeOscillatorRows", () => {
  it("keeps the reference order and never gives MFI a row", () => {
    expect(OSC_ORDER).toEqual(["rsi2", "stoch", "rsi13", "mfi"])
    expect(activeOscillatorRows(ALL_ON)).toEqual(["rsi2", "stoch", "rsi13"])
  })

  it("drops whatever is switched off", () => {
    expect(activeOscillatorRows({ ...ALL_ON, stoch: false })).toEqual(["rsi2", "rsi13"])
    expect(activeOscillatorRows({ rsi2: false, stoch: false, rsi13: false, mfi: true })).toEqual([])
  })
})

describe("oscillatorRowHeights", () => {
  it("price takes the whole chart when every oscillator is off", () => {
    expect(oscillatorRowHeights(0)).toEqual([1])
  })

  it.each([1, 2, 3])("%i rows: price keeps 0.68 and the rest splits evenly", (n) => {
    const h = oscillatorRowHeights(n)
    expect(h.length).toBe(1 + n)
    expect(h[0]).toBe(0.68)
    expect(h.slice(1).every((x) => Math.abs(x - 0.32 / n) < 1e-12)).toBe(true)
    expect(h.every(Number.isFinite)).toBe(true)
    expect(Math.abs(h.reduce((a, b) => a + b, 0) - 1)).toBeLessThan(1e-12)
  })
})

describe("levelLines", () => {
  it("only for rows being drawn", () => {
    expect(levelLines(["rsi13"])).toEqual([
      { row: "rsi13", value: 70, kind: "overbought" },
      { row: "rsi13", value: 30, kind: "oversold" },
    ])
    expect(levelLines([])).toEqual([])
  })
})
