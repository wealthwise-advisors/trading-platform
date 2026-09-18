// Fixed categorical order — card N always gets slot N, regardless of value.
// CRITICAL stays a true red: it is the general "loss/negative" status colour
// used everywhere else (trade tables, P&L bars, exit markers), and unlike
// these six it carries meaning rather than just telling cards apart.
// All six are cool. Two were not: [2] was #F97316 (orange) and [4]
// #e0a72e (amber), left over from the reference palette. They mark a
// CATEGORY, not a status, so cooling them loses no meaning -- while GOOD
// and CRITICAL below stay green and red, because those two are meaning.
import type { ReactNode } from "react"

export const ACCENTS = ["var(--primary)", "var(--accent)", "#56b6e8", "#22C55E", "#8fa6ff", "#c084fc"]
// Profit is green and loss is red in BOTH themes -- that is not a style
// choice to be re-decided per palette. What changes is lightness: #22c55e is
// 2.3:1 on paper and #EF4444 is 3.4:1, so a light theme rendering these as-is
// puts the two most important numbers on the page below the readable
// threshold. --gain / --loss / --flat are the same hues, each theme holding
// the version that clears contrast on its own surface.
//
// CSS ONLY. A Plotly layout is a JavaScript object and var() does not resolve
// in one, so PnlDistributionChart keeps its own literals -- see the note
// there. Everything else in the app draws these through the DOM.
export const GOOD = "var(--gain)"
export const CRITICAL = "var(--loss)"
export const NEUTRAL = "var(--flat)"
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
  /** Hover text, for a number whose full story does not fit in the card. */
  title?: string
}

/**
 * One KPI number: its name, its accent icon, and the value.
 *
 * The head is a real flex ROW -- label left, icon right -- because the icon
 * used to be `float-right` on a flex child, where a float does nothing at all.
 * It rendered above the label on the left instead, which is what made the card
 * 100px tall and unlike the reference.
 *
 * Every KPI on the page uses this one card, at one size. There was a `dense`
 * variant for the Avg Win / Avg Loss pair; that pair is now two ordinary cells
 * of the same grid as the rest, so a second size would only be a way for the
 * row to disagree with itself.
 */
export function StatCard({
  label, value, accent, icon, valueColor = NEUTRAL, sub, title,
}: StatCardProps) {
  return (
    <div className="stat-card"
         style={{ ["--stat-accent" as string]: accent }}
         title={title}>
      <div className="stat-head">
        <div className="stat-label">{label}</div>
        {icon && <span className="stat-icon" aria-hidden>{icon}</span>}
      </div>
      <div className="stat-value" style={{ color: valueColor }}>{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  )
}
