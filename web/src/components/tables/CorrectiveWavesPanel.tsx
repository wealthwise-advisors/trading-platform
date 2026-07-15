import type { ElliottWaveResponse, OHLCVRecord } from "@/lib/types"
import { WavePivotChart } from "@/components/charts/WavePivotChart"

// Index 0 is the correction's own starting point (the impulse's own last
// pivot, not a leg of the correction itself) -- left unlabeled so the
// first labeled point is "A", matching the other wave charts' convention
// of skipping the origin.
//
// Open-ended letter generator (A, B, C... Z, AA, AB...) -- a fixed-length
// array here used to fall back to a bare number ("6") past its last entry,
// which broke the letter sequence for corrections with more than 5 legs.
function pivotLetter(n: number): string {
  let x = n, out = ""
  while (x > 0) {
    const rem = (x - 1) % 26
    out = String.fromCharCode(65 + rem) + out
    x = Math.floor((x - 1) / 26)
  }
  return out
}

const METRIC_LABELS: Record<string, string> = {
  b_retrace_of_A: "B retraces A by",
  c_beyond_A: "C extends past A by",
  x_retrace_of_W: "X connector retraces W by",
}

interface CorrectiveWavesPanelProps {
  data: ElliottWaveResponse
  bars: OHLCVRecord[]
  symbol: string
}

export function CorrectiveWavesPanel({ data, bars, symbol }: CorrectiveWavesPanelProps) {
  const degrees = Object.values(data)
  const anyCorrection = degrees.some((a) => a.correction)

  return (
    <div className="space-y-3">
      {!anyCorrection && (
        <p className="text-muted-foreground p-4">No correction detected yet following the impulse in this backtest's price data.</p>
      )}
      {degrees.filter((a) => a.correction).map((a, i) => {
        const c = a.correction!
        return (
          <div key={i} className="rounded-lg border border-white/6 p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-sm capitalize">{a.degree} degree</span>
              <span className="text-xs px-2 py-0.5 rounded-full font-semibold"
                    style={{ background: "color-mix(in srgb, #8B5CF6 20%, transparent)", color: "#c4b5fd" }}>
                {c.type.replace(/_/g, " ")} ({c.direction})
              </span>
            </div>

            <WavePivotChart
              symbol={symbol} bars={bars}
              pivots={c.pivots.map((p, j) => ({ t: p.t, price: p.price, label: j === 0 ? "" : pivotLetter(j) }))}
              lineColor="#f0c040" seriesName={`Correction (${c.type.replace(/_/g, " ")})`}
              title={`${a.degree} degree correction — ${c.type.replace(/_/g, " ")}`}
              dash
            />

            {Object.keys(c.metrics).length > 0 && (
              <div className="text-xs space-y-1">
                {Object.entries(c.metrics).map(([key, val]) => (
                  <div key={key} className="flex items-center justify-between">
                    <span className="text-muted-foreground">{METRIC_LABELS[key] ?? key}</span>
                    <span className="font-semibold">{typeof val === "number" ? `${(val * 100).toFixed(0)}%` : String(val)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
