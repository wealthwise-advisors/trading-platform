import { ACCENTS } from "@/components/cards/StatCard"
import { RefreshCw } from "lucide-react"

interface WinLossDonutProps {
  wins: number
  losses: number
  winRate: number
}

// Same .stat-card markup as the other 4 KPI cards (was a separate shadcn
// Card with its own styling before -- looked visually different from the
// rest of the row). ACCENTS[4] is unused by the other cards (0-3), so this
// stays visually distinct without clashing with any of them.
export function WinLossDonut({ wins, losses, winRate }: WinLossDonutProps) {
  const total = wins + losses
  const lossRate = total > 0 ? 100 - winRate : 0
  return (
    <div className="stat-card" style={{ ["--stat-accent" as string]: ACCENTS[4] }}>
      <span className="float-right -mt-0.5 -mr-0.5 w-4.5 h-4.5 rounded-full flex items-center justify-center text-[0.65rem]"
            style={{
              background: `color-mix(in srgb, ${ACCENTS[4]} 22%, transparent)`,
              boxShadow: `0 0 0 1px color-mix(in srgb, ${ACCENTS[4]} 45%, transparent)`,
            }}>
        <RefreshCw className="h-3.5 w-3.5 shrink-0" aria-hidden />
      </span>
      <div className="stat-label">Win % / Loss %</div>
      <div className="stat-value">{winRate.toFixed(0)}% / {lossRate.toFixed(0)}%</div>
    </div>
  )
}
