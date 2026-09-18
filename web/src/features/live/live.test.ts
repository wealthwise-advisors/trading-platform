/**
 * The browser's half of a paper session.
 *
 * Two things are worth pinning here, and neither is cosmetic:
 *
 *   1. the last bar is never sent, because it has not closed yet
 *   2. the limits the dialog promises are the limits the server enforces
 *
 * The first is the difference between a paper result you can believe and one
 * that peeks a tick into the future. The second is a promise made to someone
 * about to start a trading loop, and a promise that drifts from the code is
 * worse than no promise.
 */

import { describe, expect, it } from "vitest"
import { closedBars } from "./useLiveSession"
import { limitsFor } from "./DeployDialog"
import type { OHLCVRecord } from "@/lib/types"

const bar = (t: string): OHLCVRecord => ({ t, o: 1, h: 2, l: 0, c: 1.5, v: 10 })

describe("only closed bars are sent", () => {
  it("drops the last bar, which is still forming", () => {
    const bars = [bar("09:30"), bar("09:31"), bar("09:32")]
    expect(closedBars(bars).map((b) => b.t)).toEqual(["09:30", "09:31"])
  })

  it("sends nothing when there is only the forming bar", () => {
    expect(closedBars([bar("09:30")])).toEqual([])
  })

  it("sends nothing when there are no bars at all", () => {
    expect(closedBars([])).toEqual([])
  })

  it("never returns the final element, whatever the length", () => {
    for (const n of [2, 3, 10, 500]) {
      const bars = Array.from({ length: n }, (_, i) => bar(String(i).padStart(4, "0")))
      const out = closedBars(bars)
      expect(out).toHaveLength(n - 1)
      expect(out.at(-1)!.t).not.toBe(bars.at(-1)!.t)
    }
  })
})

describe("the limits the dialog promises", () => {
  // These mirror src/live/paper_session.py::default_limits. If that changes
  // and this does not, the dialog under-reports what the session will do.
  it("matches the server's defaults for one contract", () => {
    expect(limitsFor(1)).toEqual({
      maxPerOrder: 1, maxPosition: 2, maxOrders: 50, minSecondsBetween: 1,
    })
  })

  it("scales the position cap with the order size, as the server does", () => {
    expect(limitsFor(3)).toMatchObject({ maxPerOrder: 3, maxPosition: 6 })
  })

  it("never promises a zero or negative size", () => {
    expect(limitsFor(0).maxPerOrder).toBe(1)
    expect(limitsFor(-5).maxPerOrder).toBe(1)
  })
})
