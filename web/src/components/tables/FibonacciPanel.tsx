import type { ElliottWaveResponse, WaveFibDetail, OHLCVRecord } from "@/lib/types"
import { FibonacciZonesChart } from "@/components/charts/FibonacciZonesChart"

function FibDetailTable({ title, fib }: { title: string; fib: WaveFibDetail }) {
  const entries = Object.entries(fib.detail)
  if (!entries.length) return null
  return (
    <div className="text-xs">
      <div className="flex items-center justify-between mb-1">
        <span className="font-medium">{title}</span>
        {fib.fib_fit != null && <span className="text-muted-foreground">overall fit: {(fib.fib_fit * 100).toFixed(0)}%</span>}
      </div>
      <div className="overflow-x-auto rounded-lg border border-white/6">
        <table className="w-full text-xs">
          <thead className="bg-[#0e1424] text-muted-foreground">
            <tr>
              <th className="text-left p-2 font-medium">Ratio</th>
              <th className="text-right p-2 font-medium">Achieved</th>
              <th className="text-right p-2 font-medium">Nearest Ideal</th>
              <th className="text-right p-2 font-medium">Distance</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([key, v]) => (
              <tr key={key} className="border-t border-white/6">
                <td className="p-2 text-muted-foreground">{key.replace(/_/g, " ")}</td>
                <td className="p-2 text-right font-mono">{v.achieved}</td>
                <td className="p-2 text-right font-mono">{v.nearest_ideal}</td>
                <td className="p-2 text-right font-mono">{v.dist}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

interface FibonacciPanelProps {
  data: ElliottWaveResponse
  bars: OHLCVRecord[]
  symbol: string
}

export function FibonacciPanel({ data, bars, symbol }: FibonacciPanelProps) {
  const degrees = Object.values(data)

  return (
    <div className="space-y-3">
      {degrees.map((a, i) => (
        <div key={i} className="rounded-lg border border-white/6 p-3 space-y-2">
          <div className="font-semibold text-sm capitalize">{a.degree} degree</div>

          {a.target_zones.length > 0 ? (
            <FibonacciZonesChart symbol={symbol} bars={bars} zones={a.target_zones} />
          ) : (
            <p className="text-xs text-muted-foreground">No confluence zones formed yet at this degree.</p>
          )}

          {a.impulse_fib && <FibDetailTable title="Impulse wave proportions" fib={a.impulse_fib} />}
          {a.correction_fib && <FibDetailTable title="Correction wave proportions" fib={a.correction_fib} />}

          {!a.impulse_fib && !a.correction_fib && a.target_zones.length === 0 && (
            <p className="text-xs text-muted-foreground">No Fibonacci data yet — needs a validated impulse or correction first.</p>
          )}
        </div>
      ))}
    </div>
  )
}
