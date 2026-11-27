// The browser's oscillators must equal the server's (src/analysis/indicators.py).
// oscCalc.fixture.json was written by calc_rsi / calc_stochrsi / calc_mfi on a
// random 60-bar series, at NON-default lengths -- the case these functions exist for.
import { describe, expect, it } from "vitest"
import { mfi, rsi, stochRsi } from "./oscCalc"
import fx from "./oscCalc.fixture.json"

const near = (a: (number | null)[], b: (number | null)[]) => {
  expect(a.length).toBe(b.length)
  a.forEach((v, i) => {
    if (b[i] == null) expect(v).toBeNull()
    else expect(v!).toBeCloseTo(b[i]!, 5)
  })
}

describe("oscillators match the server", () => {
  it("RSI(3) and RSI(7)", () => { near(rsi(fx.c, 3), fx.rsi3); near(rsi(fx.c, 7), fx.rsi7) })
  it("StochRSI(5) over 6, slowing 2, D 3", () => {
    const { k, d } = stochRsi(fx.c, 5, 6, 3, 2)
    near(k, fx.k); near(d, fx.d)
  })
  it("MFI(5)", () => {
    near(mfi(fx.c.map((c, i) => ({ c, h: fx.h[i], l: fx.l[i], v: fx.v[i] })), 5), fx.mfi5)
  })
})
