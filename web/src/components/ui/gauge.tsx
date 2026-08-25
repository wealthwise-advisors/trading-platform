// Circular progress gauge -- an instrument dial, not a spinner.
//
// The distinction matters and it is the whole point of this component: the
// loading ring in ui/loader.tsx is INDETERMINATE. Its arcs sweep at a fixed
// rate that is not tied to any quantity, because the thing it covers (a single
// fetch) reports no progress to be tied to. This one is DETERMINATE: the swept
// angle is the value, so a half-filled dial means exactly half done.
//
// THE FACE
// --------
// Drawn as a machined instrument: a ring of thick radial bars that light up to
// the current reading, a numbered scale outside them, a swept arc with a
// glowing knob riding its end, and a dark disc carrying the value.
//
// The scale is a PERCENTAGE, 0 to 100 -- ten numbered stops, one per 10%. It
// carries no units and no secondary readouts. Nothing appears on the face that
// is not the single quantity being reported: a dial showing invented numbers
// beside a real progress bar is worse than no dial, and this one is driven by
// the same value as the bar next to it.

import { useId } from "react"

interface GaugeProps {
  /** 0-100. Clamped, so a caller cannot draw an over-full dial. */
  value: number
  size?: number
  /** Big number in the middle. Defaults to the rounded percentage. */
  label?: string
  /** Small caption under the number. Omit for a face showing only the value. */
  sub?: string
  className?: string
}

/** Degrees of dial that are actually drawn. A car dial leaves a gap at the
 *  bottom rather than closing the circle -- it makes the empty and full ends
 *  distinguishable at a glance, which a full 360 ring does not. */
const SWEEP = 270
const START = 135 // 0 sits lower-left, like a speedometer's rest position

/** Bars around the face. 61 puts one every 1.67%, dense enough to read as a
 *  machined scale; every sixth is longer and carries a number, which lands
 *  them on 0, 10, 20 ... 100 exactly. */
const BARS = 61
const MAJOR_EVERY = 6

const R_LABEL = 46.5   // the numbered scale, outside everything
const R_BAR_OUT = 41   // outer end of a bar
const R_BAR_IN = 33.5  // inner end
const R_ARC = 26       // the swept value arc
const R_DISC = 21.5    // dark face the number sits on

const polar = (r: number, deg: number) => {
  const a = (deg * Math.PI) / 180
  return { x: 50 + r * Math.cos(a), y: 50 + r * Math.sin(a) }
}

export function Gauge({ value, size = 132, label, sub, className = "" }: GaugeProps) {
  const uid = useId().replace(/:/g, "")
  const arcG = `ga-${uid}`
  const knobG = `gk-${uid}`
  const glow = `gg-${uid}`
  const soft = `gs-${uid}`

  const pct = Math.min(100, Math.max(0, Number.isFinite(value) ? value : 0))

  const CIRC = 2 * Math.PI * R_ARC
  const arcLen = (CIRC * SWEEP) / 360
  const filled = (arcLen * pct) / 100

  const valueDeg = START + (SWEEP * pct) / 100
  const knob = polar(R_ARC, valueDeg)

  const bars = Array.from({ length: BARS }, (_, i) => {
    const frac = i / (BARS - 1)
    const deg = START + SWEEP * frac
    const major = i % MAJOR_EVERY === 0
    return { deg, major, frac, lit: pct >= frac * 100 - 0.001, n: Math.round(frac * 100) }
  })

  return (
    <div className={`inline-flex flex-col items-center ${className}`}
         role="progressbar" aria-valuemin={0} aria-valuemax={100}
         aria-valuenow={Math.round(pct)} aria-label={sub ?? "Progress"}>
      <svg viewBox="0 0 100 100" width={size} height={size}>
        <defs>
          {/* Deep orange at rest, brightening toward full -- the same warm ramp
              the bars use, so arc and scale agree about how far along you are. */}
          <linearGradient id={arcG} x1="0" y1="1" x2="1" y2="0">
            <stop offset="0%" stopColor="#ea580c" />
            <stop offset="50%" stopColor="#f97316" />
            <stop offset="100%" stopColor="#fbbf24" />
          </linearGradient>
          <radialGradient id={knobG}>
            <stop offset="0%" stopColor="#fff7ed" />
            <stop offset="45%" stopColor="#fdba74" />
            <stop offset="100%" stopColor="#f97316" />
          </radialGradient>
          <filter id={glow} x="-70%" y="-70%" width="240%" height="240%">
            <feGaussianBlur stdDeviation="1.5" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id={soft} x="-70%" y="-70%" width="240%" height="240%">
            <feGaussianBlur stdDeviation="2.6" />
          </filter>
        </defs>

        {/* Ambient warmth behind the face, so the lit bars sit in a glow rather
            than on flat black. */}
        <circle cx="50" cy="50" r="34" fill="#7c2d12" opacity="0.18" filter={`url(#${soft})`} />

        {/* THE BARS. Thick radial segments, not hairlines -- that weight is what
            makes the ring read as an instrument scale. */}
        {bars.map((b, i) => {
          const a = polar(R_BAR_IN, b.deg)
          const c = polar(b.major ? R_BAR_OUT + 1.5 : R_BAR_OUT, b.deg)
          return (
            <line key={i} x1={a.x} y1={a.y} x2={c.x} y2={c.y}
                  stroke={b.lit ? (b.major ? "#fbbf24" : "#fb923c") : "#78350f"}
                  strokeOpacity={b.lit ? 1 : b.major ? 0.55 : 0.38}
                  strokeWidth={b.major ? 3.2 : 2.1}
                  strokeLinecap="butt"
                  filter={b.lit ? `url(#${glow})` : undefined}
                  style={{ transition: "stroke 200ms linear, stroke-opacity 200ms linear" }} />
          )
        })}

        {/* The numbered scale: 0, 10, 20 ... 100, outside the bars. */}
        {bars.filter((b) => b.major).map((b, i) => {
          const p = polar(R_LABEL, b.deg)
          return (
            <text key={i} x={p.x} y={p.y} textAnchor="middle" dominantBaseline="central"
                  fontSize="5.2" fontWeight="700"
                  fill={b.lit ? "#fcd34d" : "#92400e"}
                  style={{ transition: "fill 200ms linear" }}>
              {b.n}
            </text>
          )
        })}

        {/* Unfilled track: the full 270 degrees, so "empty" still reads as a dial. */}
        <circle cx="50" cy="50" r={R_ARC} fill="none"
                stroke="#431407" strokeOpacity="0.9" strokeWidth="4.4" strokeLinecap="round"
                strokeDasharray={`${arcLen} ${CIRC}`}
                transform={`rotate(${START} 50 50)`} />

        {/* The value. strokeDasharray is the measurement -- this arc IS the number. */}
        {pct > 0 && (
        <circle cx="50" cy="50" r={R_ARC} fill="none"
                stroke={`url(#${arcG})`} strokeWidth="4.4" strokeLinecap="round"
                strokeDasharray={`${filled} ${CIRC}`}
                transform={`rotate(${START} 50 50)`}
                filter={`url(#${glow})`}
                style={{ transition: "stroke-dasharray 240ms cubic-bezier(0.22,1,0.36,1)" }} />
        )}

        {/* The dark face the value sits on. */}
        <circle cx="50" cy="50" r={R_DISC} fill="#140b06" fillOpacity="0.82" />

        {/* The knob riding the end of the arc -- what turns a filled bar into
            something that reads as a needle position. */}
        <circle cx={knob.x} cy={knob.y} r="4.2" fill={`url(#${knobG})`}
                filter={`url(#${glow})`}
                style={{ transition: "cx 240ms cubic-bezier(0.22,1,0.36,1), cy 240ms cubic-bezier(0.22,1,0.36,1)" }} />
      </svg>

      {/* Overlaid rather than placed below, so the number sits in the dial the
          way an odometer does. */}
      <div className="relative w-0 h-0">
        <div className="absolute -translate-x-1/2 flex flex-col items-center"
             style={{ top: -size * 0.585 }}>
          <span className="font-bold leading-none tabular-nums"
                style={{ fontSize: size * 0.152, letterSpacing: "-0.02em",
                         color: "#fb923c", textShadow: "0 0 14px rgba(249,115,22,0.55)" }}>
            {label ?? `${Math.round(pct)}%`}
          </span>
          {sub && (
            <span className="mt-1 whitespace-nowrap"
                  style={{ fontSize: Math.max(8, size * 0.062), color: "#b45309" }}>
              {sub}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
