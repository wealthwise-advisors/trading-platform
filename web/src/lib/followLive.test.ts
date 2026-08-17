import { describe, it, expect } from "vitest"
import {
  FOLLOW_POLL_MS, IDLE_FOLLOW, shouldResumeAfterExtend, shouldPoll,
  followLabel, applyExtendReply, liveEdgeLabel, type FollowState,
} from "./followLive"

const reply = (over: Partial<Parameters<typeof applyExtendReply>[1]> = {}) => ({
  added: 0, reason: null, is_done: true, data_time: null, ...over,
})

const following = (over: Partial<FollowState> = {}): FollowState => ({
  ...IDLE_FOLLOW, enabled: true, ...over,
})

describe("poll interval", () => {
  it("is one minute, matching the one-minute source resolution", () => {
    expect(FOLLOW_POLL_MS).toBe(60_000)
  })
})

describe("resuming playback after bars arrive", () => {
  const AT_EDGE = true, PAUSED = false

  it("resumes when parked at the edge and there is more to play", () => {
    expect(shouldResumeAfterExtend(reply({ added: 3, is_done: false }), AT_EDGE)).toBe(true)
  })

  it("does not resume when nothing arrived", () => {
    // Sending play here would light the button and stream no bars.
    expect(shouldResumeAfterExtend(reply({ added: 0, is_done: false }), AT_EDGE)).toBe(false)
  })

  it("does not resume when the session is still finished", () => {
    // Reachable when every returned bar was withheld as still forming: the
    // provider answered, nothing was taken, so there is nothing to play.
    expect(shouldResumeAfterExtend(reply({ added: 0, is_done: true }), AT_EDGE)).toBe(false)
  })

  it("does not resume on a provider failure", () => {
    expect(shouldResumeAfterExtend(
      reply({ added: 0, reason: "could not reach the data source", is_done: true }),
      AT_EDGE,
    )).toBe(false)
  })

  it("does NOT override a deliberate pause", () => {
    // Someone paused at 10:15 to study a bar. A new minute printing must not
    // drag them to 11:46 — that makes Pause look broken.
    expect(shouldResumeAfterExtend(reply({ added: 1, is_done: false }), PAUSED)).toBe(false)
  })

  it("still collects the bars while paused — it just does not play them", () => {
    // The distinction: extending is always fine, RESUMING is the part that
    // needs consent. So a paused follower accumulates data and plays it when
    // the user presses Play.
    const r = reply({ added: 5, is_done: false })
    expect(shouldResumeAfterExtend(r, PAUSED)).toBe(false)
    expect(shouldResumeAfterExtend(r, AT_EDGE)).toBe(true)
  })
})

describe("whether to send a poll", () => {
  it("polls when following and connected", () => {
    expect(shouldPoll(following(), true)).toBe(true)
  })

  it("does not poll when not following", () => {
    expect(shouldPoll(IDLE_FOLLOW, true)).toBe(false)
  })

  it("does not poll without a connection", () => {
    expect(shouldPoll(following(), false)).toBe(false)
  })

  it("does not stack polls while one is in flight", () => {
    // A slow provider must not be able to queue several deep — one late reply
    // would otherwise become a burst of redundant refetches.
    expect(shouldPoll(following({ waiting: true }), true)).toBe(false)
  })
})

describe("the status line", () => {
  it("says plainly when it is not following", () => {
    expect(followLabel(IDLE_FOLLOW)).toContain("Not following")
  })

  it("says it is checking before the first reply", () => {
    expect(followLabel(following({ waiting: true }))).toBe("Checking for new bars…")
  })

  it("reports new bars with the time they reach", () => {
    const label = followLabel(following({ lastAdded: 4, dataTime: "2026-08-17 09:26" }))
    expect(label).toContain("4 new bars")
    expect(label).toContain("09:26")
  })

  it("shows the edge as a BAR LABEL, never a raw ISO timestamp", () => {
    // Browser-caught: the server sends ISO, and printing it verbatim put
    // "2026-08-17T09:26:00" beside a tape column reading "09:26".
    const label = followLabel(following({ lastAdded: 1, dataTime: "2026-08-17T09:26:00" }))
    expect(label).toContain("2026-08-17 09:26")
    expect(label).not.toContain("T09:26")
    expect(label).not.toContain(":00.")
  })

  it("does the same when up to date", () => {
    const label = followLabel(following({ lastAdded: 0, dataTime: "2026-08-17T09:26:00" }))
    expect(label).toContain("2026-08-17 09:26")
    expect(label).not.toContain("T09:26")
  })

  it("uses the singular for one bar", () => {
    expect(followLabel(following({ lastAdded: 1 }))).toContain("1 new bar")
    expect(followLabel(following({ lastAdded: 1 }))).not.toContain("1 new bars")
  })

  it("says up to date when a poll found nothing", () => {
    expect(followLabel(following({ lastAdded: 0, dataTime: "2026-08-17 09:26" })))
      .toContain("up to date")
  })

  it("SURFACES a failure rather than claiming to be following", () => {
    // The failure this wording exists to prevent: a silent "Following live"
    // through a broker outage, while the user trusts the number on screen.
    const label = followLabel(following({
      lastAdded: 0, lastReason: "could not reach the data source: connection reset",
    }))
    expect(label).toContain("could not reach the data source")
  })

  it("a reason outranks a bar count", () => {
    const label = followLabel(following({
      lastAdded: 0, lastReason: "the newest bar is still forming (1 withheld)",
      dataTime: "2026-08-17 09:26",
    }))
    expect(label).toContain("still forming")
    expect(label).not.toContain("up to date")
  })

  it("the three situations are all distinguishable", () => {
    const off = followLabel(IDLE_FOLLOW)
    const ok = followLabel(following({ lastAdded: 0 }))
    const bad = followLabel(following({ lastAdded: 0, lastReason: "provider down" }))
    expect(new Set([off, ok, bad]).size).toBe(3)
  })
})

describe("folding a reply into state", () => {
  it("clears the in-flight flag", () => {
    expect(applyExtendReply(following({ waiting: true }), reply()).waiting).toBe(false)
  })

  it("records the count and the reason", () => {
    const next = applyExtendReply(following(), reply({ added: 2, reason: "hm" }))
    expect(next.lastAdded).toBe(2)
    expect(next.lastReason).toBe("hm")
  })

  it("keeps the last known edge when a reply carries none", () => {
    // A failed poll should not blank a time the user was reading.
    const next = applyExtendReply(
      following({ dataTime: "2026-08-17 09:26" }),
      reply({ reason: "provider down", data_time: null }),
    )
    expect(next.dataTime).toBe("2026-08-17 09:26")
  })

  it("advances the edge when a reply carries one", () => {
    const next = applyExtendReply(
      following({ dataTime: "2026-08-17 09:26" }),
      reply({ added: 1, data_time: "2026-08-17T09:27:00" }),
    )
    expect(next.dataTime).toBe("2026-08-17T09:27:00")
  })

  it("leaves `enabled` alone — a reply never turns following off", () => {
    expect(applyExtendReply(following(), reply({ reason: "provider down" })).enabled).toBe(true)
  })
})

describe("the live edge as a bar label", () => {
  it("converts an ISO timestamp to the tape's label shape", () => {
    expect(liveEdgeLabel("2026-08-17T09:26:00")).toBe("2026-08-17 09:26")
  })

  it("accepts a value that is already in label shape", () => {
    expect(liveEdgeLabel("2026-08-17 09:26")).toBe("2026-08-17 09:26")
  })

  it("drops seconds, which bar labels do not carry", () => {
    expect(liveEdgeLabel("2026-08-17T09:26:45")).toBe("2026-08-17 09:26")
  })

  it("is null for null", () => {
    expect(liveEdgeLabel(null)).toBeNull()
  })

  it("is null for something unparseable rather than passed through", () => {
    expect(liveEdgeLabel("not a time")).toBeNull()
  })

  it("compares correctly against a bar label on the same date", () => {
    // The bug this exists to prevent: "T" sorts AFTER " ", so comparing the raw
    // ISO string against a tape label makes every bar that day look earlier
    // than the live edge.
    const raw = "2026-08-17T09:26:00"
    const bar = "2026-08-17 09:20"
    expect(bar < raw).toBe(true)              // meaningless, but true either way
    expect(bar < liveEdgeLabel(raw)!).toBe(true)
    // The case that actually breaks: a bar LATER than the edge.
    const later = "2026-08-17 09:30"
    expect(later < raw).toBe(true)             // wrong — reads as before the edge
    expect(later < liveEdgeLabel(raw)!).toBe(false)   // right
  })
})
