import { describe, it, expect } from "vitest"
import { FOLLOW_POLL_MS, IDLE_FOLLOW, shouldResumeAfterExtend, shouldPoll, followLabel, applyExtendReply, liveEdgeLabel, shouldAutoFollow, minutesBehind, lagNote, canReceiveNewBars, type FollowState, isLostSession } from "./followLive"

const reply = (over: Partial<Parameters<typeof applyExtendReply>[1]> = {}) => ({
  added: 0, reason: null, is_done: true, data_time: null, ...over,
})

const following = (over: Partial<FollowState> = {}): FollowState => ({
  ...IDLE_FOLLOW, enabled: true, ...over,
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

// ---------------------------------------------------------------------------
// THE REPORTED LAG
//
// Measured against the live feed over 9 samples: Schwab's own newest bar was
// 0.47 min behind on average (essentially real-time), withholding the forming bar
// cost exactly 1.00 min, and the 60s poll added up to 1.00 min more -- worst case
// 2.98 min, which is the "two minutes behind thinkorswim" that was reported.
//
// Only the poll interval was avoidable, so that is what changed.
// ---------------------------------------------------------------------------
describe("poll interval bounds the collection delay", () => {
  it("is 15s, so a closed bar is collected within 15s", () => {
    expect(FOLLOW_POLL_MS).toBe(15_000)
  })

  it("is not so fast that requests overlap a slow provider", () => {
    // Each poll refetches and resamples the whole window; below ~10s a slow
    // provider would still be answering the previous request.
    expect(FOLLOW_POLL_MS).toBeGreaterThanOrEqual(10_000)
  })
})

describe("auto-following once the live edge is reached", () => {
  const NOW = "2026-08-17 14:51"

  it("starts on a session that ends today", () => {
    expect(shouldAutoFollow("2026-08-17", NOW, "schwab")).toBe(true)
  })

  it("starts on a session that ends in the future", () => {
    expect(shouldAutoFollow("2026-08-20", NOW, "schwab")).toBe(true)
  })

  it("does NOT start on a past session", () => {
    // It would light the control and then report that nothing will ever print.
    expect(shouldAutoFollow("2026-08-16", NOW, "schwab")).toBe(false)
  })

  it("does NOT start on synthetic data", () => {
    expect(shouldAutoFollow("2026-08-17", NOW, "synthetic")).toBe(false)
  })

  it("uses the MARKET's date, not the viewer's", () => {
    // 23:30 in Asia is still the same trading day in New York. Comparing against
    // a local date would switch following off for the whole evening.
    expect(shouldAutoFollow("2026-08-17", "2026-08-17 09:31", "schwab")).toBe(true)
    expect(shouldAutoFollow("2026-08-17", "2026-08-17 15:59", "schwab")).toBe(true)
  })

  it("ignores a half-typed date rather than guessing", () => {
    for (const bad of ["", "2026-8-17", "17-08-2026", "nonsense"]) {
      expect(shouldAutoFollow(bad, NOW, "schwab")).toBe(false)
    }
  })
})

describe("how far behind the tape is", () => {
  it("counts whole minutes from the newest shown bar", () => {
    expect(minutesBehind("2026-08-17T14:50:00", "2026-08-17 14:51")).toBe(1)
    expect(minutesBehind("2026-08-17T14:48:00", "2026-08-17 14:51")).toBe(3)
  })

  it("is 0 when the tape is on the current minute", () => {
    expect(minutesBehind("2026-08-17T14:51:00", "2026-08-17 14:51")).toBe(0)
  })

  it("never goes negative", () => {
    // A bar stamped ahead of the clock should read 0, not -1.
    expect(minutesBehind("2026-08-17T14:52:00", "2026-08-17 14:51")).toBe(0)
  })

  it("crosses an hour and a date correctly", () => {
    expect(minutesBehind("2026-08-17T13:58:00", "2026-08-17 14:02")).toBe(4)
    expect(minutesBehind("2026-08-16T23:58:00", "2026-08-17 00:03")).toBe(5)
  })

  it("is null without a known edge", () => {
    expect(minutesBehind(null, "2026-08-17 14:51")).toBeNull()
  })
})

describe("explaining the gap honestly", () => {
  it("one bar behind is explained as the forming bar", () => {
    const note = lagNote(1, 1)!
    expect(note).toContain("still forming")
  })

  it("one bar plus collection time is explained as such", () => {
    const note = lagNote(2, 1)!
    expect(note).toContain("collect")
  })

  it("further behind than the design accounts for SAYS SO", () => {
    // The important case: it must not reassure the user when something really is
    // wrong. 8 minutes on a 1m chart is not the forming bar.
    const note = lagNote(8, 1)!
    expect(note).toContain("feed itself may be delayed")
    expect(note).not.toContain("still forming")
  })

  it("scales with the timeframe", () => {
    // 4 minutes behind is normal on a 5m chart and abnormal on a 1m one.
    expect(lagNote(4, 5)!).toContain("still forming")
    expect(lagNote(4, 1)!).toContain("feed itself may be delayed")
  })

  it("is null when the gap is unknown", () => {
    expect(lagNote(null, 1)).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// A HISTORICAL SESSION IS NOT "BEHIND"
//
// Shipped bug, reported from the app. A session ending 2025-01-07, opened on
// 2026-08-17, displayed:
//
//   845728 min behind the clock — further behind than the 6 min this design
//   accounts for, so the feed itself may be delayed.
//
// The arithmetic was correct and the statement was nonsense: nothing is delayed,
// that session belongs to last year. Worse, it blamed the data provider, which
// is the sort of message that sends someone hunting a fault that does not exist.
// ---------------------------------------------------------------------------
describe("the lag note stays silent on a session that cannot go live", () => {
  const NOW = "2026-08-17 15:43"

  it("says nothing for a historical session, however large the gap", () => {
    expect(lagNote(845728, 5, false)).toBeNull()
    expect(lagNote(1, 1, false)).toBeNull()
  })

  it("still speaks for a live session", () => {
    expect(lagNote(1, 1, true)).not.toBeNull()
  })

  it("defaults to speaking, so an un-updated caller is not silenced", () => {
    expect(lagNote(1, 1)).not.toBeNull()
  })

  it("canReceiveNewBars is false exactly when the lag note is meaningless", () => {
    expect(canReceiveNewBars("2025-01-07", NOW, "schwab")).toBe(false)
    expect(canReceiveNewBars("2026-08-16", NOW, "schwab")).toBe(false)
    expect(canReceiveNewBars("2026-08-17", NOW, "schwab")).toBe(true)
    expect(canReceiveNewBars("2026-08-20", NOW, "schwab")).toBe(true)
    expect(canReceiveNewBars("2026-08-17", NOW, "synthetic")).toBe(false)
  })

  it("agrees with shouldAutoFollow — one rule, two uses", () => {
    // They diverged before, which is how the bad line reached the screen: the
    // auto-start knew the session was historical and the lag line did not.
    for (const end of ["2025-01-07", "2026-08-16", "2026-08-17", "2026-08-20", "bad"]) {
      for (const src of ["schwab", "external_csv", "synthetic"]) {
        expect(shouldAutoFollow(end, NOW, src)).toBe(canReceiveNewBars(end, NOW, src))
      }
    }
  })

  it("the reported case produces no lag line at all", () => {
    const live = canReceiveNewBars("2025-01-07", NOW, "external_csv")
    expect(live).toBe(false)
    expect(lagNote(minutesBehind("2025-01-07T08:20:00", NOW), 5, live)).toBeNull()
  })
})

describe("isLostSession", () => {
  const base = { deliberate: false, current: true, status: "playing" as const }

  it("reports a socket that closed on its own while the tape was running", () => {
    // The case that prompted this: a deploy recreated the API container at
    // 03:46 ET and every live session went with it.
    expect(isLostSession(base)).toBe(true)
    expect(isLostSession({ ...base, status: "paused" })).toBe(true)
    expect(isLostSession({ ...base, status: "ready" })).toBe(true)
    expect(isLostSession({ ...base, status: "loading" })).toBe(true)
  })

  it("stays quiet when we closed the socket ourselves", () => {
    // Loading a new session, changing setup and unmounting all close the old
    // socket. Reporting those would put an error on screen every single time
    // somebody pressed Load Data.
    expect(isLostSession({ ...base, deliberate: true })).toBe(false)
  })

  it("stays quiet for a socket a newer session already replaced", () => {
    expect(isLostSession({ ...base, current: false })).toBe(false)
  })

  it("stays quiet once the tape has finished", () => {
    // A close after "done" is tidying up, not a failure, and dressing it as one
    // would tell people something broke at the exact moment it succeeded.
    expect(isLostSession({ ...base, status: "done" })).toBe(false)
    expect(isLostSession({ ...base, status: "idle" })).toBe(false)
  })
})
