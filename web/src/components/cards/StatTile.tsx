// The summary tiles above the tables: label, big value, optional delta, and a
// small visual on the right.
//
// The visuals are hand-rolled SVG rather than recharts. Seven of these render
// on every frame of a replay; a charting library per tile costs a mount, a
// resize observer and a re-render each, for a shape that is one <polyline>.
//
// Every visual is driven by the SAME numbers as the value beside it, so a tile
// can never show a rising spark next to a falling figure.

import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

export type Tone = "good" | "bad" | "neutral"

const STROKE: Record<Tone, string> = {
  good: "#22c55e",
  bad: "#ef4444",
  neutral: "#7aa2ff",
}

/** Line through a series, normalised to the box. Flat line if it cannot vary. */
function Spark({ data, tone }: { data: number[]; tone: Tone }) {
  const W = 78, H = 30
  if (data.length < 2) {
    return (
      <svg width={W} height={H} aria-hidden className="opacity-30">
        <line x1="0" y1={H / 2} x2={W} y2={H / 2}
              stroke={STROKE[tone]} strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    )
  }
  const min = Math.min(...data), max = Math.max(...data)
  const span = max - min || 1
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * W
    const y = H - 3 - ((v - min) / span) * (H - 6)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  const id = `sp-${tone}-${data.length}-${Math.round(max)}`
  return (
    <svg width={W} height={H} aria-hidden>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={STROKE[tone]} stopOpacity="0.28" />
          <stop offset="100%" stopColor={STROKE[tone]} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`0,${H} ${pts.join(" ")} ${W},${H}`} fill={`url(#${id})`} />
      <polyline
        points={pts.join(" ")}
        fill="none" stroke={STROKE[tone]} strokeWidth="1.6"
        strokeLinejoin="round" strokeLinecap="round"
      />
    </svg>
  )
}

/** Column chart -- used where the series is a count, not a level. */
function Bars({ data, tone }: { data: number[]; tone: Tone }) {
  const W = 78, H = 30, n = Math.min(data.length, 12)
  const tail = data.slice(-n)
  const max = Math.max(...tail, 1)
  const bw = n ? W / n : W
  return (
    <svg width={W} height={H} aria-hidden>
      {tail.map((v, i) => {
        const h = Math.max(2, (Math.abs(v) / max) * (H - 4))
        return (
          <rect key={i} x={i * bw + 1} y={H - h} width={Math.max(1.5, bw - 2)} height={h}
                rx="1" fill={STROKE[tone]} opacity={0.45 + 0.55 * (Math.abs(v) / max)} />
        )
      })}
    </svg>
  )
}

/** Ring -- used for a single percentage. */
function Donut({ pct, tone }: { pct: number; tone: Tone }) {
  const S = 34, R = 13, C = 2 * Math.PI * R
  const v = Math.min(100, Math.max(0, pct))
  return (
    <svg width={S} height={S} viewBox="0 0 34 34" aria-hidden>
      <circle cx="17" cy="17" r={R} fill="none" stroke="currentColor"
              strokeOpacity="0.14" strokeWidth="4" />
      <circle
        cx="17" cy="17" r={R} fill="none" stroke={STROKE[tone]} strokeWidth="4"
        strokeLinecap="round" strokeDasharray={`${(C * v) / 100} ${C}`}
        transform="rotate(-90 17 17)"
        style={{ transition: "stroke-dasharray 220ms cubic-bezier(0.22,1,0.36,1)" }}
      />
    </svg>
  )
}

interface StatTileProps {
  label: string
  value: string
  /** Small line under the value, e.g. "+99.94%". */
  delta?: string
  deltaTone?: Tone
  /** Colours the value text. */
  tone?: Tone
  /** Pick exactly one visual. */
  spark?: number[]
  bars?: number[]
  donut?: number
  icon?: ReactNode
}

export function StatTile({
  label, value, delta, deltaTone = "neutral", tone = "neutral",
  spark, bars, donut, icon,
}: StatTileProps) {
  const valueColor =
    tone === "good" ? "text-emerald-400"
      : tone === "bad" ? "text-red-400"
        : "text-slate-100"

  return (
    <div className="group relative overflow-hidden rounded-xl border border-white/8
                    bg-[#0c1322] px-3.5 py-3 transition-colors duration-200
                    hover:border-white/16">
      {/* hairline of the tile's own colour along the top */}
      <span aria-hidden className="absolute inset-x-0 top-0 h-px opacity-60"
            style={{ background: STROKE[tone] }} />

      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[11px] font-medium text-slate-400 truncate">{label}</div>
          <div className={cn("mt-1 text-[22px] font-bold leading-none tabular-nums tracking-tight",
                             valueColor)}>
            {value}
          </div>
          {delta && (
            <div className={cn(
              "mt-1.5 text-[11px] font-semibold tabular-nums",
              deltaTone === "good" ? "text-emerald-400"
                : deltaTone === "bad" ? "text-red-400" : "text-slate-500",
            )}>
              {delta}
            </div>
          )}
        </div>

        <div className="shrink-0 self-end text-slate-500">
          {spark ? <Spark data={spark} tone={tone} />
            : bars ? <Bars data={bars} tone={tone} />
              : donut !== undefined ? <Donut pct={donut} tone={tone} />
                : icon}
        </div>
      </div>
    </div>
  )
}
