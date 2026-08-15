// Circular progress gauge -- an analog dial, not a spinner.
//
// The distinction matters and it is the whole point of this component: the
// loading ring in ui/loader.tsx is INDETERMINATE. Its arcs sweep at a fixed
// rate that is not tied to any quantity, because the thing it covers (a single
// fetch) reports no progress to be tied to. This one is DETERMINATE: the swept
// angle is the value, so a half-filled dial means exactly half done.
//
// Styled to match the loader and the tick bar -- same --primary to --accent
// sweep, same glow -- so the app has one visual language for "work happening".

import { useId } from "react"

interface GaugeProps {
  /** 0-100. Clamped, so a caller cannot draw an over-full dial. */
  value: number
  size?: number
  /** Big number in the middle. Defaults to the rounded percentage. */
  label?: string
  /** Small caption under the number. */
  sub?: string
  className?: string
}

/** Degrees of dial that are actually drawn. A car dial leaves a gap at the
 *  bottom rather than closing the circle -- it makes the empty and full ends
 *  distinguishable at a glance, which a full 360 ring does not. */
const SWEEP = 270
const START = 135 // 0% sits lower-left, like a speedometer's rest position

export function Gauge({ value, size = 132, label, sub, className = "" }: GaugeProps) {
  const uid = useId().replace(/:/g, "")
  const grad = `gauge-grad-${uid}`
  const glow = `gauge-glow-${uid}`

  const pct = Math.min(100, Math.max(0, Number.isFinite(value) ? value : 0))

  // Geometry in a fixed 100-unit box, scaled by `size`, so stroke weights stay
  // proportional at any size.
  const R = 40
  const CIRC = 2 * Math.PI * R
  const arcLen = (CIRC * SWEEP) / 360
  const filled = (arcLen * pct) / 100

  // Tick marks every 10%, so the dial can be read approximately without the
  // number -- the thing that makes a gauge a gauge.
  const ticks = Array.from({ length: 11 }, (_, i) => {
    const a = ((START + (SWEEP * i) / 10) * Math.PI) / 180
    const major = i % 5 === 0
    const r1 = R + 7
    const r2 = R + (major ? 12 : 10)
    return {
      x1: 50 + r1 * Math.cos(a), y1: 50 + r1 * Math.sin(a),
      x2: 50 + r2 * Math.cos(a), y2: 50 + r2 * Math.sin(a),
      major, lit: pct >= i * 10,
    }
  })

  return (
    <div className={`inline-flex flex-col items-center ${className}`}
         role="progressbar" aria-valuemin={0} aria-valuemax={100}
         aria-valuenow={Math.round(pct)} aria-label={sub ?? "Progress"}>
      <svg viewBox="0 0 100 100" width={size} height={size}>
        <defs>
          <linearGradient id={grad} x1="0" y1="1" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--primary)" />
            <stop offset="100%" stopColor="var(--accent)" />
          </linearGradient>
          <filter id={glow} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {ticks.map((t, i) => (
          <line key={i} x1={t.x1} y1={t.y1} x2={t.x2} y2={t.y2}
                stroke={t.lit ? "var(--accent)" : "currentColor"}
                strokeOpacity={t.lit ? 0.85 : 0.18}
                strokeWidth={t.major ? 1.6 : 0.9} strokeLinecap="round" />
        ))}

        {/* Unfilled track: the full 270 degrees, so "empty" still reads as a dial. */}
        <circle
          cx="50" cy="50" r={R} fill="none"
          stroke="currentColor" strokeOpacity="0.12" strokeWidth="8" strokeLinecap="round"
          strokeDasharray={`${arcLen} ${CIRC}`}
          transform={`rotate(${START} 50 50)`}
        />
        {/* The value. strokeDasharray is the measurement -- this arc IS the number. */}
        <circle
          cx="50" cy="50" r={R} fill="none"
          stroke={`url(#${grad})`} strokeWidth="8" strokeLinecap="round"
          strokeDasharray={`${filled} ${CIRC}`}
          transform={`rotate(${START} 50 50)`}
          filter={`url(#${glow})`}
          style={{ transition: "stroke-dasharray 200ms cubic-bezier(0.22,1,0.36,1)" }}
        />
      </svg>

      {/* Overlaid rather than placed below, so the number sits in the dial the
          way an odometer does. */}
      <div className="relative w-0 h-0">
        <div className="absolute -translate-x-1/2 flex flex-col items-center"
             style={{ top: -size * 0.62 }}>
          <span className="font-bold leading-none tabular-nums"
                style={{ fontSize: size * 0.24, letterSpacing: "-0.02em" }}>
            {label ?? `${Math.round(pct)}%`}
          </span>
          {sub && (
            <span className="text-muted-foreground mt-1 whitespace-nowrap"
                  style={{ fontSize: Math.max(9, size * 0.082) }}>
              {sub}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
