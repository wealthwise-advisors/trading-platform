// Two pieces of chrome that bracket the setup form: the summary chips that sit
// beside the transport buttons, and the hint strip at the foot of the page.
//
// The chips exist because Load Data is irreversible-ish -- it fetches a range
// and locks symbol, source, strategy and capital for the session. Restating
// those four right beside the button is the last chance to catch "I meant
// Synthetic, not Schwab" before waiting on a download.
//
// The strip's field animates only while data is actually moving. An ambient
// loop that runs on an idle screen is decoration pretending to be status; one
// that stops when the feed stops is status.

import type { ReactNode } from "react"
import { Database, Cpu, CandlestickChart, LayoutGrid } from "lucide-react"
import { Reveal, motion, useReducedMotion } from "@/components/motion/primitives"

export function SummaryChips({
  source, strategy, dataType, mode, sourceLive,
}: {
  source: string
  strategy: string
  dataType: string
  mode: string
  sourceLive?: boolean
}) {
  const items: { label: string; value: ReactNode; Icon: typeof Database }[] = [
    {
      label: "Data source", Icon: Database,
      value: (
        <span className="flex items-center gap-1.5">
          {source}
          {sourceLive && (
            <span className="rounded px-1 py-px text-[9px] font-bold tracking-[0.08em]
                             bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-400/30">
              LIVE
            </span>
          )}
        </span>
      ),
    },
    { label: "Strategy", value: strategy, Icon: Cpu },
    { label: "Data type", value: dataType, Icon: CandlestickChart },
    { label: "Mode", value: mode, Icon: LayoutGrid },
  ]

  return (
    <div className="flex flex-wrap items-stretch gap-x-6 gap-y-3 rounded-xl
                    border border-white/8 bg-[#0b1322] px-4 py-2.5">
      {items.map((it, i) => (
        <div key={it.label}
             className={i > 0 ? "pl-6 border-l border-white/8 min-w-0" : "min-w-0"}>
          <div className="text-[10px] font-bold uppercase tracking-[0.09em] text-slate-500">
            {it.label}
          </div>
          <div className="mt-0.5 flex items-center gap-1.5 text-[13px] font-semibold
                          text-slate-200 truncate">
            <it.Icon size={13} strokeWidth={2} className="text-slate-500 shrink-0" />
            {it.value}
          </div>
        </div>
      ))}
    </div>
  )
}

/** Slow-drifting constellation. Static unless `active`. */
function Constellation({ active }: { active: boolean }) {
  const reduced = useReducedMotion()
  const moving = active && !reduced

  // Fixed geometry -- deterministic, so it never re-randomises on re-render
  // and never causes a layout shift.
  const pts = [
    [4, 62], [12, 48], [21, 66], [29, 40], [38, 58], [46, 34],
    [55, 54], [63, 30], [72, 52], [80, 36], [88, 60], [96, 44],
  ] as const

  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden
         className="absolute inset-0 h-full w-full">
      <defs>
        <linearGradient id="cst" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#7c6cf5" stopOpacity="0.15" />
          <stop offset="50%" stopColor="#9b8afb" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.15" />
        </linearGradient>
      </defs>
      <motion.g
        animate={moving ? { x: [0, -8, 0] } : { x: 0 }}
        transition={moving
          ? { duration: 14, repeat: Infinity, ease: "easeInOut" }
          : { duration: 0 }}
      >
        <polyline
          points={pts.map(([x, y]) => `${x},${y}`).join(" ")}
          fill="none" stroke="url(#cst)" strokeWidth="0.5"
          vectorEffect="non-scaling-stroke"
        />
        {pts.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r="0.7" fill="#9b8afb"
                  opacity={0.35 + (i % 3) * 0.2} vectorEffect="non-scaling-stroke" />
        ))}
      </motion.g>
    </svg>
  )
}

export function SetupFooterHint({
  active, children,
}: {
  /** Feed moving -- drives the field and the tone of the copy. */
  active: boolean
  children: ReactNode
}) {
  return (
    <Reveal delay={0.12}>
      <div className="relative overflow-hidden rounded-2xl border border-white/8
                      bg-[#080d1a] h-[92px] grid place-items-center">
        <Constellation active={active} />
        <div aria-hidden className="absolute inset-0"
             style={{ background: "linear-gradient(180deg,#080d1a00,#080d1acc)" }} />
        <p className="relative text-[13.5px] text-slate-400 text-center px-4">
          {children}
        </p>
      </div>
    </Reveal>
  )
}
