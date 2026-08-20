/**
 * "Follow live": once the replay has caught up to the newest bar, keep asking
 * the server for bars that have printed since, and play them as they arrive.
 *
 * WHY POLLING AND NOT A STREAM
 * ----------------------------
 * The provider has no working stream -- SchwabProvider.stream() raises
 * NotImplementedError. It does not need one. The finest bar the app shows is one
 * minute, so a bar can only appear once a minute, and one request per minute is
 * the entire requirement. A stream would deliver ticks this app has nowhere to
 * put.
 *
 * The decisions live here rather than in the component so they can be tested
 * without a socket, a timer or a browser. What is left in the component is the
 * interval and the socket send.
 */

/**
 * How often to ask, once following.
 *
 * FIFTEEN seconds, not sixty.
 *
 * One minute was the obvious choice -- a one-minute chart cannot produce a bar
 * more often than that, so a faster poll usually just gets told "still forming".
 * The reasoning was about how often a bar APPEARS and missed how long one waits
 * to be COLLECTED. A bar closing a second after a poll sat unseen for the next
 * 59, so the tape ran up to a minute behind for no reason other than the timer.
 *
 * Reported as a two-minute lag against thinkorswim, of which this was about
 * half. Fifteen seconds bounds the collection delay at fifteen seconds, at the
 * cost of three extra provider requests a minute -- cheap next to a tape that
 * looks a minute stale.
 *
 * Not faster than that: each poll refetches and resamples the session's window
 * (see MultiReplaySession.extend), so the work is real, and below roughly ten
 * seconds a slow provider would still be answering the previous request.
 */
export const FOLLOW_POLL_MS = 15_000

/** The server's reply to one poll, narrowed to the parts a decision needs. */
export interface ExtendReply {
  added: number
  reason: string | null
  is_done: boolean
  data_time: string | null
}

export interface FollowState {
  enabled: boolean
  /** null until the first reply has come back. */
  lastAdded: number | null
  lastReason: string | null
  dataTime: string | null
  /** A poll is in flight. */
  waiting: boolean
}

export const IDLE_FOLLOW: FollowState = {
  enabled: false, lastAdded: null, lastReason: null, dataTime: null, waiting: false,
}

/**
 * Whether newly-arrived bars should start playing on their own.
 *
 * Three conditions, and the third is the one that is easy to miss.
 *
 * Bars must have actually arrived, and the session must have something left to
 * play -- sending play on an empty poll lights the button and streams nothing.
 *
 * And the replay must have been sitting AT THE EDGE, waiting for data. Following
 * live means keeping the tape at the live edge; it does not mean overriding a
 * deliberate pause. Someone who paused at 10:15 to look at a bar has not asked
 * to be dragged to 11:46 because a new minute printed, and auto-resuming there
 * would make the Pause button appear broken.
 */
export function shouldResumeAfterExtend(
  reply: ExtendReply,
  wasAtEdge: boolean,
): boolean {
  return wasAtEdge && reply.added > 0 && !reply.is_done
}

/**
 * Whether a poll is worth sending right now.
 *
 * Skipped while one is already in flight. A poll costs a provider request and a
 * full resample, and a slow provider must not be able to queue several deep --
 * that turns one late reply into a burst of redundant work.
 */
export function shouldPoll(state: FollowState, connected: boolean): boolean {
  return state.enabled && connected && !state.waiting
}

/**
 * The one line of status the user reads.
 *
 * Written so the three situations that look identical from the outside cannot be
 * confused: not following at all, following and up to date, and following but
 * something is wrong. A silent "Following live" during a broker outage is the
 * failure this wording exists to prevent -- the whole point of the feature is
 * trusting that the number on screen is current.
 */
export function followLabel(state: FollowState): string {
  if (!state.enabled) return "Not following — the tape stops at the last loaded bar."
  if (state.waiting && state.lastAdded === null) return "Checking for new bars…"

  if (state.lastReason) {
    // A reason always wins over a count: it is the only thing that explains why
    // the tape might not be moving.
    return `Following live — ${state.lastReason}`
  }
  if (state.lastAdded === null) return "Following live — checking every minute."

  // Through liveEdgeLabel, not raw: the server sends ISO, and printing that
  // verbatim put "2026-08-17T11:43:00" in front of the user next to a tape whose
  // own column reads "11:43". Caught in the browser, not by a unit test.
  const edge = liveEdgeLabel(state.dataTime)
  if (state.lastAdded > 0) {
    const bars = state.lastAdded === 1 ? "1 new bar" : `${state.lastAdded} new bars`
    return `Following live — ${bars}, now at ${edge ?? "the live edge"}.`
  }
  return `Following live — up to date at ${edge ?? "the last bar"}.`
}

/** Fold a reply into the state the label reads. */
export function applyExtendReply(state: FollowState, reply: ExtendReply): FollowState {
  return {
    ...state,
    waiting: false,
    lastAdded: reply.added,
    lastReason: reply.reason,
    // Keep the last known edge when a failed poll reports none, rather than
    // blanking a time the user was reading.
    dataTime: reply.data_time ?? state.dataTime,
  }
}

/**
 * Whether to start following on its own once playback reaches the live edge.
 *
 * Requested after a session sat frozen at 100% because the checkbox had not been
 * ticked -- which reads as "the live data does not work", and is the worst
 * failure available here: indistinguishable from a broken feed. Loading a session
 * that ends today is already a statement of intent to watch it live, so the
 * checkbox should be a way to STOP, not a step to remember.
 *
 * Only when new bars can actually arrive. Auto-following a past date, or
 * synthetic data, would light the control and then report that nothing will ever
 * print -- noise in place of a frozen tape.
 *
 * `endDateISO` is the session's end date (YYYY-MM-DD); `nowET` is a full
 * nowEasternLabel, so the comparison is against the MARKET's date. Comparing
 * against a local date would turn following off for the whole evening in Asia,
 * while New York is still trading.
 */
export function shouldAutoFollow(
  endDateISO: string,
  nowET: string,
  dataSource: string,
): boolean {
  return canReceiveNewBars(endDateISO, nowET, dataSource)
}

/**
 * Whether this session can receive new bars at all.
 *
 * Extracted because two separate decisions need it and only one of them had it,
 * which shipped a genuinely alarming line: a session ending 2025-01-07, loaded
 * on 2026-08-17, reported "845728 min behind the clock -- the feed itself may be
 * delayed". The arithmetic was right and the statement was nonsense. Nothing is
 * behind; that session simply belongs to last year.
 *
 * Synthetic data is excluded for the same reason it is excluded from following:
 * it is generated, so "new bars" is not a thing that happens to it.
 */
export function canReceiveNewBars(
  endDateISO: string,
  nowET: string,
  dataSource: string,
): boolean {
  if (dataSource === "synthetic") return false
  if (!/^\d{4}-\d{2}-\d{2}$/.test(endDateISO)) return false
  // The MARKET's date. A local date would switch this off for the whole evening
  // in Asia while New York is still trading.
  return endDateISO >= nowET.slice(0, 10)
}

/**
 * How far the newest shown bar sits behind the clock, in minutes.
 *
 * Reported because the gap was invisible and got read as a fault. A tape showing
 * 13:00 next to a broker platform showing 13:02 looks broken; the same tape
 * saying "1 bar behind the live edge" is obviously working as intended.
 *
 * Both arguments are naive Eastern labels (see nowEasternLabel), so the
 * arithmetic is on the market's clock, not the viewer's.
 */
export function minutesBehind(dataTime: string | null, nowET: string): number | null {
  const edge = liveEdgeLabel(dataTime)
  if (!edge) return null
  const ms = Date.parse(`${nowET.replace(" ", "T")}:00Z`)
         - Date.parse(`${edge.replace(" ", "T")}:00Z`)
  if (!Number.isFinite(ms)) return null
  return Math.max(0, Math.round(ms / 60_000))
}

/**
 * Why the tape is not on the current minute, in the user's terms.
 *
 * Two of the three causes are deliberate and one is not, and lumping them
 * together as "lag" is what made this look like a defect:
 *
 *   * one bar is withheld until it has CLOSED. A broker platform draws the bar
 *     in progress, whose high, low and close are still moving; this app shows
 *     only finished bars, because a bar that changes after the fact is what
 *     jammed live-follow in the first place. That is a difference in what is
 *     displayed, not a delay.
 *   * up to FOLLOW_POLL_MS passes before a closed bar is collected.
 *   * the provider's own feed may itself be behind.
 *
 * Anything past one bar plus a poll interval is NOT explained by this design,
 * and the wording says so rather than reassuring the user.
 */
export function lagNote(
  behind: number | null,
  timeframeMinutes: number,
  live: boolean = true,
): string | null {
  // A session that cannot receive new bars is not "behind" anything -- and the
  // reason line already says it ends in the past, so there is nothing to add.
  // Without this, a session from last year reported six figures of lag and
  // blamed the provider.
  if (!live) return null
  if (behind == null) return null
  const expected = timeframeMinutes + Math.ceil(FOLLOW_POLL_MS / 60_000)
  if (behind <= timeframeMinutes) {
    return `${behind} min behind the clock — the current bar is still forming and ` +
           `is shown only once it closes.`
  }
  if (behind <= expected) {
    return `${behind} min behind the clock — one unfinished bar, plus up to ` +
           `${Math.ceil(FOLLOW_POLL_MS / 1000)}s to collect the last closed one.`
  }
  return `${behind} min behind the clock — further behind than the ` +
         `${expected} min this design accounts for, so the feed itself may be delayed.`
}

/**
 * The bar-label form of a `data_time` timestamp, for comparing against the tape.
 *
 * The server sends ISO ("2026-08-17T09:26:00"); the tape's own labels are space
 * separated without seconds. "T" sorts after " ", so comparing the two raw makes
 * every bar on the same date look EARLIER than the live edge -- the same class
 * of bug barOpenLabel exists to prevent.
 */
export function liveEdgeLabel(dataTime: string | null): string | null {
  if (!dataTime) return null
  const m = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/.exec(dataTime)
  return m ? `${m[1]} ${m[2]}` : null
}

/**
 * Should a closed WebSocket be reported to the user as a lost session?
 *
 * Replay sessions live in a plain dict in the API process, so anything that
 * replaces that process -- a deploy, a crash, an OOM kill -- silently takes
 * every running replay with it. The socket then closes with no further
 * messages, and with no handler the UI carried on showing "Playing" over a
 * frozen chart. A person watching that has no way to tell it from a bug in the
 * tape, which is exactly how it was reported.
 *
 * Three closes must stay quiet:
 *   - one we asked for (loading a new session, changing setup, unmounting)
 *   - one belonging to a socket a newer session already replaced
 *   - one that arrives after the tape finished, which is just tidying up
 */
export function isLostSession(args: {
  /** Did we initiate this close ourselves? */
  deliberate: boolean
  /** Is this still the socket the page is using? */
  current: boolean
  /** Playback status at the moment the socket closed. */
  status: "idle" | "loading" | "ready" | "playing" | "paused" | "done"
}): boolean {
  if (args.deliberate) return false
  if (!args.current) return false
  return args.status !== "idle" && args.status !== "done"
}
