// The session-anchored Volume Profile rects and level lines are positioned
// with xref "x", so they carry the same timestamp-convention hazard as the
// candlestick trace: a UTC-serialized boundary slides the whole per-session
// profile off the axis by the browser's UTC offset.
//
// Latent in practice because these shapes only draw when time-per-profile is
// DAY or WEEK; the default CHART mode uses the right-hand bar overlay.

import { describe, it, expect } from "vitest"
import { buildSessionProfileShapes } from "@/lib/volumeProfileShapes"
import type { ProfileSlice } from "@/lib/volumeProfile"
import { toNaiveString } from "@/lib/isoTime"

const ALL_ON = { poc: true, vah: true, val: true, profileHigh: true, profileLow: true }
const ALL_OFF = { poc: false, vah: false, val: false, profileHigh: false, profileLow: false }

function slice(startT: string, endT: string): ProfileSlice {
  return {
    startT,
    endT,
    profile: {
      prices: [4500, 4510, 4520],
      volumes: [10, 40, 20],
      poc: 4510, val: 4500, vah: 4520, binSize: 10,
    },
  }
}

const naiveSlices = () => [
  slice("2026-08-10T09:30:00", "2026-08-10T16:00:00"),
  slice("2026-08-11T09:30:00", "2026-08-11T16:00:00"),
]

/** Every x coordinate present on the returned shapes. */
function xs(shapes: ReturnType<typeof buildSessionProfileShapes>): string[] {
  return shapes.flatMap((s) => [s.x0, s.x1].filter((v): v is string => typeof v === "string"))
}

describe("buildSessionProfileShapes", () => {
  it("returns nothing without slices", () => {
    expect(buildSessionProfileShapes([], 50, ALL_ON)).toEqual([])
  })

  it("emits a rect per non-empty bin plus the enabled levels", () => {
    const shapes = buildSessionProfileShapes([slice("2026-08-10T09:30:00",
      "2026-08-10T16:00:00")], 50, ALL_ON)
    expect(shapes.filter((s) => s.type === "rect")).toHaveLength(3)
    expect(shapes.filter((s) => s.type === "line")).toHaveLength(5)
  })

  it("omits level lines that are toggled off", () => {
    const shapes = buildSessionProfileShapes([slice("2026-08-10T09:30:00",
      "2026-08-10T16:00:00")], 50, ALL_OFF)
    expect(shapes.filter((s) => s.type === "line")).toHaveLength(0)
  })

  it("THE BUG: naive slice boundaries produce naive shape coordinates", () => {
    for (const x of xs(buildSessionProfileShapes(naiveSlices(), 50, ALL_ON))) {
      expect(x).not.toMatch(/Z$/)
      expect(x).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/)
    }
  })

  it("THE BUG: every shape stays inside its own session's span", () => {
    // A UTC-shifted boundary drags the profile hours away from the session it
    // describes -- off-axis entirely on a machine with a large UTC offset.
    const slices = naiveSlices()
    const shapes = buildSessionProfileShapes(slices, 50, ALL_ON)
    const lo = Date.parse(slices[0].startT)
    const hi = Date.parse(slices[slices.length - 1].endT)
    for (const x of xs(shapes)) {
      expect(Date.parse(x)).toBeGreaterThanOrEqual(lo)
      expect(Date.parse(x)).toBeLessThanOrEqual(hi)
    }
  })

  it("each profile starts exactly at its own session start", () => {
    const slices = naiveSlices()
    const shapes = buildSessionProfileShapes(slices, 50, ALL_ON)
    const starts = new Set(shapes.map((s) => s.x0 as string))
    expect(starts).toEqual(new Set([slices[0].startT, slices[1].startT]))
  })

  it("level lines span the full session, rects only a fraction of it", () => {
    const s = slice("2026-08-10T09:30:00", "2026-08-10T16:00:00")
    const shapes = buildSessionProfileShapes([s], 50, ALL_ON)
    const span = Date.parse(s.endT) - Date.parse(s.startT)
    for (const line of shapes.filter((x) => x.type === "line")) {
      expect(Date.parse(line.x1 as string) - Date.parse(line.x0 as string)).toBe(span)
    }
    for (const rect of shapes.filter((x) => x.type === "rect")) {
      const w = Date.parse(rect.x1 as string) - Date.parse(rect.x0 as string)
      expect(w).toBeGreaterThan(0)
      expect(w).toBeLessThanOrEqual(span * 0.9)
    }
  })

  it("Z-suffixed slice boundaries keep that convention", () => {
    const zoned = naiveSlices().map((s) => ({
      ...s,
      startT: new Date(Date.parse(s.startT)).toISOString(),
      endT: new Date(Date.parse(s.endT)).toISOString(),
    }))
    for (const x of xs(buildSessionProfileShapes(zoned, 50, ALL_ON))) {
      expect(x).toMatch(/Z$/)
    }
  })

  it("opacity feeds through to the rect fill", () => {
    const s = [slice("2026-08-10T09:30:00", "2026-08-10T16:00:00")]
    const dim = buildSessionProfileShapes(s, 10, ALL_ON).find((x) => x.type === "rect")
    const bright = buildSessionProfileShapes(s, 90, ALL_ON).find((x) => x.type === "rect")
    const alphaOf = (c: unknown) => Number(String(c).match(/,([\d.]+)\)$/)?.[1] ?? 0)
    expect(alphaOf(bright?.fillcolor)).toBeGreaterThan(alphaOf(dim?.fillcolor))
  })

  it("uses toNaiveString's exact format for naive input", () => {
    const s = [slice("2026-08-10T09:30:00", "2026-08-10T16:00:00")]
    const first = buildSessionProfileShapes(s, 50, ALL_ON)[0]
    expect(first.x0).toBe(toNaiveString(Date.parse("2026-08-10T09:30:00")))
  })
})
