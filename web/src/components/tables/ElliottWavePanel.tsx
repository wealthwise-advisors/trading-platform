import type { ElliottWaveResponse, OHLCVRecord } from "@/lib/types"
import { ElliottWaveChart, groupRuns, labelSegments, splitIntoSegments } from "@/components/charts/ElliottWaveChart"
import { WaveNotesCard } from "@/components/tables/WaveNotesPanel"

interface ElliottWavePanelProps {
  data: ElliottWaveResponse
  bars: OHLCVRecord[]
  symbol: string
}

const GLOBAL_SUFFIX = "_global"
const DEFAULT_DESCRIPTION = "Shows the highest-level Elliott Wave structures detected for this timeframe."

// Every degree in the response renders as its OWN independent chart card
// (2026-07-20: reverted from the earlier single-merged-chart design per
// explicit user request -- no overlaying two readings on one Plotly chart
// anymore). Purely name-based, not hardcoded to "minor": a degree ending in
// "_global" is labeled "Global"; a degree with a "_global" sibling
// elsewhere in the response (e.g. "minor", when "minor_global" is also
// present) is labeled "Nested". A degree with neither relationship (e.g.
// "primary") gets no variant label, but still gets the default description
// below (every chart gets a purpose line, per explicit user request).
function variantLabelFor(name: string, data: ElliottWaveResponse): "Global" | "Nested" | undefined {
  if (name.endsWith(GLOBAL_SUFFIX)) return "Global"
  if (data[`${name}${GLOBAL_SUFFIX}`]) return "Nested"
  return undefined
}

// 2026-07-21: wording updated to explicit user-provided examples, still
// substituting the REAL degree name (not hardcoded to "Minor") so a future
// "major"/"major_global" pair reads "Shows higher-level Major structures...".
function descriptionFor(name: string, variant: "Global" | "Nested" | undefined): string {
  const baseDegree = name.replace(/_global$/, "")
  const degreeLabel = `${baseDegree.charAt(0).toUpperCase()}${baseDegree.slice(1)}`
  if (variant === "Global") return `Shows higher-level ${degreeLabel} structures across the entire chart.`
  if (variant === "Nested") return `Shows smaller ${degreeLabel} structures detected inside the larger trend.`
  return DEFAULT_DESCRIPTION
}

export function ElliottWavePanel({ data, bars, symbol }: ElliottWavePanelProps) {
  const entries = Object.entries(data)
  if (!entries.length) {
    return <p className="text-muted-foreground p-4">No wave structure detected in this backtest's price data.</p>
  }

  return (
    <div className="space-y-4">
      {entries.map(([name, analysis]) => {
        const variant = variantLabelFor(name, data)
        const description = descriptionFor(name, variant)
        // Same labeling ElliottWaveChart.tsx uses for its own on-chart
        // headers (labelSegments is the shared single source of truth) --
        // solo/separate-cards mode always uses 1-indexed "Wave N", matching
        // what ElliottWaveChart.tsx renders for this same analysis. Each
        // label's `.display` already includes the point range or letter
        // span, e.g. "Wave 1 (1-5)" or "ABC Correction (A–C)" -- exactly
        // what's shown on the chart itself.
        const segments = groupRuns(analysis.wave_sequence).flatMap(splitIntoSegments)
        const detected = labelSegments(segments, false)
        return (
          <div key={name} className="space-y-1">
            <ElliottWaveChart symbol={symbol} bars={bars} analysis={analysis} variantLabel={variant} />
            <p className="px-1 text-xs text-muted-foreground">{description}</p>
            {detected.length > 0 && (
              <p className="px-1 text-xs text-muted-foreground">
                <span className="font-medium">Detected:</span> {detected.map((l) => l.display).join(", ")}
              </p>
            )}
            <WaveNotesCard notes={analysis.notes} />
          </div>
        )
      })}
    </div>
  )
}
