import { describe, it, expect } from "vitest"
import { assetClassOf, markStyle } from "./SymbolMark"

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

/**
 * The mark exists to tell one row from another. A colour shared between two
 * contracts is therefore not a cosmetic slip, it is the feature not working --
 * and it is invisible to a render test, which is how the first version shipped
 * with ES, NQ, YM and RTY all drawing the same violet disc.
 */
describe("disc colours", () => {
  /** Every contract the settings file actually offers. */
  const OFFERED = [
    "ES", "NQ", "MES", "MNQ", "YM", "RTY", "CL", "NG", "GC", "SI", "HG",
  ] as const

  it("gives every offered contract its own disc colour", () => {
    const seen = new Map<string, string>()
    for (const s of OFFERED) {
      const { disc } = markStyle(s)
      expect(seen.has(disc), `${s} and ${seen.get(disc)} share ${disc}`).toBe(false)
      seen.set(disc, s)
    }
    expect(seen.size).toBe(OFFERED.length)
  })

  it("keeps a micro distinct from its full-size parent", () => {
    expect(markStyle("MES").disc).not.toBe(markStyle("ES").disc)
    expect(markStyle("MNQ").disc).not.toBe(markStyle("NQ").disc)
  })

  it("darkens the ink on the discs a white glyph would vanish into", () => {
    // Gold and silver are pale; white-on-pale is the one combination that
    // renders as an empty circle.
    for (const s of ["GC", "SI"]) expect(markStyle(s).ink).not.toBe("#ffffff")
    for (const s of ["ES", "CL", "HG"]) expect(markStyle(s).ink).toBe("#ffffff")
  })

  it("gives an unknown ticker a colour rather than undefined", () => {
    // A contract added to settings.yaml before anyone teaches this file about it
    // must still render, not crash on a missing table entry.
    for (const s of ["ZB", "6E", ""]) {
      expect(markStyle(s).disc).toMatch(/^(#|hsl)/)
    }
  })

  it("keeps equity hues out of the rising-candle green band", () => {
    // A mark that reads as a direction on a trading screen is worse than no mark.
    for (const s of ["AAPL", "NVDA", "TSLA", "META", "AMD", "COIN", "UPST"]) {
      const m = /^hsl\((\d+(?:\.\d+)?)/.exec(markStyle(s).disc)
      expect(m, `${s} should take a generated hue`).not.toBeNull()
      const hue = Number(m![1])
      expect(hue < 95 || hue >= 170, `${s} landed on hue ${hue}`).toBe(true)
    }
  })
})
