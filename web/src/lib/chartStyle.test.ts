import { afterEach, describe, expect, it, vi } from "vitest"
import {
  CHART_STYLE_STORE_KEY, DEFAULT_CHART_STYLE, autoRenkoBrick, extendedHoursSpans, heikinAshi,
  loadChartStyle, renkoBricks, saveChartStyle,
} from "./chartStyle"
import type { OHLCVRecord } from "./types"

const bar = (t: string, o: number, h: number, l: number, c: number): OHLCVRecord => ({ t, o, h, l, c, v: 1 })

describe("heikinAshi", () => {
  it("first candle: close is the OHLC mean, open the O/C midpoint", () => {
    const [ha] = heikinAshi([bar("a", 10, 14, 8, 12)])
    expect(ha).toMatchObject({ o: 11, c: 11, h: 14, l: 8 })
  })

  it("later candles open at the previous HA midpoint and widen to it", () => {
    const ha = heikinAshi([bar("a", 10, 14, 8, 12), bar("b", 20, 21, 19, 20)])
    expect(ha[1].o).toBe(11)
    expect(ha[1].c).toBe(20)
    expect(ha[1].l).toBe(11)
    expect(ha[1].h).toBe(21)
  })
})

describe("renkoBricks", () => {
  const closes = (cs: number[]) => cs.map((c, i) => bar(`t${i}`, c, c, c, c))

  it("a brick per full move", () => {
    const bricks = renkoBricks(closes([100, 101, 102.5, 104.1]), 1)
    expect(bricks.map((b) => [b.o, b.c])).toEqual([[100, 101], [101, 102], [102, 103], [103, 104]])
  })

  it("turning round takes two bricks", () => {
    const bricks = renkoBricks(closes([100, 103, 102.5, 101]), 1)
    expect(bricks.map((b) => [b.o, b.c])).toEqual([[100, 101], [101, 102], [102, 103], [102, 101]])
  })

  it("each brick carries the bar that completed it", () => {
    const bricks = renkoBricks(closes([100, 102]), 1)
    expect(bricks.map((b) => b.t)).toEqual(["t1", "t1"])
  })

  it("nothing for no bars or no brick", () => {
    expect(renkoBricks([], 1)).toEqual([])
    expect(renkoBricks(closes([1, 5]), 0)).toEqual([])
  })

  it("auto brick is twice the median range, to the tick", () => {
    expect(autoRenkoBrick([bar("a", 1, 2, 1, 1), bar("b", 1, 2.5, 1, 1), bar("c", 1, 4, 1, 1)])).toBe(3)
  })
})

describe("extendedHoursSpans", () => {
  const M = 60_000
  const t = ["2026-11-09T09:28:00", "2026-11-09T09:29:00", "2026-11-09T09:30:00", "2026-11-09T15:59:00",
             "2026-11-09T16:00:00", "2026-11-09T16:01:00"]

  it("runs outside 09:30-16:00", () => {
    expect(extendedHoursSpans(t, M)).toEqual([
      ["2026-11-09T09:28:00", "2026-11-09T09:29:00"], ["2026-11-09T16:00:00", "2026-11-09T16:01:00"],
    ])
  })

  it("regular hours only: nothing to shade", () => {
    expect(extendedHoursSpans(t.slice(2, 4), M)).toEqual([])
  })

  it("daily bars have no session", () => {
    expect(extendedHoursSpans(["2026-11-09T00:00:00"], 24 * 60 * M)).toEqual([])
  })
})

describe("stored style", () => {
  afterEach(() => vi.unstubAllGlobals())
  const store = (values: Record<string, string>) => vi.stubGlobal("localStorage", {
    getItem: (k: string) => values[k] ?? null, setItem: (k: string, v: string) => { values[k] = v },
  })

  it("round-trips", () => {
    store({})
    const s = { ...DEFAULT_CHART_STYLE, type: "heikin" as const, maroon: true, compare: "NQ", rightSpace: 10 }
    saveChartStyle(s)
    expect(loadChartStyle()).toEqual(s)
  })

  it.each(["x", "null", "[]", '{"type":"tick","up":"red","rightSpace":-4,"compare":"<script>"}'])(
    "anything unrecognised is the default: %s", (raw) => {
      store({ [CHART_STYLE_STORE_KEY]: raw })
      expect(loadChartStyle()).toEqual(DEFAULT_CHART_STYLE)
    },
  )
})
