import type { ElliottWaveResponse, OHLCVRecord } from "@/lib/types"
import { ElliottWaveChart } from "@/components/charts/ElliottWaveChart"

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
        <ElliottWaveChart key={i} symbol={symbol} bars={bars} analysis={a} nested={a.degree === "minor"} />
      ))}
    </div>
  )
}
