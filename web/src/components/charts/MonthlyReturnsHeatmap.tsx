import type { MonthlyReturns } from "@/lib/types"
import { GOOD, CRITICAL } from "@/components/cards/StatCard"

// Diverging: two hues (green/red) + neutral gray midpoint at 0, intensity by
// magnitude — same rule as the dataviz skill's color-formula for polarity data.
const NEUTRAL_CELL = "#1a2340"
const MAX_MAGNITUDE = 8 // % return at which a cell reaches full saturation

function cellColor(val: number | null): string {
  if (val === null) return NEUTRAL_CELL
  const t = Math.min(Math.abs(val) / MAX_MAGNITUDE, 1)
  const hue = val >= 0 ? GOOD : CRITICAL
  return `color-mix(in srgb, ${hue} ${Math.round(t * 85)}%, ${NEUTRAL_CELL})`
}

export function MonthlyReturnsHeatmap({ data }: { data: MonthlyReturns }) {
  if (!data.years.length) {
    return <p className="text-muted-foreground p-4">Not enough data to compute monthly returns.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="border-separate" style={{ borderSpacing: "3px" }}>
        <thead>
          <tr>
            <th className="text-xs text-muted-foreground text-left pr-2 pb-1 font-medium">Year</th>
            {data.months.map((m) => (
              <th key={m} className="text-xs text-muted-foreground font-medium pb-1 min-w-[56px]">{m}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.years.map((year, yi) => (
            <tr key={year}>
              <td className="text-sm text-muted-foreground pr-2 font-medium">{year}</td>
              {data.values[yi].map((val, mi) => (
                <td key={mi}
                    className="rounded-md text-center text-xs font-semibold py-3"
                    style={{ background: cellColor(val), color: val === null ? "var(--muted-foreground)" : "#fff" }}
                    title={val !== null ? `${year} ${data.months[mi]}: ${val >= 0 ? "+" : ""}${val.toFixed(1)}%` : "No data"}>
                  {val !== null ? `${val >= 0 ? "+" : ""}${val.toFixed(1)}%` : "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm" style={{ background: CRITICAL }} /> Loss month
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm" style={{ background: NEUTRAL_CELL }} /> No data
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm" style={{ background: GOOD }} /> Gain month
        </span>
      </div>
    </div>
  )
}
