import type { ElliottWaveResponse, OHLCVRecord } from "@/lib/types"
import { GOOD, CRITICAL } from "@/components/cards/StatCard"
import { WavePivotChart } from "@/components/charts/WavePivotChart"

const LABEL_COLOR: Record<string, string> = {
  HH: GOOD, HL: "#14E0D4", LH: "#e0a72e", LL: CRITICAL,
}

interface SwingsPanelProps {
  data: ElliottWaveResponse
  bars: OHLCVRecord[]
  symbol: string
}

export function SwingsPanel({ data, bars, symbol }: SwingsPanelProps) {
  const degrees = Object.values(data)
  if (!degrees.length) {
    return <p className="text-muted-foreground p-4">No swings detected in this backtest's price data.</p>
  }

  return (
    <div className="space-y-3">
      {degrees.map((a, i) => (
        <div key={i} className="rounded-lg border border-white/6 p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-sm capitalize">{a.degree} degree</span>
            <span className="text-xs text-muted-foreground">{a.swings.length} pivots · trend: {a.trend}</span>
          </div>
          <WavePivotChart
            symbol={symbol} bars={bars}
            pivots={a.swings.map((s) => ({ t: s.t, price: s.price, label: s.label ?? "", kind: s.kind }))}
            lineColor="#8b93b8" seriesName="Swings" title={`${a.degree} degree swings`}
          />
          <div className="overflow-x-auto max-h-60 overflow-y-auto rounded-lg border border-white/6">
            <table className="w-full text-xs">
              <thead className="bg-[#0e1424] text-muted-foreground sticky top-0">
                <tr>
                  <th className="text-left p-2 font-medium">Time</th>
                  <th className="text-left p-2 font-medium">Kind</th>
                  <th className="text-right p-2 font-medium">Price</th>
                  <th className="text-left p-2 font-medium">Structure</th>
                </tr>
              </thead>
              <tbody>
                {a.swings.map((s, j) => (
                  <tr key={j} className="border-t border-white/6">
                    <td className="p-2">{s.t.replace("T", " ").slice(0, 16)}</td>
                    <td className={`p-2 ${s.kind === "high" ? "text-red-400" : "text-green-400"}`}>{s.kind}</td>
                    <td className="p-2 text-right font-mono">{s.price.toFixed(2)}</td>
                    <td className="p-2">
                      {s.label && (
                        <span className="px-1.5 py-0.5 rounded font-semibold"
                              style={{ background: `color-mix(in srgb, ${LABEL_COLOR[s.label] ?? "#8b93b8"} 20%, transparent)`,
                                       color: LABEL_COLOR[s.label] ?? "#8b93b8" }}>
                          {s.label}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  )
}
