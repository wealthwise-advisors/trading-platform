import { afterEach, describe, expect, it, vi } from "vitest"
import {
  DEFAULT_VOLUME_AVG_LENGTH, VOLUME_AVG_STORE_KEY, buyerSellerSplit, clampVolumeAvgLength,
  loadVolumeAvgSettings, saveVolumeAvgSettings, volumeAverage, volumeAverageAt, volumeAverageWithContext,
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

  it("one outsized bar does not squash the rest", () => {
    // 2026-11-09: a 73,659 close among bars of a few thousand.
    const bars = [...Array.from({ length: 39 }, (_, i) => at(i % 60, 2000 + (i % 5) * 1000)), at(59, 73659)]
    const top = volumeAxisMax(bars, bars.map(() => null), ms(0), ms(59))
    expect(top).toBeCloseTo(6000 * 1.6 * 1.1)
  })

  it("a window of similar bars still fits its tallest", () => {
    const bars = [at(1, 900), at(2, 1000), at(3, 1100)]
    expect(volumeAxisMax(bars, [null, null, null], ms(0), ms(5))).toBeCloseTo(1210)
  })

  it("never returns an empty range", () => {
    expect(volumeAxisMax([], [], 0, 1)).toBe(1)
    expect(volumeAxisMax([at(1, null)], [null], ms(0), ms(2))).toBe(1)
  })
})

describe("volumeAverageWithContext", () => {
  const b = (m: number, v: number | null) => ({ t: `2026-11-09T09:${String(m).padStart(2, "0")}:00`, v })

  it("gives the first bars an average from the bars before the run", () => {
    const ctx = { t: [b(28, 0).t, b(29, 0).t], v: [10, 20] }
    expect(volumeAverageWithContext([b(30, 30), b(31, 40)], ctx, 3)).toEqual([20, 30])
  })

  it("runs through bars the session filter removed, in time order", () => {
    const ctx = { t: [b(31, 0).t], v: [100] }
    expect(volumeAverageWithContext([b(30, 10), b(32, 20)], ctx, 2)).toEqual([null, 60])
  })

  it("without context it is the plain average", () => {
    expect(volumeAverageWithContext([b(30, 1), b(31, 3)], undefined, 2)).toEqual([null, 2])
    expect(volumeAverageWithContext([b(30, 1), b(31, 3)], { t: [], v: [] }, 2)).toEqual([null, 2])
  })
})

describe("volumeAverageAt", () => {
  const rows = [1, 2, 3, 4].map((v) => ({ v }))

  it("is the average as of that many bars", () => {
    expect(volumeAverageAt(rows, 3, 2)).toBe(2.5)
    expect(volumeAverageAt(rows, 4, 2)).toBe(3.5)
  })

  it("agrees with the chart's series", () => {
    const series = volumeAverage(rows.map((r) => r.v), 3)
    rows.forEach((_, i) => expect(volumeAverageAt(rows, i + 1, 3)).toBe(series[i]))
  })

  it("has nothing before a full window, or across a missing volume", () => {
    expect(volumeAverageAt(rows, 1, 2)).toBeNull()
    expect(volumeAverageAt([{ v: 1 }, { v: null }], 2, 2)).toBeNull()
  })

  it("a count past the end stops at the end", () => expect(volumeAverageAt(rows, 99, 2)).toBe(3.5))
})

describe("saved settings", () => {
  afterEach(() => vi.unstubAllGlobals())
  const store = (values: Record<string, string>) => vi.stubGlobal("localStorage", {
    getItem: (k: string) => values[k] ?? null,
    setItem: (k: string, v: string) => { values[k] = v },
  })
  const FACTORY = { on: true, length: 20 }

  it("round-trips", () => {
    store({})
    saveVolumeAvgSettings({ on: false, length: 50 })
    expect(loadVolumeAvgSettings()).toEqual({ on: false, length: 50 })
  })

  it("nothing saved is on, 20", () => {
    store({})
    expect(loadVolumeAvgSettings()).toEqual(FACTORY)
  })

  it.each(["not json", "null", "[]", '{"on":"yes","length":"x"}'])("corrupt value %s is the factory setting", (raw) => {
    store({ [VOLUME_AVG_STORE_KEY]: raw })
    expect(loadVolumeAvgSettings()).toEqual(FACTORY)
  })

  it("an out-of-range length is pulled back in bounds", () => {
    store({ [VOLUME_AVG_STORE_KEY]: '{"on":true,"length":99999}' })
    expect(loadVolumeAvgSettings().length).toBe(500)
  })

  it("storage that throws is survivable", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => { throw new Error("denied") }, setItem: () => { throw new Error("full") },
    })
    expect(loadVolumeAvgSettings()).toEqual(FACTORY)
    expect(() => saveVolumeAvgSettings(FACTORY)).not.toThrow()
  })
})
