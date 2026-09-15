import { afterAll, describe, expect, it } from "vitest"
// ?raw rather than node:fs: the app build type-checks tests with browser types only.
import goldenJson from "../../../tests/fixtures/volume_profile_golden.json?raw"
import { computeVolumeProfile, computeVolumeProfiles } from "./volumeProfile"

// Shared with tests/test_report_chart_settings.py: the exported report's port
// must reproduce these numbers exactly, and so must this code.
const GOLDEN = JSON.parse(goldenJson)

describe("the numbers the exported report is pinned to", () => {
  it("whole-chart profiles", () => {
    for (const c of GOLDEN.single) {
      expect(computeVolumeProfile(GOLDEN.bars, c.bins, c.valueArea / 100)).toEqual(c.expected)
    }
  })

  it("session profiles", () => {
    for (const c of GOLDEN.multi) {
      const { valueArea = 70, ...opts } = c.options
      expect(computeVolumeProfiles(GOLDEN.bars, { ...opts, valueAreaPct: valueArea / 100 })).toEqual(c.expected)
    }
  })

  it("rounding to the cent", () => {
    for (const [v, d, text] of GOLDEN.fixed) expect(v.toFixed(d)).toBe(text)
  })
})

// The test runner's process environment, typed locally so the browser-only
// build does not need Node's type definitions.
const env = (globalThis as unknown as { process: { env: Record<string, string | undefined> } }).process.env
const bar = (t: string) => ({ t, h: 2, l: 1, v: 10 })
const originalTz = env.TZ

afterAll(() => {
  if (originalTz === undefined) delete env.TZ
  else env.TZ = originalTz
})

describe("time per profile: DAY", () => {
  it("files each bar under the date written on it, whatever the viewer's time zone", () => {
    // West of UTC, local evening is already tomorrow in UTC -- where the old
    // grouping, which went through the browser's clock, put these bars.
    env.TZ = "America/New_York"
    const slices = computeVolumeProfiles(
      [bar("2025-01-02T19:30:00"), bar("2025-01-02T20:30:00"), bar("2025-01-02T23:55:00"), bar("2025-01-03T00:05:00")],
      { timePer: "DAY" },
    )
    expect(slices.map((s) => [s.startT, s.endT])).toEqual([
      ["2025-01-02T19:30:00", "2025-01-02T23:55:00"],
      ["2025-01-03T00:05:00", "2025-01-03T00:05:00"],
    ])
  })
})
