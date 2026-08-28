// Two panels of the setup form: the session summary beside the date row, and
// the card each strategy parameter gets.
//
// The summary panel restates what the fields to its left add up to. That
// sounds redundant and isn't: "18 Aug to 22 Aug" and "5 days" and "5m bars"
// and "6h 30m of session" are four separate derivations of the same choice,
// and getting one of them wrong is the mistake this whole step exists to
// prevent. Reading them together is how you catch it before Load Data.
//
// The parameter cards exist because a bare slider says nothing about what
// moving it does. Colour ties each one to the line it draws on the chart --
// overbought red, oversold green -- so the panel and the chart agree.

import type { ReactNode } from "react"
import { CalendarDays, Clock, Layers3, Timer } from "lucide-react"
import { CountUp } from "@/components/motion/primitives"
import { Slider } from "@/components/ui/slider"

/* ── session summary ──────────────────────────────────────────────────── */

export interface SummaryRow {
  label: string
  value: ReactNode
  Icon: typeof Clock
}

export function makeSummaryRows(opts: {
  days: number
  sessions: number
  timeframe: string
  duration: string
}): SummaryRow[] {
  return [
    {
      label: "Total period", Icon: CalendarDays,
      value: <><CountUp value={opts.days} />{opts.days === 1 ? " Day" : " Days"}</>,
    },
    {
      label: "Trading sessions", Icon: Layers3,
      value: <CountUp value={opts.sessions} />,
    },
    { label: "Selected timeframe", Icon: Clock, value: opts.timeframe },
    { label: "Total duration", Icon: Timer, value: opts.duration },
  ]
}

export function SummaryPanel({ rows }: { rows: SummaryRow[] }) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-violet-400/25
                    bg-gradient-to-b from-violet-500/[0.07] to-transparent px-4 py-3">
      <div className="space-y-2.5">
        {rows.map((r) => (
          <div key={r.label} className="flex items-center gap-2.5">
            <r.Icon size={14} strokeWidth={2} className="text-violet-400 shrink-0" />
            <span className="text-[11px] font-bold uppercase tracking-[0.07em] text-slate-400">
              {r.label}
            </span>
            <span className="ml-auto text-[13.5px] font-bold text-violet-300 tabular-nums whitespace-nowrap">
              {r.value}
            </span>
          </div>
        ))}
      </div>
      {/* A quiet trace along the foot. Decoration, and marked as such -- it
          carries no data and must never be read as a chart. */}
      <svg aria-hidden viewBox="0 0 120 16" preserveAspectRatio="none"
           className="absolute inset-x-0 bottom-0 h-4 w-full opacity-30">
        <polyline
          points="0,13 10,10 20,12 30,6 40,9 50,4 60,8 70,3 80,7 90,2 100,6 110,3 120,5"
          fill="none" stroke="#38bdf8" strokeWidth="1" vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  )
}

/* ── strategy parameter card ──────────────────────────────────────────── */

/** Colour per parameter, matched to the line it controls on the chart. */
const PARAM_TONE: Record<string, { bar: string; text: string; ring: string }> = {
  rsi_overbought: { bar: "#ef4444", text: "text-red-400", ring: "border-red-400/45" },
  rsi_oversold: { bar: "#22c55e", text: "text-emerald-400", ring: "border-emerald-400/45" },
}
const DEFAULT_TONE = { bar: "#7c6cf5", text: "text-violet-300", ring: "border-violet-400/40" }

export function ParamCard({
  name, label, value, min, max, step, disabled, title, onChange, Icon,
}: {
  name: string
  label: string
  value: number
  min: number
  max: number
  step: number
  disabled?: boolean
  title?: string
  onChange: (v: number) => void
  Icon: typeof Clock
}) {
  const tone = PARAM_TONE[name] ?? DEFAULT_TONE
  return (
    <div className="rounded-xl border border-white/8 bg-[#0b1322] px-4 py-3.5">
      <div className="flex items-center gap-2.5">
        <Icon size={16} strokeWidth={2} className={tone.text} />
        <span className="text-[11.5px] font-bold uppercase tracking-[0.07em] text-slate-300">
          {label}
        </span>
        <span
          className={`ml-auto min-w-[46px] rounded-lg border ${tone.ring} bg-white/[0.03]
                      px-2 py-1 text-center text-[13px] font-bold tabular-nums ${tone.text}`}
        >
          {value}
        </span>
      </div>

      {/* The track takes the parameter's own colour, so the control and the
          line it moves on the chart are recognisably the same thing. */}
      <div className="mt-3" style={{ ["--param-bar" as string]: tone.bar }}>
        <Slider
          className="param-slider"
          min={min} max={max} step={step}
          value={[value]} disabled={disabled} title={title}
          onValueChange={([v]) => onChange(v)}
        />
      </div>

      <div className="mt-1.5 flex justify-between text-[10.5px] font-medium text-slate-500 tabular-nums">
        <span>{min}</span>
        <span>{Math.round((min + max) / 2)}</span>
        <span>{max}</span>
      </div>
    </div>
  )
}
