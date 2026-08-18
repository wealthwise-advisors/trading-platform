/**
 * The six stages a backtest actually runs through, as a live pipeline.
 *
 * This exists because the results pane, before a run, was one sentence in the
 * middle of an empty screen. Someone opening the app for the first time had no
 * way to see what pressing Run Backtest was going to DO. The six stages are the
 * real ones -- market data in, resampled to the chosen timeframe, analysed,
 * traded by the strategy, filled by the paper broker, scored -- so the empty
 * state now explains the machine instead of apologising for being empty.
 *
 * WHY CSS AND SVG RATHER THAN framer-motion
 * -----------------------------------------
 * framer-motion is in package.json but is used by nothing in this codebase; the
 * animation that ships (the loading ring, the tick bar) is CSS keyframes with a
 * prefers-reduced-motion block. Following that costs no new runtime, keeps the
 * whole thing off the JS thread -- transform and opacity only, so it composites
 * on the GPU and cannot jank the chart -- and means one convention rather than
 * two. See index.css for the keyframes.
 *
 * WHAT IS DELIBERATELY NOT HERE
 * -----------------------------
 * No hero title, no closing slogan, no row of adjectives underneath. Those were
 * framing for a poster; this is a component inside an application, and an
 * application does not need to tell you it is reliable. The stage badges are the
 * only claims made, and each names something the code does.
 */

import {
  Download, Database, Waves, Target, Receipt, TrendingUp, type LucideIcon,
} from "lucide-react"

interface Stage {
  /** Displayed as 01..06; derived from position so it cannot fall out of step. */
  title: string
  description: string
  /** The one claim each stage makes. Every one names something real. */
  badge: string
  Icon: LucideIcon
  /** Drives the ring, the number, the badge and the glow for this stage. */
  accent: string
}

export const PIPELINE_STAGES: readonly Stage[] = [
  {
    title: "Market Data",
    description: "Bars from your chosen source",
    badge: "Schwab · Rithmic · CSV",
    Icon: Download,
    accent: "#38bdf8",
  },
  {
    title: "Resample",
    description: "Normalise & align across timeframes",
    badge: "One aggregator",
    Icon: Database,
    accent: "#2dd4bf",
  },
  {
    title: "Analysis",
    description: "Extract structure & market context",
    badge: "Waves · VWAP",
    Icon: Waves,
    accent: "#3b82f6",
  },
  {
    title: "Strategy",
    description: "Apply rules & generate signals",
    badge: "Signal",
    Icon: Target,
    accent: "#a855f7",
  },
  {
    title: "Paper Broker",
    description: "Simulate fills, slippage & costs",
    badge: "Fills · Costs",
    Icon: Receipt,
    accent: "#f97316",
  },
  {
    title: "Scored Result",
    description: "Objective metrics you can check",
    // The reference said "reproducible", which is an adjective rather than a
    // thing the stage produces -- and it collided with the feature row that was
    // removed. These are the metrics the scorer actually computes; see
    // src/backtesting (win_rate, sharpe_ratio, max_drawdown_pct).
    badge: "Sharpe · Drawdown",
    Icon: TrendingUp,
    accent: "#22c55e",
  },
] as const

/** Circumference of the r=30 ring, for the arc's dash maths. */
const RING_CIRCUMFERENCE = 2 * Math.PI * 30

function StageRing({ accent, Icon }: { accent: string; Icon: LucideIcon }) {
  return (
    <span className="pipeline-node" style={{ ["--accent" as string]: accent }}>
      <svg viewBox="0 0 72 72" className="pipeline-ring" aria-hidden>
        {/* The full ring, faint: the track the bright arc runs on. */}
        <circle cx="36" cy="36" r="30" fill="none"
                stroke="currentColor" strokeOpacity=".22" strokeWidth="1.6" />
        {/* A quarter-arc, rotating. One dash and one very long gap, so exactly
            one arc exists no matter what the circumference rounds to. */}
        <circle cx="36" cy="36" r="30" fill="none"
                stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"
                className="pipeline-arc"
                strokeDasharray={`${RING_CIRCUMFERENCE * 0.24} ${RING_CIRCUMFERENCE}`} />
        {/* The seat the icon sits on. */}
        <circle cx="36" cy="36" r="23.5" fill="currentColor" fillOpacity=".07" />
      </svg>
      <Icon className="pipeline-icon" aria-hidden strokeWidth={1.75} />
    </span>
  )
}

interface Props {
  className?: string
}

export function PipelineFlow({ className }: Props) {
  return (
    <div className={`pipeline${className ? ` ${className}` : ""}`}>
      {/*
        The connector, behind the nodes. Six equal columns put the first node's
        centre at 1/12 of the width and the last at 11/12, so the line spans
        exactly between them -- no measuring, and it stays correct at any width.
        Hidden below the six-across breakpoint, where the nodes wrap and a
        straight horizontal line would no longer join anything.
      */}
      <div className="pipeline-track" aria-hidden>
        {/*
          One link per gap, not one rail across the whole row. A single rail ran
          straight through the middle of every node -- the rings are translucent,
          so it showed inside them. A link inset by the node radius at each end
          starts and stops exactly at the circles' edges.

          It also buys the sequential flow for free: each link's dot is delayed a
          little more than the last, so one wave travels 01 to 06 rather than six
          dots drifting independently.
        */}
        {PIPELINE_STAGES.slice(0, -1).map((s, i) => (
          <span key={s.title} className="pipeline-link"
                style={{
                  ["--k" as string]: i,
                  // The link carries the two stages it joins, so the colour
                  // hands off along the row instead of the whole rail being one
                  // neutral grey.
                  ["--from" as string]: s.accent,
                  ["--to" as string]: PIPELINE_STAGES[i + 1].accent,
                }}>
            <span className="pipeline-rail" />
            <span className="pipeline-comet" />
          </span>
        ))}
      </div>

      <ol className="pipeline-stages">
        {PIPELINE_STAGES.map((s, i) => (
          <li key={s.title} className="pipeline-stage"
              style={{ ["--i" as string]: i, ["--accent" as string]: s.accent }}>
            <span className="pipeline-index">
              {String(i + 1).padStart(2, "0")}
            </span>
            <span className="pipeline-stem" aria-hidden />
            <StageRing accent={s.accent} Icon={s.Icon} />
            <h4 className="pipeline-title">{s.title}</h4>
            <p className="pipeline-desc">{s.description}</p>
            <span className="pipeline-badge">{s.badge}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}
