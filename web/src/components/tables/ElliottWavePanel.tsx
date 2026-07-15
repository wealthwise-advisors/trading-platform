import type { ElliottWaveResponse, WaveAnalysis, OHLCVRecord } from "@/lib/types"
import { GOOD, CRITICAL, CYAN, ACCENTS } from "@/components/cards/StatCard"
import { ElliottWaveChart } from "@/components/charts/ElliottWaveChart"

// Bias/invalidation are now shown directly on the chart itself (see
// ElliottWaveChart's bias box + invalidation line), so this card only
// carries the supplementary info the chart doesn't already show: fib fit,
// confluence target zones, notes, and alternate counts.
function DegreeSummary({ a }: { a: WaveAnalysis }) {
  return (
    <div className="rounded-lg border border-white/6 p-3 space-y-2 text-xs"
         style={{ background: "color-mix(in srgb, #8b5cf6 5%, transparent)" }}>
      {a.impulse && (
        <div className="flex items-center gap-2">
          <span className="font-medium">Impulse ({a.impulse.direction})</span>
          <span className="px-1.5 py-0.5 rounded"
                style={{ background: a.impulse.valid ? "color-mix(in srgb, #22C55E 20%, transparent)" : "color-mix(in srgb, #EF4444 20%, transparent)",
                         color: a.impulse.valid ? GOOD : CRITICAL }}>
            {a.impulse.valid ? "valid" : "invalid"}
          </span>
          {a.impulse_fib && (
            <span className="text-muted-foreground">fib fit: {((a.impulse_fib.fib_fit ?? 0) * 100).toFixed(0)}%</span>
          )}
          {a.impulse.truncated_fifth && <span style={{ color: "#e0a72e" }}>truncated 5th</span>}
        </div>
      )}

      {a.correction && (
        <div className="flex items-center gap-2">
          <span className="font-medium">Correction: {a.correction.type.replace(/_/g, " ")} ({a.correction.direction})</span>
          {a.correction_fib?.fib_fit != null && (
            <span className="text-muted-foreground">fib fit: {(a.correction_fib.fib_fit * 100).toFixed(0)}%</span>
          )}
        </div>
      )}

      {a.target_zones.length > 0 && (
        <div className="border-t border-white/6 pt-2">
          <div className="font-medium mb-1">Confluence target zones</div>
          <div className="flex flex-wrap gap-1.5">
            {a.target_zones.slice(0, 6).map((z, i) => (
              <span key={i} className="px-2 py-1 rounded"
                    style={{ background: `color-mix(in srgb, ${CYAN} ${Math.min(12 + z.strength * 8, 40)}%, transparent)` }}
                    title={z.members.map((m) => `${m.source}: ${m.price.toFixed(2)}`).join(", ")}>
                {z.center.toFixed(2)} <span className="text-muted-foreground">(×{z.strength})</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {a.notes.length > 0 && (
        <div className="border-t border-white/6 pt-2 space-y-1">
          {a.notes.map((n, i) => <div key={i} className="text-muted-foreground">💡 {n}</div>)}
        </div>
      )}

      {a.alternates.length > 0 && (
        <div className="space-y-1">
          {a.alternates.map((alt, i) => (
            <div key={i} style={{ color: ACCENTS[1] }}>⚠ {alt}</div>
          ))}
        </div>
      )}
    </div>
  )
}

interface ElliottWavePanelProps {
  data: ElliottWaveResponse
  bars: OHLCVRecord[]
  symbol: string
}

export function ElliottWavePanel({ data, bars, symbol }: ElliottWavePanelProps) {
  const degrees = Object.values(data)
  if (!degrees.length) {
    return <p className="text-muted-foreground p-4">No wave structure detected in this backtest's price data.</p>
  }

  return (
    <div className="space-y-4">
      {degrees.map((a, i) => (
        <div key={i} className="space-y-2">
          <ElliottWaveChart symbol={symbol} bars={bars} analysis={a} nested={a.degree === "minor"} />
          <DegreeSummary a={a} />
        </div>
      ))}
    </div>
  )
}
