import { describe, expect, it } from "vitest"
import { delta, price } from "./priceFormat"

describe("price — the reference platform's display convention", () => {
  it("keeps two decimals when there are two", () => {
    expect(price(7809.89)).toBe("7809.89")
    expect(price(7816.25)).toBe("7816.25")
    expect(price(7824.87)).toBe("7824.87")
  })

  it("strips a single trailing zero", () => {
    // thinkorswim printed 7794.90 as "7794.9"
    expect(price(7794.9)).toBe("7794.9")
    expect(price(7814.5)).toBe("7814.5")
  })

  it("strips the decimal point entirely on a whole number", () => {
    // printed as "7810", "7828", "7795", "7811" on the reference tooltips
    expect(price(7810)).toBe("7810")
    expect(price(7828)).toBe("7828")
    expect(price(7795)).toBe("7795")
    expect(price(7811)).toBe("7811")
  })

  it("rounds to two decimals before trimming, not after", () => {
    // 7809.8986 must not leak float noise into the display
    expect(price(7809.8986)).toBe("7809.9")
    expect(price(7825.99098)).toBe("7825.99")
    expect(price(7830.5976)).toBe("7830.6")
  })

  it("does NOT round to whole numbers", () => {
    // The change that was asked for and rejected: it would print the reference's
    // own 7809.89 as "7810" and make the two screens less alike, not more.
    expect(price(7809.89)).not.toBe("7810")
  })

  it("shows a dash for missing values rather than NaN or 0", () => {
    expect(price(null)).toBe("—")
    expect(price(undefined)).toBe("—")
    expect(price(NaN)).toBe("—")
  })
})

describe("delta", () => {
  it("signs the value and trims the same way", () => {
    expect(delta(2.5)).toBe("+2.5")
    expect(delta(-1.75)).toBe("-1.75")
    expect(delta(0)).toBe("+0")
    expect(delta(2.0)).toBe("+2")
  })

  it("dashes on missing", () => {
    expect(delta(null)).toBe("—")
  })
})
