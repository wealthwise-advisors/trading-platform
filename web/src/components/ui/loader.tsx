// Loading indicator: a glowing holographic ring.
//
// There was no shared loading component before this -- four places each rendered
// their own line of grey text ("Loading results…", "Checking Schwab
// connection…", and so on). This is that one component, so a change to the
// loading look lands everywhere at once.
//
// Built from SVG arcs and CSS keyframes only. No canvas, no video, no image
// asset, nothing fetched at runtime -- which also means it costs nothing to
// render while the main thread is busy waiting on data, and it cannot be broken
// by the strict CSP the app is served under.
//
// Colours come from the existing theme tokens rather than new constants:
// --primary (#7c6cf5) into --accent (#9b8afb), the same pair used by the
// buttons and badges.

import { useId } from "react"

interface LoaderProps {
  /** Diameter in px. 20 suits inline/button use, 56+ suits a panel. */
  size?: number
  /** Accessible name; also shown by LoadingBlock as a caption. */
  label?: string
  /**
   * "brand"   — the --primary/--accent gradient. For dark surfaces.
   * "current" — inherits currentColor. Needed ON a filled accent surface: a
   *             brand-coloured ring inside a --primary button is the same blue
   *             as the button and effectively invisible.
   */
  tone?: "brand" | "current"
  className?: string
}

/**
 * The ring on its own.
 *
 * Four layers, deliberately at different speeds so the motion reads as
 * mechanical rather than as a single spinning graphic:
 *   1. a static track, so the ring still has a shape between sweeps
 *   2. a long gradient sweep clockwise
 *   3. a shorter counter-rotating sweep, which is what stops it looking like
 *      an ordinary spinner
 *   4. dashed tick marks turning slowly, for the holographic instrument feel
 * plus a pulsing core.
 */
export function Loader({ size = 24, label = "Loading", tone = "brand", className = "" }: LoaderProps) {
  // Unique per instance: two loaders on one page must not share gradient ids.
  const uid = useId().replace(/:/g, "")
  const gradient = `ldr-grad-${uid}`
  const glow = `ldr-glow-${uid}`

  // Geometry is expressed in a fixed 48-unit viewBox and scaled by `size`, so
  // stroke weights stay proportional at every size.
  const R_OUTER = 20
  const R_MID = 14
  const R_TICKS = 23
  const circ = (r: number) => 2 * Math.PI * r

  const solid = tone === "current" ? "currentColor" : "var(--primary)"
  const second = tone === "current" ? "currentColor" : "var(--accent)"
  const sweepStroke = tone === "current" ? "currentColor" : `url(#${gradient})`

  return (
    <span
      className={`ldr-root ${className}`}
      style={{ width: size, height: size }}
      role="status"
      aria-label={label}
    >
      <svg viewBox="0 0 48 48" width={size} height={size} aria-hidden="true">
        <defs>
          <linearGradient id={gradient} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--primary)" stopOpacity="0" />
            <stop offset="45%" stopColor="var(--primary)" stopOpacity="0.9" />
            <stop offset="100%" stopColor="var(--accent)" />
          </linearGradient>
          <filter id={glow} x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="1.4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* 4. slow tick ring */}
        <circle
          className="ldr-ticks" cx="24" cy="24" r={R_TICKS}
          fill="none" stroke={solid} strokeOpacity="0.28"
          strokeWidth="1" strokeDasharray="1 5" strokeLinecap="round"
        />
        {/* 1. static track */}
        <circle
          cx="24" cy="24" r={R_OUTER}
          fill="none" stroke={solid} strokeOpacity="0.13" strokeWidth="3"
        />
        {/* 2. main sweep, clockwise */}
        <circle
          className="ldr-sweep" cx="24" cy="24" r={R_OUTER}
          fill="none" stroke={sweepStroke} strokeWidth="3" strokeLinecap="round"
          strokeDasharray={`${circ(R_OUTER) * 0.62} ${circ(R_OUTER)}`}
          filter={`url(#${glow})`}
        />
        {/* 3. counter-rotating inner sweep */}
        <circle
          className="ldr-sweep-rev" cx="24" cy="24" r={R_MID}
          fill="none" stroke={second} strokeOpacity="0.75"
          strokeWidth="1.5" strokeLinecap="round"
          strokeDasharray={`${circ(R_MID) * 0.22} ${circ(R_MID)}`}
        />
        {/* pulsing core */}
        <circle className="ldr-core" cx="24" cy="24" r="3.2" fill={solid} />
      </svg>
    </span>
  )
}

/**
 * The ring centred in a block, with a caption underneath -- for the case where
 * a whole panel or route is waiting on data.
 */
export function LoadingBlock({
  label = "Loading",
  hint,
  size = 56,
  tone = "brand",
  className = "",
}: LoaderProps & { hint?: string }) {
  return (
    <div className={`flex flex-col items-center justify-center gap-3 py-10 ${className}`}>
      <Loader size={size} tone={tone} label={label} />
      <div className="text-center">
        <p className="text-sm text-muted-foreground">{label}</p>
        {hint && <p className="text-xs text-muted-foreground/70 mt-0.5">{hint}</p>}
      </div>
    </div>
  )
}
