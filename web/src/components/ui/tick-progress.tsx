// Playback progress for Live Replay.
//
// Deliberately a sibling of components/ui/loader.tsx rather than a one-off in
// ReplayPage: the two are the app's only two "work in progress" indicators, and
// they now share a palette (--primary into --accent), a glow and an easing. The
// styling lives in index.css under ".tickbar-*" so the shimmer keyframes sit
// beside the ring's.
//
// The bar reports the SHARED CLOCK's position -- one tick per base-timeframe
// bar -- not any single pane's bar count, which is why the readout is in ticks.

import { Gauge } from "@/components/ui/gauge"

interface TickProgressProps {
  /** Ticks of the shared clock already replayed. */
  processed: number
  /** Total ticks in the session. */
  total: number
  /** Drives the shimmer; paused/idle shows a still bar. */
  playing?: boolean
  /** Right-hand caption, e.g. the market timestamp. */
  detail?: string
}

export function TickProgress({ processed, total, playing = false, detail }: TickProgressProps) {
  // total is 0 between "session created" and the first frame, so guard rather
  // than rendering a NaN width.
  const pct = total > 0 ? Math.min(100, Math.max(0, (processed / total) * 100)) : 0
  const done = total > 0 && processed >= total

  return (
    <div className="flex items-center gap-5">
      {/* The dial is the glanceable read -- percentage complete, in one look,
          the way a car gauge is read. The bar beside it keeps the fine-grained
          position that a 270-degree arc cannot resolve at a few hundred ticks.
          Both are driven by the same number, so they cannot disagree. */}
      <Gauge value={pct} size={104} sub="complete" />

      <div className="flex-1 space-y-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="tickbar-readout">
          <span className="text-foreground/80 font-medium">
            {processed.toLocaleString()}
          </span>
          <span className="opacity-60"> / {total.toLocaleString()} ticks</span>
          {detail && <span className="opacity-60"> · {detail}</span>}
        </span>
        <span className="tickbar-readout tabular-nums">
          {/* One decimal below 10%: a long replay sits at "0%" for many seconds
              otherwise, which reads as nothing happening. */}
          {pct < 10 && pct > 0 ? pct.toFixed(1) : Math.round(pct)}%
        </span>
      </div>

      <div
        className="tickbar-track"
        data-playing={playing && !done ? "true" : "false"}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total || 100}
        aria-valuenow={processed}
        aria-label="Replay progress"
      >
        <div className="tickbar-fill" style={{ width: `${pct}%` }} />
      </div>
      </div>
    </div>
  )
}
