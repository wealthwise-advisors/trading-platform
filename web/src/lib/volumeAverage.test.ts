import { describe, expect, it } from "vitest"
import {
  DEFAULT_VOLUME_AVG_LENGTH, buyerSellerSplit, clampVolumeAvgLength, volumeAverage,
  volumeAxisMax, volumeBarColors, VOLUME_UP, VOLUME_DOWN, VOLUME_FLAT,
} from "./volumeAverage"
import type { OHLCVRecord } from "./types"

const bar = (h: number, l: number, c: number, v: number | null, o = c, t = "2026-11-09T11:45:00"): OHLCVRecord =>
  ({ t, o, h, l, c, v })

describe("buyerSellerSplit -- sir's formula", () => {
  it("his worked example: H105 L100 C104, 1,500,000 -> 80%, 1,200,000 / 300,000", () => {
    const s = buyerSellerSplit(bar(105, 100, 104, 1_500_000))!
    expect(s.buyerPct).toBeCloseTo(0.8, 10)
    expect(s.sellerPct).toBeCloseTo(0.2, 10)
    expect(s).toMatchObject({ buyers: 1_200_000, sellers: 300_000 })
  })

  // Read off the thinkorswim screenshots of 2026-11-09, 1m /ES.
  it.each([
    ["11:45 red", 7568.75, 7567, 7567.25, 1959, 280, 1679],
    ["11:34 red", 7576, 7573.25, 7574, 1925, 525, 1400],
    ["11:33 green", 7575.75, 7572, 7575.5, 2606, 2432, 174],
  ])("%s", (_n, h, l, c, v, buyers, sellers) => {
    expect(buyerSellerSplit(bar(h, l, c, v))).toMatchObject({ buyers, sellers })
  })

  it("red candle: seller % is (High - Close) / Range", () => {
    expect(buyerSellerSplit(bar(7568.75, 7567, 7567.25, 1959, 7568.25))!.sellerPct).toBeCloseTo(1.5 / 1.75, 10)
  })

  it("green candle: buyer % is (Close - Low) / Range", () => {
    expect(buyerSellerSplit(bar(7575.75, 7572, 7575.5, 2606, 7572))!.buyerPct).toBeCloseTo(3.5 / 3.75, 10)
  })

  it("the two sides always add up to the candle's own volume", () => {
    for (const [h, l, c, v] of [[10, 1, 3.3, 7], [7.25, 7, 7.1, 1], [100, 90, 95, 3], [5.5, 5, 5.25, 12345]]) {
      const s = buyerSellerSplit(bar(h, l, c, v))!
      expect(s.buyers + s.sellers).toBe(v)
    }
  })

  it("closing on the high is all buyers, on the low all sellers", () => {
    expect(buyerSellerSplit(bar(10, 5, 10, 100))).toMatchObject({ buyers: 100, sellers: 0 })
    expect(buyerSellerSplit(bar(10, 5, 5, 100))).toMatchObject({ buyers: 0, sellers: 100 })
  })

  it("a candle with no range splits evenly rather than dividing by zero", () => {
    expect(buyerSellerSplit(bar(10, 10, 10, 100))).toMatchObject({ buyerPct: 0.5, buyers: 50, sellers: 50 })
  })

  it("no volume, no split", () => {
    expect(buyerSellerSplit(bar(10, 5, 7, null))).toBeNull()
  })

  it("a close outside its own high/low stays within 0-100%", () => {
    expect(buyerSellerSplit(bar(10, 5, 12, 100))).toMatchObject({ buyers: 100, sellers: 0 })
  })
})

describe("volumeAverage", () => {
  it("defaults to 20", () => expect(DEFAULT_VOLUME_AVG_LENGTH).toBe(20))

  it("is empty until a full window exists, then the simple mean", () => {
    expect(volumeAverage([1, 2, 3, 4], 3)).toEqual([null, null, 2, 3])
  })

  it("a window holding a bar with no volume has no average", () => {
    expect(volumeAverage([1, null, 3, 4, 5], 2)).toEqual([null, null, null, 3.5, 4.5])
  })

  it("matches a brute-force mean on a long series", () => {
    const v = Array.from({ length: 200 }, (_, i) => (i * 37) % 101)
    const out = volumeAverage(v, 20)
    for (let i = 19; i < v.length; i++) {
      const brute = v.slice(i - 19, i + 1).reduce((a, b) => a + b, 0) / 20
      expect(out[i]).toBeCloseTo(brute, 9)
    }
  })
})

describe("clampVolumeAvgLength", () => {
  it.each([[20, 20], [1, 1], [500, 500], [0, 1], [-5, 1], [501, 500], [12.7, 12], [NaN, 20]])(
    "%s -> %s", (input, want) => expect(clampVolumeAvgLength(input)).toBe(want),
  )
})

describe("volumeBarColors -- close against the previous close", () => {
  it("up, down, unchanged; the first bar has no previous close and counts as unchanged", () => {
    expect(volumeBarColors([5, 6, 4, 4])).toEqual([VOLUME_FLAT, VOLUME_UP, VOLUME_DOWN, VOLUME_FLAT])
  })
})

describe("volumeAxisMax", () => {
  const at = (m: number, v: number | null) => bar(1, 0, 1, v, 1, `2026-11-09T10:${String(m).padStart(2, "0")}:00`)
  const ms = (m: number) => Date.parse(at(m, 0).t)

  it("scales to the visible bars and leaves headroom", () => {
    const bars = [at(0, 9000), at(1, 100), at(2, 200)]
    expect(volumeAxisMax(bars, [null, null, null], ms(1), ms(2))).toBeCloseTo(220)
  })

  it("includes the average line", () => {
    expect(volumeAxisMax([at(1, 100)], [300], ms(0), ms(2))).toBeCloseTo(330)
  })

  it("never returns an empty range", () => {
    expect(volumeAxisMax([], [], 0, 1)).toBe(1)
    expect(volumeAxisMax([at(1, null)], [null], ms(0), ms(2))).toBe(1)
  })
})
