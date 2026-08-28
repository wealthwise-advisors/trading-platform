import type { ChartPatternRecord } from "@/lib/types"
import { Badge } from "@/components/ui/badge"
import { GOOD, CRITICAL, NEUTRAL } from "@/components/cards/StatCard"

const PATTERN_LABELS: Record<string, string> = {
  double_top: "Double Top",
  double_bottom: "Double Bottom",
  head_and_shoulders: "Head & Shoulders",
  inverse_head_and_shoulders: "Inverse Head & Shoulders",
  triangle: "Triangle",
}

function directionColor(direction: string) {
  if (direction === "bullish") return GOOD
  if (direction === "bearish") return CRITICAL
  return NEUTRAL
}

export function ChartPatternsTable({ patterns }: { patterns: ChartPatternRecord[] }) {
  if (!patterns.length) {
    return <p className="text-muted-foreground p-4">No chart patterns detected in this period.</p>
  }

  return (
    <div>
      <div className="overflow-x-auto rounded-lg border border-white/6 max-h-[480px] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#1a1c24] text-muted-foreground sticky top-0">
            <tr>
              <th className="text-left p-2 font-medium">Pattern</th>
              <th className="text-left p-2 font-medium">Direction</th>
              <th className="text-left p-2 font-medium">Start</th>
              <th className="text-left p-2 font-medium">End</th>
              <th className="text-right p-2 font-medium">Neckline</th>
              <th className="text-left p-2 font-medium">Metrics</th>
            </tr>
          </thead>
          <tbody>
            {patterns.map((p, i) => (
              <tr key={i} className="border-t border-white/6">
                <td className="p-2">{PATTERN_LABELS[p.pattern] ?? p.pattern}</td>
                <td className="p-2">
                  <Badge style={{ background: `color-mix(in srgb, ${directionColor(p.direction)} 25%, transparent)`, color: directionColor(p.direction) }}>
                    {p.direction}
                  </Badge>
                </td>
                <td className="p-2">{p.start.replace("T", " ").slice(0, 16)}</td>
                <td className="p-2">{p.end.replace("T", " ").slice(0, 16)}</td>
                <td className="p-2 text-right">{p.neckline.toFixed(2)}</td>
                <td className="p-2 text-xs text-muted-foreground">
                  {Object.entries(p.metrics).map(([k, v]) => `${k}: ${typeof v === "number" ? v.toFixed(2) : v}`).join(" · ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground mt-2 px-1">
        Detected via swing-pivot geometry (rule-based, no ML) — chart patterns fire frequently on
        noisy intraday data; treat as candidates to review on the price chart, not standalone signals.
      </p>
    </div>
  )
}
