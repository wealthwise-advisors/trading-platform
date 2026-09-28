/**
 * The default date range must land on a day the regular session exists.
 *
 * THE BUG THIS LOCKS DOWN. The old rollback table was
 * `day === 0 ? 2 : day === 6 ? 1 : 1`, which rolled every non-Sunday back a
 * single day -- so a MONDAY landed on Sunday. The run then fetched the
 * Sunday-evening futures reopen (18:00 onwards) and the 09:30-16:00 session
 * filter removed every bar, which reached the user as "No bars remain after
 * applying the session filter" on the first run of the week.
 */
import { describe, expect, it } from "vitest"

import { defaultDateRange } from "./configStore"

/** Local noon, so the assertion cannot be moved by a timezone offset. */
const at = (y: number, m: number, d: number) => new Date(y, m - 1, d, 12, 0, 0)

const dow = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number)
  return new Date(y, m - 1, d).getDay()
}

describe("defaultDateRange", () => {
  // September 2026: 25th is a Friday, 26th Saturday, 27th Sunday, 28th Monday.
  it.each([
    ["Monday", at(2026, 9, 28), "2026-09-25"],
    ["Sunday", at(2026, 9, 27), "2026-09-25"],
    ["Saturday", at(2026, 9, 26), "2026-09-25"],
    ["Tuesday", at(2026, 9, 29), "2026-09-28"],
    ["Wednesday", at(2026, 9, 30), "2026-09-29"],
    ["Thursday", at(2026, 10, 1), "2026-09-30"],
    ["Friday", at(2026, 10, 2), "2026-10-01"],
  ])("on a %s it picks the previous weekday", (_name, now, expected) => {
    const { start, end } = defaultDateRange(now)
    expect(start).toBe(expected)
    expect(end).toBe(expected)
  })

  it("never lands on a Saturday or a Sunday", () => {
    // Every day of a full year, not just the seven above: an off-by-one in the
    // table would still pass a hand-picked week.
    for (let i = 0; i < 366; i++) {
      const now = new Date(2026, 0, 1, 12, 0, 0)
      now.setDate(now.getDate() + i)
      const day = dow(defaultDateRange(now).start)
      expect(day, `${now.toDateString()} produced a weekend`).not.toBe(0)
      expect(day, `${now.toDateString()} produced a weekend`).not.toBe(6)
    }
  })

  it("reports the LOCAL date, not the UTC one", () => {
    // 00:30 local. toISOString() would report the previous day for any
    // timezone ahead of UTC -- IST, where this app is used, among them.
    const earlyMonday = new Date(2026, 8, 28, 0, 30, 0)
    expect(defaultDateRange(earlyMonday).start).toBe("2026-09-25")
  })
})
