// Fixed categorical order — card N always gets slot N, regardless of value.
// CRITICAL stays a true red: it is the general "loss/negative" status colour
// used everywhere else (trade tables, P&L bars, exit markers), and unlike
// these six it carries meaning rather than just telling cards apart.
// All six are cool. Two were not: [2] was #F97316 (orange) and [4]
// #e0a72e (amber), left over from the reference palette. They mark a
// CATEGORY, not a status, so cooling them loses no meaning -- while GOOD
// and CRITICAL below stay green and red, because those two are meaning.
import type { ReactNode } from "react"

export const ACCENTS = ["#7c6cf5", "#9b8afb", "#56b6e8", "#22C55E", "#8fa6ff", "#c084fc"]
export const GOOD = "#22C55E"
export const CRITICAL = "#EF4444"
export const NEUTRAL = "#e8e9f2"
export const CYAN = "#14E0D4"

interface StatCardProps {
  label: string
  value: string
  accent: string
  /** A drawn icon. Not a string: an emoji would carry its own colour
   *  and could not follow the theme. */
  icon?: ReactNode
  valueColor?: string
  sub?: string
}

// Sparkline mini-charts removed -- numbers only, per explicit request to
// free up vertical space for the price chart. This card is now just
// label + value (+ optional sub line), sized to its own compact content
// instead of stretching to fill a tall row.
export function StatCard({
  label, value, accent, icon, valueColor = NEUTRAL, sub,
}: StatCardProps) {
  return (
    <div className="stat-card" style={{ ["--stat-accent" as string]: accent }}>
      {icon && (
        // Dimmed to match the card's new restraint: at 45% ring opacity the
        // chip was competing with the value for attention. It is a category
        // marker, not a data point.
        <span className="float-right -mt-0.5 -mr-0.5 w-5 h-5 rounded-full flex items-center justify-center text-[0.65rem] opacity-70"
              style={{
                background: `color-mix(in srgb, ${accent} 14%, transparent)`,
                boxShadow: `0 0 0 1px color-mix(in srgb, ${accent} 24%, transparent)`,
              }}>
          {icon}
        </span>
      )}
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={{ color: valueColor }}>{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  )
}
