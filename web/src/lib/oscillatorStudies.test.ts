import { describe, expect, it } from "vitest"
import {
  OSC_ORDER, OSC_STUDIES, activeOscillatorRows, fittedRange, levelLines, oscillatorRowHeights, zoneOverlays,
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
    expect(Object.fromEntries(s.inputs)).toMatchObject({
      "RSI length": "14", "K period": "3", "D period": "3",
      "RSI average": "Wilder's", "K/D average": "Wilder's",
    })
    expect(s.levels).toEqual({ overbought: 80, oversold: 20 })
  })

  it("MFI is built: length 20, 80/20", () => {
    expect(OSC_STUDIES.mfi.available).toBe(true)
    expect(Object.fromEntries(OSC_STUDIES.mfi.inputs).length).toBe("20")
    expect(OSC_STUDIES.mfi.levels).toEqual({ overbought: 80, oversold: 20 })
  })
})

describe("activeOscillatorRows", () => {
  it("all four in the reference order: RSI(2), StochRSI, RSI(13), MFI", () => {
    expect(OSC_ORDER).toEqual(["rsi2", "stochrsi", "rsi13", "mfi"])
    expect(activeOscillatorRows(ALL_ON)).toEqual(["rsi2", "stochrsi", "rsi13", "mfi"])
  })

  it("drops whatever is switched off, keeping the rest in order", () => {
    expect(activeOscillatorRows({ ...ALL_ON, stochrsi: false })).toEqual(["rsi2", "rsi13", "mfi"])
    expect(activeOscillatorRows({ rsi2: false, stochrsi: false, rsi13: false, mfi: true })).toEqual(["mfi"])
    expect(activeOscillatorRows({ rsi2: false, stochrsi: false, rsi13: false, mfi: false })).toEqual([])
  })
})

describe("oscillatorRowHeights", () => {
  it("price takes the whole chart when every oscillator is off", () => {
    expect(oscillatorRowHeights(0)).toEqual([1])
  })

  it.each([1, 2, 3, 4])("%i rows: price keeps 0.68 and the rest splits evenly", (n) => {
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
    expect(levelLines(["mfi"])).toEqual([
      { row: "mfi", value: 80, kind: "overbought" },
      { row: "mfi", value: 20, kind: "oversold" },
    ])
    expect(levelLines([])).toEqual([])
  })
})

describe("zoneOverlays", () => {
  it("keeps the points in a zone and the one leading into it", () => {
    const { above, below } = zoneOverlays([50, 95, 96, 50, 1, 50], 94, 2)
    expect(above).toEqual([50, 95, 96, null, null, null])
    expect(below).toEqual([null, null, null, 50, 1, null])
  })

  it("gaps stay gaps", () => {
    expect(zoneOverlays([null, 99], 94, 2).above).toEqual([null, 99])
  })
})

describe("fittedRange", () => {
  const t = [0, 1, 2]

  it("fits the bars on screen with padding, inside 0-100", () => {
    expect(fittedRange([10, 50, 60], t, 1, 2)).toEqual([48, 62])
  })

  it("never leaves 0-100", () => expect(fittedRange([1, 99], [0, 1], 0, 1)).toEqual([0, 100]))
  it("nothing on screen is the full scale", () => expect(fittedRange([null], [0], 0, 1)).toEqual([0, 100]))
})
