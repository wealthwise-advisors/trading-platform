// Fixed categorical order — card N always gets slot N, regardless of value.
// Exact hex values pinned to the reference palette (blue/purple/orange/green).
// ACCENTS[2] (Max Drawdown's card border) is the palette's orange; CRITICAL
// stays a true red since it's the general "loss/negative" status color used
// everywhere else (trade tables, P&L bars, exit markers).
export const ACCENTS = ["#2F80FF", "#8B5CF6", "#F97316", "#22C55E", "#e0a72e", "#f0699a"]
export const GOOD = "#22C55E"
export const CRITICAL = "#EF4444"
export const NEUTRAL = "#e2e8ff"
export const CYAN = "#14E0D4"

interface StatCardProps {
  label: string
  value: string
  accent: string
  icon?: string
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
