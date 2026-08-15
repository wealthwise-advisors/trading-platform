// Volume Profile, computed in the browser.
//
// WHY HERE AND NOT ON THE SERVER
// ------------------------------
// The server already computes a profile (src/analysis/indicators.py's
// calc_volume_profile) and the report exporters still use it. The dashboard
// needs a second, local copy because every one of its controls changes an
// input to the *bucketing*:
//
//   value area percent  — selection only; derivable from delivered buckets
//   bins                — re-buckets from raw bars; not derivable
//   opacity / show-hide — pure rendering
//
// VWAP's deviations could be rebuilt from the shipped ±2σ payload because σ
// was recoverable exactly. Bins cannot be: changing 48 to 96 needs the raw
// high/low/volume regrouped, which the delivered histogram has already thrown
// away. That left two options — a debounced refetch of /price-data on every
// bin change, or computing locally.
//
// Refetching would re-run EMA, RSI, Stochastic, VWAP and the profile on the
// server to change one rendering parameter, add latency to a slider drag, and
// still need bins plumbed up to ResultsPage where the query lives. Computing
// locally makes every control instant with no plumbing at all.
//
// The cost is a second implementation of the same algorithm, which is a real
// risk — so this file is verified numerically against the Python one rather
// than assumed to agree. See the equivalence check in the commit message.

export interface VPBar {
  h: number
  l: number
  v: number | null
}

export interface VPResult {
  prices: number[]
  volumes: number[]
  poc: number | null
  val: number | null
  vah: number | null
  binSize: number | null
}

const EMPTY: VPResult = {
  prices: [], volumes: [], poc: null, val: null, vah: null, binSize: null,
}

/**
 * Standard construction, mirroring calc_volume_profile():
 * the price range is split into `bins` equal buckets; each bar spreads its
 * volume evenly across the buckets its high–low range touches; POC is the
 * richest bucket; the value area grows outward from the POC, repeatedly
 * taking whichever neighbour holds more volume, until `valueAreaPct` of total
 * volume is enclosed.
 */
export function computeVolumeProfile(
  bars: VPBar[],
  bins = 48,
  valueAreaPct = 0.7,
): VPResult {
  if (!bars.length || bins < 1) return EMPTY

  let lo = Infinity
  let hi = -Infinity
  let totalVol = 0
  for (const b of bars) {
    if (b.l < lo) lo = b.l
    if (b.h > hi) hi = b.h
    totalVol += b.v ?? 0
  }
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi <= lo || totalVol <= 0) {
    return EMPTY
  }

  const width = (hi - lo) / bins
  const centers = Array.from({ length: bins }, (_, i) => lo + width * (i + 0.5))
  const bucket = new Array<number>(bins).fill(0)

  for (const b of bars) {
    const vol = b.v ?? 0
    if (vol <= 0) continue
    // Math.floor matches numpy's // on non-negative values; the clamp mirrors
    // np.clip and keeps the topmost bar inside the last bucket.
    const first = Math.min(Math.max(Math.floor((b.l - lo) / width), 0), bins - 1)
    const last = Math.min(Math.max(Math.floor((b.h - lo) / width), 0), bins - 1)
    const share = vol / (last - first + 1)
    for (let i = first; i <= last; i++) bucket[i] += share
  }

  const total = bucket.reduce((a, b) => a + b, 0)
  if (total <= 0) return EMPTY

  let pocI = 0
  for (let i = 1; i < bins; i++) if (bucket[i] > bucket[pocI]) pocI = i

  const target = total * valueAreaPct
  let covered = bucket[pocI]
  let below = pocI
  let above = pocI
  while (covered < target && (below > 0 || above < bins - 1)) {
    const takeBelow = below > 0 ? bucket[below - 1] : -1
    const takeAbove = above < bins - 1 ? bucket[above + 1] : -1
    if (takeAbove >= takeBelow) {
      above += 1
      covered += takeAbove
    } else {
      below -= 1
      covered += takeBelow
    }
  }

  return {
    prices: centers,
    volumes: bucket,
    poc: centers[pocI],
    val: lo + width * below,            // lower edge of the lowest VA bucket
    vah: lo + width * (above + 1),      // upper edge of the highest VA bucket
    binSize: width,
  }
}

// ── Multiple time-based profiles ────────────────────────────────────────────
// "time per profile" in the reference dialog. CHART builds one profile over
// everything visible; DAY/WEEK restart it each session, which is what makes a
// profile comparable between days rather than smeared across all of them.
// `multiplier` widens the period (DAY x 2 = two-day profiles) and `maxProfiles`
// keeps only the most recent N, matching the dialog's "profiles" count.

export type TimePerProfile = "CHART" | "DAY" | "WEEK"
export type RowHeightMode = "AUTOMATIC" | "MANUAL"

export interface ProfileSlice {
  /** ISO timestamp of the first bar in this profile. */
  startT: string
  /** ISO timestamp of the last bar in this profile. */
  endT: string
  profile: VPResult
}

export interface ProfileOptions {
  timePer?: TimePerProfile
  multiplier?: number
  maxProfiles?: number
  rowMode?: RowHeightMode
  /** Price units per row, used when rowMode is MANUAL. */
  customRowHeight?: number
  bins?: number
  valueAreaPct?: number
}

interface TimedBar extends VPBar {
  t: string
}

/** Base period a bar belongs to, before the multiplier is applied. */
function periodKey(iso: string, timePer: TimePerProfile): string {
  if (timePer === "CHART") return "all"
  const d = new Date(iso)
  const dayIndex = Math.floor(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate())
    / 86_400_000)
  if (timePer === "WEEK") return `w${Math.floor(dayIndex / 7)}`
  return `d${dayIndex}`
}

export function computeVolumeProfiles(
  bars: TimedBar[],
  opts: ProfileOptions = {},
): ProfileSlice[] {
  const {
    timePer = "CHART", multiplier = 1, maxProfiles = 1000,
    rowMode = "AUTOMATIC", customRowHeight = 1, bins = 48, valueAreaPct = 0.7,
  } = opts
  if (!bars.length) return []

  const groups = new Map<string, TimedBar[]>()
  const order: string[] = []
  for (const b of bars) {
    const k = periodKey(b.t, timePer)
    if (!groups.has(k)) { groups.set(k, []); order.push(k) }
    groups.get(k)!.push(b)
  }

  // The multiplier merges N CONSECUTIVE sessions present in the data, not N
  // calendar days. Bucketing by floor(dayIndex / multiplier) against the epoch
  // was tried first and behaves erratically once weekends and holidays create
  // gaps: over Jan 2/3/6 2025 a multiplier of 2 merged two sessions while 3
  // merged none, because the boundary happened to fall between the 2nd and
  // 3rd. Chunking the ordered session list makes "multiplier 3" mean three
  // sessions per profile regardless of which days those are.
  const step = Math.max(1, Math.floor(multiplier))
  const merged: TimedBar[][] = []
  for (let i = 0; i < order.length; i += step) {
    merged.push(order.slice(i, i + step).flatMap((k) => groups.get(k)!))
  }

  // "profiles" in the dialog caps how many are kept; the most recent win.
  const kept = merged.slice(-Math.max(1, maxProfiles))

  const out: ProfileSlice[] = []
  for (const grp of kept) {
    // MANUAL row height fixes the price increment per row, so the bin COUNT
    // falls out of the group's own range rather than being fixed at 48.
    let binCount = bins
    if (rowMode === "MANUAL" && customRowHeight > 0) {
      let lo = Infinity, hi = -Infinity
      for (const b of grp) { if (b.l < lo) lo = b.l; if (b.h > hi) hi = b.h }
      if (Number.isFinite(lo) && Number.isFinite(hi) && hi > lo) {
        binCount = Math.max(1, Math.min(2000, Math.round((hi - lo) / customRowHeight)))
      }
    }
    const profile = computeVolumeProfile(grp, binCount, valueAreaPct)
    if (!profile.prices.length) continue
    out.push({ startT: grp[0].t, endT: grp[grp.length - 1].t, profile })
  }
  return out
}
