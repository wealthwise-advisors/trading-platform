import { describe, it, expect } from "vitest"
import { assetClassOf } from "./SymbolMark"

/**
 * The mark's colour comes from the asset class, so a misclassification is not a
 * cosmetic slip -- it puts a gold bar next to an index future and the list stops
 * being scannable, which is the only reason the mark exists.
 */
describe("asset classification", () => {
  it("puts the index futures together", () => {
    for (const s of ["ES", "NQ", "YM", "RTY"]) {
      expect(assetClassOf(s)).toBe("index")
    }
  })

  it("separates micros from their full-size parent", () => {
    // MES must not read as ES: same glyph, but the class drives the corner dot
    // and the lighter blue that distinguish them in a list.
    expect(assetClassOf("MES")).toBe("micro")
    expect(assetClassOf("MNQ")).toBe("micro")
    expect(assetClassOf("ES")).toBe("index")
    expect(assetClassOf("NQ")).toBe("index")
  })

  it("groups energy and metals by what they are, not by exchange", () => {
    expect(assetClassOf("CL")).toBe("energy")
    expect(assetClassOf("NG")).toBe("energy")
    expect(assetClassOf("GC")).toBe("metal")
    expect(assetClassOf("SI")).toBe("metal")
    expect(assetClassOf("HG")).toBe("metal")
  })

  it("knows the crypto tickers", () => {
    expect(assetClassOf("BTC")).toBe("crypto")
    expect(assetClassOf("ETH")).toBe("crypto")
  })

  it("treats US single names as equities", () => {
    for (const s of ["AAPL", "NVDA", "TSLA", "META", "AMD", "COIN", "UPST"]) {
      expect(assetClassOf(s)).toBe("equity")
    }
  })

  it("is case-insensitive, since a symbol can arrive either way", () => {
    expect(assetClassOf("es")).toBe("index")
    expect(assetClassOf("mnq")).toBe("micro")
    expect(assetClassOf("aapl")).toBe("equity")
  })

  it("falls back rather than throwing on something unrecognised", () => {
    // A new contract added to settings.yaml must still render a mark, even before
    // anyone teaches this function about it.
    expect(assetClassOf("ZB")).toBe("equity")   // letters -> the lettered fallback
    expect(assetClassOf("6E")).toBe("other")    // has a digit -> the neutral mark
    expect(assetClassOf("")).toBe("other")
  })

  it("MES is checked before ES, or the prefix would win", () => {
    // The ordering inside the function matters: a naive startsWith("ES") test
    // would never see MES, and a naive includes-check on the index list would
    // classify every micro as its parent.
    expect(assetClassOf("MES")).not.toBe(assetClassOf("ES"))
    expect(assetClassOf("MNQ")).not.toBe(assetClassOf("NQ"))
  })
})
