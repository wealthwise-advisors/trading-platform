import { describe, expect, it } from "vitest"
import {
  OSC_ORDER, OSC_STUDIES, activeOscillatorRows, levelLines, oscillatorRowHeights,
} from "./oscillatorStudies"

const ALL_ON = { rsi2: true, stochrsi: true, rsi13: true, mfi: true }

describe("confirmed settings", () => {
  it("RSI levels stay 94/2 and 70/30, not the reference platform's 5 and 55/45", () => {
    expect(OSC_STUDIES.rsi2.levels).toEqual({ overbought: 94, oversold: 2 })
    expect(OSC_STUDIES.rsi13.levels).toEqual({ overbought: 70, oversold: 30 })
  })

  it("the third panel is StochRSI: RSI 14, K 3, D 3, Wilder's, 80/20", () => {
    const s = OSC_STUDIES.stochrsi
    expect(s.label).toBe("StochRSI")
    expect(Object.fromEntries(s.inputs)).toEqual({
      "RSI length": "14", "stochastic length": "14", "K period": "3", "D period": "3",
      "RSI average": "Wilder's", "K/D average": "Wilder's",
    })
    expect(s.levels).toEqual({ overbought: 80, oversold: 20 })
  })

  it("MFI is listed but unavailable, with a reason and no levels", () => {
    expect(OSC_STUDIES.mfi.available).toBe(false)
    expect(OSC_STUDIES.mfi.levels).toBeNull()
    expect(OSC_STUDIES.mfi.pending).toMatch(/not built yet/)
  })
})

describe("activeOscillatorRows", () => {
  it("keeps the reference order and never gives an unbuilt study a row", () => {
    expect(OSC_ORDER).toEqual(["rsi2", "stochrsi", "rsi13", "mfi"])
    expect(activeOscillatorRows(ALL_ON)).toEqual(["rsi2", "stochrsi", "rsi13"])
  })

  it("drops whatever is switched off", () => {
    expect(activeOscillatorRows({ ...ALL_ON, stochrsi: false })).toEqual(["rsi2", "rsi13"])
    expect(activeOscillatorRows({ rsi2: false, stochrsi: false, rsi13: false, mfi: true })).toEqual([])
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
    expect(levelLines(["stochrsi"])).toEqual([
      { row: "stochrsi", value: 80, kind: "overbought" },
      { row: "stochrsi", value: 20, kind: "oversold" },
    ])
    expect(levelLines([])).toEqual([])
  })
})
