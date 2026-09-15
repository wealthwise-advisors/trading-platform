// Session-anchored Volume Profile geometry (time per profile = DAY / WEEK).
//
// Each profile is drawn inside its own session's x-range as filled rects,
// rather than on the right-hand overlay. Rects are used instead of bar traces
// because a horizontal bar on a date axis has no natural way to express
// "extend N milliseconds from this timestamp" per profile.
//
// Extracted from the chart component so the x-boundary handling is testable:
// these shapes are positioned with xref "x", so serializing a boundary as UTC
// would slide the whole per-session profile off the axis by the browser's UTC
// offset -- the same defect that made the candlestick trace disappear. See
// lib/isoTime.ts.

import type { Shape } from "plotly.js"
import type { ProfileSlice } from "@/lib/volumeProfile"
import { formatterFor } from "@/lib/isoTime"
import type { PlotStyles } from "@/lib/vpPlotStyles"

export interface ProfileLevelToggles {
  poc: boolean
  vah: boolean
  val: boolean
  profileHigh: boolean
  profileLow: boolean
}

export function buildSessionProfileShapes(
  slices: ProfileSlice[],
  opacityPct: number,
  show: ProfileLevelToggles,
  /** Per-plot colour, style and width from the study dialog. Omitted, the
   *  levels keep the colours they have always had. Draw as does not apply:
   *  these are shapes, which only draw as lines. */
  styles?: PlotStyles,
): Partial<Shape>[] {
  if (!slices.length) return []
  const out: Partial<Shape>[] = []
  const a = opacityPct / 100
  const fmtX = formatterFor(slices[0].startT)

  for (const slice of slices) {
    const { profile: p, startT, endT } = slice
    const x0 = Date.parse(startT)
    const span = Math.max(Date.parse(endT) - x0, 60_000)
    const maxVol = Math.max(...p.volumes, 1)
    const half = (p.binSize ?? 0) / 2
    const inVA = (price: number) =>
      p.val != null && p.vah != null && price >= p.val && price <= p.vah

    p.prices.forEach((price, i) => {
      const frac = p.volumes[i] / maxVol
      if (frac <= 0) return
      out.push({
        type: "rect", xref: "x", yref: "y", layer: "below",
        x0: fmtX(x0),
        x1: fmtX(x0 + span * frac * 0.9),
        y0: price - half, y1: price + half,
        fillcolor: inVA(price)
          ? `rgba(56,189,248,${(a * 0.68).toFixed(3)})`
          : `rgba(56,189,248,${(a * 0.26).toFixed(3)})`,
        line: { width: 0 },
      } as Partial<Shape>)
    })

    // Per-profile levels, each spanning only its own session.
    const levels: [keyof ProfileLevelToggles, number | null, string, string][] = [
      ["poc", p.poc, "#38bdf8", "solid"],
      ["vah", p.vah, "#7dd3fc", "dash"],
      ["val", p.val, "#7dd3fc", "dash"],
      ["profileHigh", p.prices.length ? p.prices[p.prices.length - 1] + half : null, "#94a3b8", "dot"],
      ["profileLow", p.prices.length ? p.prices[0] - half : null, "#94a3b8", "dot"],
    ]
    for (const [key, value, color, dash] of levels) {
      if (!show[key] || value == null) continue
      const st = styles?.[key]
      out.push({
        type: "line", xref: "x", yref: "y",
        x0: fmtX(x0), x1: fmtX(x0 + span),
        y0: value, y1: value,
        // Width 1 keeps the thinner 1.1px these session levels have always used.
        line: {
          color: st ? st.color : color,
          width: st && st.width > 1 ? st.width : 1.1,
          dash: st ? st.style : dash,
        },
      } as Partial<Shape>)
    }
  }
  return out
}
