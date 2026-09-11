// @vitest-environment jsdom
//
// The app ships `plotly-finance`, not the full plotly bundle, to keep a
// compiled-in copy of maplibre-gl (GHSA-jrc7-96c5-q579, critical) out of what
// users download. The cost of that choice is that trace types outside the
// bundle fail at run time, on the chart, with nothing failing at build time.
// These tests are the build-time failure that would otherwise not exist.
import { describe, it, expect } from "vitest"
import Plotly from "plotly.js/dist/plotly-finance"

const USED = ["candlestick", "scatter", "bar"] as const

describe("the Plotly bundle the app ships", () => {
  it("registers every trace type the charts draw", () => {
    const schema = (Plotly as unknown as { PlotSchema: { get(): { traces: Record<string, unknown> } } })
      .PlotSchema.get()
    for (const t of USED) expect(Object.keys(schema.traces)).toContain(t)
  })

  it("carries no map traces, which is what drags maplibre-gl in", () => {
    const schema = (Plotly as unknown as { PlotSchema: { get(): { traces: Record<string, unknown> } } })
      .PlotSchema.get()
    const traces = Object.keys(schema.traces)
    for (const t of ["scattermap", "choroplethmap", "scattermapbox", "densitymapbox"]) {
      expect(traces).not.toContain(t)
    }
  })

  it("keeps the layout features the charts depend on", () => {
    const schema = (Plotly as unknown as {
      PlotSchema: { get(): { layout: { layoutAttributes: Record<string, unknown> } } }
    }).PlotSchema.get()
    for (const k of ["annotations", "shapes", "xaxis"]) {
      expect(Object.keys(schema.layout.layoutAttributes)).toContain(k)
    }
  })
})
