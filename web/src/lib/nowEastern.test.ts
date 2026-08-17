import { describe, it, expect } from "vitest"
import { nowEasternLabel } from "./clock"

/**
 * The label frame every bar comparison uses.
 *
 * Bars arrive as naive Eastern timestamps and all the label helpers do plain
 * string arithmetic on that basis, so "now" has to be produced in the same
 * frame. Getting it from a local Date would be wrong for any user outside
 * Eastern -- which is the actual situation: the reporter's machine is on
 * Central, an hour behind the tape.
 */
describe("nowEasternLabel", () => {
  it("returns the YYYY-MM-DD HH:MM shape bar labels use", () => {
    expect(nowEasternLabel()).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/)
  })

  it("converts a known UTC instant to Eastern daylight time", () => {
    // 2026-08-17 13:28 UTC is 09:28 EDT (UTC-4). This is the exact instant
    // from the reported case.
    expect(nowEasternLabel(new Date("2026-08-17T13:28:00Z"))).toBe("2026-08-17 09:28")
  })

  it("uses standard time in winter, not a fixed offset", () => {
    // January is EST (UTC-5). A hard-coded -4 would give 08:30 here.
    expect(nowEasternLabel(new Date("2026-01-15T13:30:00Z"))).toBe("2026-01-15 08:30")
  })

  it("crosses the date boundary correctly", () => {
    // 03:30 UTC is the previous evening in Eastern.
    expect(nowEasternLabel(new Date("2026-08-17T03:30:00Z"))).toBe("2026-08-16 23:30")
  })

  it("renders midnight as 00, not 24", () => {
    // 04:00 UTC in August is exactly midnight Eastern. Intl can emit "24".
    expect(nowEasternLabel(new Date("2026-08-17T04:00:00Z"))).toBe("2026-08-17 00:00")
  })

  it("sorts lexicographically, which is how it gets compared to bar labels", () => {
    const a = nowEasternLabel(new Date("2026-08-17T13:28:00Z"))   // 09:28
    expect(a < "2026-08-17 18:00").toBe(true)     // 18:00 is still ahead
    expect(a > "2026-08-17 09:00").toBe(true)
    expect(a < "2026-08-18 00:00").toBe(true)
  })
})

/**
 * The decision the jump handler makes. Replicated here as the same three-way
 * branch, so the wording rule is pinned even though the handler itself lives
 * inside a large component.
 */
type Advice = "future" | "reload" | "play"

function adviceFor(target: string, newest: string, nowET: string, done: boolean): Advice | null {
  if (target <= newest) return null       // the bar exists; no note needed
  if (target > nowET) return "future"
  if (done) return "reload"
  return "play"
}

describe("which advice a later jump target gets", () => {
  const NOW = "2026-08-17 09:28"

  it("the reported case: 18:00 today, asked at 09:20, mid-playback", () => {
    // Previously answered with "press Play", which could never work.
    expect(adviceFor("2026-08-17 18:00", "2026-08-17 09:04", NOW, false)).toBe("future")
  })

  it("still says future even once playback has finished", () => {
    expect(adviceFor("2026-08-17 18:00", "2026-08-17 09:28", NOW, true)).toBe("future")
  })

  it("a past time beyond a FINISHED replay asks for a reload", () => {
    // The snapshot stopped short; more bars exist upstream by now.
    expect(adviceFor("2026-08-17 09:20", "2026-08-17 09:00", NOW, true)).toBe("reload")
  })

  it("a past time during a RUNNING replay still says press Play", () => {
    // The original message, kept for the case where it is true.
    expect(adviceFor("2026-08-17 09:20", "2026-08-17 09:00", NOW, false)).toBe("play")
  })

  it("no note at all when the bar is already on the tape", () => {
    expect(adviceFor("2026-08-17 08:00", "2026-08-17 09:00", NOW, false)).toBeNull()
  })

  it("one minute into the future is future; one minute past is not", () => {
    expect(adviceFor("2026-08-17 09:29", "2026-08-17 09:00", NOW, false)).toBe("future")
    expect(adviceFor("2026-08-17 09:27", "2026-08-17 09:00", NOW, false)).toBe("play")
  })

  it("a target exactly now is not treated as the future", () => {
    expect(adviceFor(NOW, "2026-08-17 09:00", NOW, false)).toBe("play")
  })

  it("tomorrow is future regardless of playback state", () => {
    for (const done of [true, false]) {
      expect(adviceFor("2026-08-18 10:00", "2026-08-17 09:28", NOW, done)).toBe("future")
    }
  })
})
