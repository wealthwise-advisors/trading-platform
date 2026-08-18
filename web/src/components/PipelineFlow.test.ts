import { describe, it, expect } from "vitest"
import { PIPELINE_STAGES } from "./PipelineFlow"

/**
 * The pipeline replaced an infographic, and the whole point of the rewrite was
 * that the poster framing went away: no hero title, no closing slogan, no row of
 * adjectives asserting the thing is trustworthy.
 *
 * A browser check proved that once. A test keeps it true -- otherwise the next
 * person to "improve the empty state" adds "DEFENSIBLE · REPEATABLE" back and
 * nothing complains.
 */
describe("pipeline stages", () => {
  it("has the six real stages, in order", () => {
    expect(PIPELINE_STAGES.map((s) => s.title)).toEqual([
      "Market Data", "Resample", "Analysis", "Strategy", "Paper Broker",
      "Scored Result",
    ])
  })

  it("carries none of the infographic framing", () => {
    // Every phrase that was framing rather than content. Checked against all the
    // copy the component can render, not just the titles.
    const BANNED = [
      "bars in", "a number you can defend out", "defensible", "repeatable",
      "measurable", "reproducible", "from raw data to reliable results",
      "every bar counts", "6 steps", "one edge",
    ]
    const copy = PIPELINE_STAGES
      .flatMap((s) => [s.title, s.description, s.badge])
      .join(" | ")
      .toLowerCase()
    for (const phrase of BANNED) {
      expect(copy, `"${phrase}" is back in the pipeline copy`).not.toContain(phrase)
    }
  })

  it("gives every stage its own accent, or the flow would not read as a run", () => {
    const accents = new Set(PIPELINE_STAGES.map((s) => s.accent))
    expect(accents.size).toBe(PIPELINE_STAGES.length)
  })

  it("keeps each stage's copy short enough not to wrap the row apart", () => {
    // The six sit in equal columns; one long line pushes its neighbours' badges
    // out of alignment, which is the layout bug that reads as "sloppy".
    for (const s of PIPELINE_STAGES) {
      expect(s.description.length, `${s.title} description`).toBeLessThanOrEqual(40)
      expect(s.badge.length, `${s.title} badge`).toBeLessThanOrEqual(22)
    }
  })

  it("states a badge and a description for every stage", () => {
    for (const s of PIPELINE_STAGES) {
      expect(s.description.trim()).not.toBe("")
      expect(s.badge.trim()).not.toBe("")
      // A lucide icon in v1 is a forwardRef object, not a plain function, so
      // assert it is renderable rather than guessing its runtime shape.
      expect(s.Icon, `${s.title} icon`).toBeTruthy()
    }
  })
})
