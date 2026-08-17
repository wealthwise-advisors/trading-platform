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
 * One minute, matched to the one-minute source resolution: asking more often
 * cannot produce a bar that does not exist yet, it just multiplies provider
 * requests. Bars are also withheld by the server until they have actually
 * closed, so a faster poll would mostly be told "still forming".
 */
export const FOLLOW_POLL_MS = 60_000

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
