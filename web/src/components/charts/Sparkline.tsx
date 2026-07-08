// Port of ui/components/metrics.py's _sparkline_svg — same downsample-to-40,
// min/max-normalize, filled-area + stroke approach. A charting library is
// overkill for a 150x34px trend line; this stays a plain SVG component so
// it's pixel-identical in spirit to the Python version it replaces.

interface SparklineProps {
  values: number[]
  color: string
  width?: number
  height?: number
  filled?: boolean
}

export function Sparkline({ values, color, width = 150, height = 34, filled = true }: SparklineProps) {
  const clean = values.filter((v) => Number.isFinite(v))
  if (clean.length < 2) return null

  let vals = clean
  if (vals.length > 40) {
    const step = Math.floor(vals.length / 40)
    vals = vals.filter((_, i) => i % step === 0)
  }

  const vmin = Math.min(...vals)
  const vmax = Math.max(...vals)
  const rng = vmax - vmin || 1

  const points = vals
    .map((v, i) => {
      const x = (i / (vals.length - 1)) * width
      const y = height - ((v - vmin) / rng) * height
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(" ")

  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      {filled && (
        <polyline
          points={`0,${height} ${points} ${width},${height}`}
          fill={color}
          fillOpacity={0.16}
          stroke="none"
        />
      )}
      <polyline points={points} fill="none" stroke={color} strokeWidth={2}
                strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
