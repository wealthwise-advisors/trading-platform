import type { ElliottWaveResponse, OHLCVRecord } from "@/lib/types"
import { GOOD, CRITICAL } from "@/components/cards/StatCard"
import { WavePivotChart } from "@/components/charts/WavePivotChart"

const WAVE_LABELS = ["0", "1", "2", "3", "4", "5"]

const RULE_LABELS: Record<string, string> = {
  alternation: "Pivots alternate high/low correctly",
  w2_holds_origin: "Wave 2 never retraces beyond Wave 1's origin",
  w3_exceeds_w1: "Wave 3 extends beyond Wave 1's end",
  w3_not_shortest: "Wave 3 is not the shortest of 1, 3, 5",
  w4_no_overlap_w1: "Wave 4 doesn't enter Wave 1's price territory",
}

interface ImpulseWavesPanelProps {
  data: ElliottWaveResponse
  bars: OHLCVRecord[]
  symbol: string
}

export function ImpulseWavesPanel({ data, bars, symbol }: ImpulseWavesPanelProps) {
  const degrees = Object.values(data)
  const anyImpulse = degrees.some((a) => a.impulse)

  return (
    <div className="space-y-3">
      {!anyImpulse && (
        <p className="text-muted-foreground p-4">No structurally valid impulse wave found in this backtest's price data.</p>
      )}
      {degrees.filter((a) => a.impulse).map((a, i) => {
        const w = a.impulse!
        return (
          <div key={i} className="rounded-lg border border-white/6 p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-sm capitalize">{a.degree} degree — {w.direction}-impulse</span>
              <span className="text-xs px-2 py-0.5 rounded-full font-semibold"
                    style={{ background: w.valid ? "color-mix(in srgb, #22C55E 20%, transparent)" : "color-mix(in srgb, #EF4444 20%, transparent)",
                             color: w.valid ? GOOD : CRITICAL }}>
                {w.valid ? "VALID" : "INVALID"}
              </span>
            </div>

            <WavePivotChart
              symbol={symbol} bars={bars}
              pivots={w.pivots.map((p, j) => ({ t: p.t, price: p.price, label: WAVE_LABELS[j] ?? String(j) }))}
              lineColor={w.valid ? GOOD : CRITICAL} seriesName={`Impulse (${w.direction})`}
              title={`${a.degree} degree impulse (${w.valid ? "valid" : "invalid"})`}
            />

            <div className="text-xs space-y-1">
              {Object.entries(w.rules).map(([key, passed]) => (
                <div key={key} className="flex items-center gap-2">
                  <span style={{ color: passed ? GOOD : CRITICAL }}>{passed ? "✓" : "✗"}</span>
                  <span className="text-muted-foreground">{RULE_LABELS[key] ?? key}</span>
                </div>
              ))}
              {w.truncated_fifth && (
                <div className="flex items-center gap-2" style={{ color: "#e0a72e" }}>
                  <span>⚠</span><span>Wave 5 failed to exceed Wave 3 (truncated fifth)</span>
                </div>
              )}
            </div>

            <div className="text-xs">
              <span className="text-muted-foreground">Fibonacci fit: </span>
              <span className="font-semibold">{(w.fib_score * 100).toFixed(0)}%</span>
              <span className="text-muted-foreground"> (soft guideline score, not a rule)</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
