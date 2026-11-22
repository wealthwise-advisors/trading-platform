// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest"
import { alertText, takeNew, SEEN_KEY, type AlertEvent } from "./alertEvents"

const ev = (id: number, fired_at = "2026-11-23T10:42:05-05:00", over: Partial<AlertEvent> = {}): AlertEvent => ({
  id, alert_id: `a${id}`, symbol: "ES", direction: "above", level: 6900, note: "", price: 6901.25, fired_at, ...over,
})
const NOW = new Date("2026-11-23T11:00:00-05:00").getTime()

beforeEach(() => localStorage.clear())

describe("which alert events to announce", () => {
  it("only those after the last one this browser showed", () => {
    localStorage.setItem(SEEN_KEY, "2")
    expect(takeNew([ev(1), ev(2), ev(3)], NOW).map((e) => e.id)).toEqual([3])
    expect(localStorage.getItem(SEEN_KEY)).toBe("3")
    expect(takeNew([ev(3)], NOW)).toEqual([])
  })
  it("a browser's first visit shows the last 12 hours, not the whole history", () => {
    const got = takeNew([ev(1, "2026-11-22T20:00:00-05:00"), ev(2, "2026-11-23T08:00:00-05:00")], NOW)
    expect(got.map((e) => e.id)).toEqual([2])
    expect(localStorage.getItem(SEEN_KEY)).toBe("2")
  })
})

describe("a scanner condition alert", () => {
  it("says what matched, where it closed and when", () => {
    expect(alertText(ev(1, "2026-11-23T10:42:05-05:00", { direction: "condition", level: 0, price: 6912.5,
                                                          note: "RSI dip on 5m, bar 10:35" })))
      .toBe("ES: RSI dip on 5m, bar 10:35. Close 6,912.50 at 10:42.")
  })
})

describe("what the notice says", () => {
  it("level, direction, the price that reached it, the time and the note", () => {
    expect(alertText(ev(1, "2026-11-23T10:42:05-05:00", { note: "breakout" })))
      .toBe("ES reached 6,900.00 (above): traded 6,901.25 at 10:42. breakout")
    expect(alertText(ev(1, "2026-11-23T09:05:00-05:00", { direction: "below", level: 6800, price: 6799.5 })))
      .toBe("ES reached 6,800.00 (below): traded 6,799.50 at 09:05.")
  })
})
