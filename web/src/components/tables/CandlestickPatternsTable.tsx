import { useState } from "react"
import type { CandlestickPatternRecord } from "@/lib/types"
import { Slider } from "@/components/ui/slider"
import { Badge } from "@/components/ui/badge"
import { GOOD, CRITICAL, NEUTRAL } from "@/components/cards/StatCard"

const PATTERN_LABELS: Record<string, string> = {
  doji: "Doji",
  hammer: "Hammer",
  bullish_engulfing: "Bullish Engulfing",
  bearish_engulfing: "Bearish Engulfing",
  morning_star: "Morning Star",
  evening_star: "Evening Star",
}

function directionColor(direction: string) {
  if (direction === "bullish") return GOOD
  if (direction === "bearish") return CRITICAL
  return NEUTRAL
}

export function CandlestickPatternsTable({ patterns }: { patterns: CandlestickPatternRecord[] }) {
  const [minConfidence, setMinConfidence] = useState(70)
  const filtered = patterns
    .filter((p) => p.confidence >= minConfidence)
    .slice()
    .sort((a, b) => b.confidence - a.confidence)

  return (
    <div>
      <div className="flex items-center gap-3 mb-3 px-1">
        <span className="text-xs text-muted-foreground whitespace-nowrap">Min confidence: {minConfidence}%</span>
        <Slider className="max-w-xs" min={0} max={100} step={5}
                value={[minConfidence]} onValueChange={(v) => setMinConfidence(v[0])} />
        <span className="text-xs text-muted-foreground whitespace-nowrap">{filtered.length} of {patterns.length} bars</span>
      </div>

      {!filtered.length ? (
        <p className="text-muted-foreground p-4">No candlestick patterns at this confidence threshold.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-white/6 max-h-[480px] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#0e1424] text-muted-foreground sticky top-0">
              <tr>
                <th className="text-left p-2 font-medium">Time</th>
                <th className="text-left p-2 font-medium">Pattern</th>
                <th className="text-left p-2 font-medium">Direction</th>
                <th className="text-right p-2 font-medium">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p, i) => (
                <tr key={i} className="border-t border-white/6">
                  <td className="p-2">{p.timestamp.replace("T", " ").slice(0, 16)}</td>
                  <td className="p-2">{PATTERN_LABELS[p.pattern] ?? p.pattern}</td>
                  <td className="p-2">
                    <Badge style={{ background: `color-mix(in srgb, ${directionColor(p.direction)} 25%, transparent)`, color: directionColor(p.direction) }}>
                      {p.direction}
                    </Badge>
                  </td>
                  <td className="p-2 text-right">{p.confidence.toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-xs text-muted-foreground mt-2 px-1">
        Detected via rule-based candle geometry (body/wick ratios) — high frequency on noisy data is expected;
        use the confidence slider to focus on the clearer signals.
      </p>
    </div>
  )
}
