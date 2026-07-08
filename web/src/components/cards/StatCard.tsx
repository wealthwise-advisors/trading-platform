import { Sparkline } from "@/components/charts/Sparkline"

// Fixed categorical order — card N always gets slot N, regardless of value.
// Hue identity kept from the dataviz-skill validated set; lightness/chroma
// bumped for the "premium trading platform" redesign pass (blue/purple/
// orange/green, same order, more neon).
export const ACCENTS = ["#4f8ef7", "#9d7bf0", "#ff7a45", "#22d97e", "#e0a72e", "#f0699a"]
export const GOOD = "#22d97e"
export const CRITICAL = "#e0455a"
export const NEUTRAL = "#e2e8ff"
export const CYAN = "#37e0e0"

interface StatCardProps {
  label: string
  value: string
  accent: string
  icon?: string
  valueColor?: string
  sub?: string
  sparklineValues?: number[]
  sparklineColor?: string
}

export function StatCard({
  label, value, accent, icon, valueColor = NEUTRAL, sub, sparklineValues, sparklineColor,
}: StatCardProps) {
  return (
    <div className="stat-card" style={{ ["--stat-accent" as string]: accent }}>
      {icon && (
        <span className="float-right -mt-0.5 -mr-0.5 w-8 h-8 rounded-full flex items-center justify-center text-base"
              style={{
                background: `color-mix(in srgb, ${accent} 22%, transparent)`,
                boxShadow: `0 0 0 1px color-mix(in srgb, ${accent} 45%, transparent)`,
              }}>
          {icon}
        </span>
      )}
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={{ color: valueColor }}>{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
      {sparklineValues && sparklineValues.length > 1 && (
        <div className="mt-1.5">
          <Sparkline values={sparklineValues} color={sparklineColor ?? accent} />
        </div>
      )}
    </div>
  )
}
