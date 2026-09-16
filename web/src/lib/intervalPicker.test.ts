import { describe, expect, it } from "vitest"
import { ALL_CHART_TIMEFRAMES } from "./chartSetup"
import {
  FAV_KEY, LAYOUT_KEY, defaultLayout, favouriteRows, loadFavourites, loadLayout,
  moveInterval, normalizeLayout, rangeLabel, saveFavourites, saveLayout,
  toggleFavourite, toggleHidden, visibleRows,
} from "./intervalPicker"

/** An in-memory Storage, so persistence is tested without a browser. */
function memStore(seed: Record<string, string> = {}) {
  const data = { ...seed }
  return {
    data,
    getItem: (k: string) => (k in data ? data[k] : null),
    setItem: (k: string, v: string) => { data[k] = v },
  }
}

const throwing = {
  getItem: () => { throw new Error("blocked") },
  setItem: () => { throw new Error("blocked") },
}

describe("rangeLabel reads the specified table and invents nothing", () => {
  it.each([
    ["1m", "2 D"], ["5m", "2 D"], ["10m", "3 D"], ["15m", "4 D"],
    ["20m", "5 D"], ["30m", "10 D"], ["45m", "15 D"], ["1h", "25 D"],
    ["2h", "180 D"], ["4h", "180 D"], ["1d", "Max"], ["1w", "Max"],
  ])("%s -> %s", (tf, label) => {
    expect(rangeLabel(tf)).toBe(label)
  })

  it.each(["2m", "25m", "35m"])("%s has no day count, so no label", (tf) => {
    expect(rangeLabel(tf)).toBeNull()
  })
})

describe("normalizeLayout", () => {
  it("defaults to every interval, in order, none hidden", () => {
    expect(normalizeLayout(undefined)).toEqual({ order: [...ALL_CHART_TIMEFRAMES], hidden: [] })
  })

  it("drops intervals the app does not offer and collapses duplicates", () => {
    // 3h and 7m: intervals the app has never offered (4h was the example until it was added).
    const l = normalizeLayout({ order: ["3h", "5m", "5m", "7m", "1m"], hidden: ["D", "1m", "1m"] })
    expect(l.order.slice(0, 2)).toEqual(["5m", "1m"])
    expect(l.order).not.toContain("3h")
    expect(l.order).not.toContain("7m")
    expect(l.hidden).toEqual(["1m"])
  })

  it("appends any known interval missing from a stored order", () => {
    const l = normalizeLayout({ order: ["1h"] })
    expect(l.order[0]).toBe("1h")
    expect([...l.order].sort()).toEqual([...ALL_CHART_TIMEFRAMES].sort())
  })

  it("survives garbage", () => {
    expect(normalizeLayout("nope")).toEqual(defaultLayout())
    expect(normalizeLayout({ order: "x", hidden: 3 })).toEqual(defaultLayout())
  })
})

describe("moveInterval", () => {
  const order = ["1m", "2m", "5m"]
  it("swaps with the neighbour", () => {
    expect(moveInterval(order, "2m", -1)).toEqual(["2m", "1m", "5m"])
    expect(moveInterval(order, "2m", 1)).toEqual(["1m", "5m", "2m"])
  })
  it("does nothing off either end or for an unknown interval", () => {
    expect(moveInterval(order, "1m", -1)).toBe(order)
    expect(moveInterval(order, "5m", 1)).toBe(order)
    expect(moveInterval(order, "9m", 1)).toBe(order)
  })
})

describe("rows", () => {
  it("the Time frame tab leaves out hidden rows", () => {
    const l = toggleHidden(defaultLayout(), "1m")
    expect(visibleRows(l)).not.toContain("1m")
    expect(visibleRows(toggleHidden(l, "1m"))).toContain("1m")
  })

  it("the Favorites tab keeps the custom order and still shows a starred hidden row", () => {
    const l = { order: ["1h", "5m", "1m"], hidden: ["1h"] }
    expect(favouriteRows(l, ["1m", "1h"])).toEqual(["1h", "1m"])
  })

  it("toggleFavourite adds then removes", () => {
    expect(toggleFavourite([], "5m")).toEqual(["5m"])
    expect(toggleFavourite(["5m"], "5m")).toEqual([])
  })
})

describe("persistence", () => {
  it("favourites round-trip, filtered to known intervals", () => {
    const s = memStore({ [FAV_KEY]: JSON.stringify(["5m", "3h", "5m", 7]) })
    expect(loadFavourites(s)).toEqual(["5m"])
    saveFavourites(["1m", "1h"], s)
    expect(loadFavourites(s)).toEqual(["1m", "1h"])
  })

  it("layout round-trips", () => {
    const s = memStore()
    const l = { order: [...ALL_CHART_TIMEFRAMES].reverse(), hidden: ["2m"] }
    saveLayout(l, s)
    expect(JSON.parse(s.data[LAYOUT_KEY])).toEqual(l)
    expect(loadLayout(s)).toEqual(l)
  })

  it("a blocked or corrupt store falls back instead of throwing", () => {
    expect(loadFavourites(throwing)).toEqual([])
    expect(loadLayout(throwing)).toEqual(defaultLayout())
    expect(() => saveFavourites(["1m"], throwing)).not.toThrow()
    expect(loadFavourites(memStore({ [FAV_KEY]: "{not json" }))).toEqual([])
    expect(loadLayout(memStore({ [LAYOUT_KEY]: "{not json" }))).toEqual(defaultLayout())
  })
})
