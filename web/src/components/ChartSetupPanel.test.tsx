// @vitest-environment jsdom
//
// Per-file, matching accessibility.a11y.test.tsx: this vitest version
// ignores environmentMatchGlobs, and the default environment is node,
// where every render fails with "document is not defined".
/**
 * Renders the panel rather than reading the table it renders from.
 *
 * The point of these is that what reaches the SCREEN is the specified setup.
 * chartSetup.test.ts already proves the numbers; if this file only re-read
 * the same table it would prove nothing beyond that the import works.
 */
import { cleanup, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"
import { ChartSetupPanel } from "./ChartSetupPanel"

// Explicit, matching accessibility.a11y.test.tsx. There is no setup file
// registering RTL's auto-cleanup, so without this each render stacks on the
// last and a count of rows returns every row this file has ever drawn.
afterEach(cleanup)

/** The row containing a timeframe's cell, so a day count is read from the
 *  row it actually belongs to rather than from anywhere on the panel. */
function rowFor(tf: string) {
  const rows = screen.getAllByRole("row")
  const row = rows.find((r) => within(r).queryByText(tf))
  if (!row) throw new Error(`no row for ${tf}`)
  return row
}

describe("what the panel puts on screen", () => {
  it("shows every specified pairing", () => {
    render(<ChartSetupPanel active={["5m"]} />)
    for (const [tf, days] of [
      ["1m", "2D"], ["5m", "2D"], ["10m", "3D"], ["15m", "4D"],
      ["20m", "5D"], ["30m", "10D"], ["45m", "15D"], ["1h", "25D"],
    ] as const) {
      expect(within(rowFor(tf)).queryByText(new RegExp(`^${days}`))).not.toBeNull()
    }
  })

  it("renders one row per timeframe the pages offer", () => {
    render(<ChartSetupPanel active={[]} />)
    expect(screen.getAllByRole("row")).toHaveLength(11)
  })

  it("shows a dash, not a number, where nothing was specified", () => {
    render(<ChartSetupPanel active={[]} />)
    for (const tf of ["2m", "25m", "35m"]) {
      expect(within(rowFor(tf)).queryByTitle(/leaves the date range unchanged/i))
        .not.toBeNull()
      // and no day count at all, so nothing on screen can be mistaken for one
      expect(within(rowFor(tf)).queryByText(/\dD/)).toBeNull()
    }
    expect(within(rowFor("30m")).queryByTitle(/leaves the date range unchanged/i))
      .toBeNull()
  })

  it("distinguishes the selected timeframe from the rest", () => {
    render(<ChartSetupPanel active={["15m"]} />)
    const on = within(rowFor("15m")).getByText("15m")
    const off = within(rowFor("30m")).getByText("30m")
    expect(on.className).toContain("text-primary")
    expect(off.className).not.toContain("text-primary")
  })

  it("marks every selection when the grid holds several", () => {
    render(<ChartSetupPanel active={["1m", "1h"]} />)
    expect(within(rowFor("1m")).getByText("1m").className).toContain("text-primary")
    expect(within(rowFor("1h")).getByText("1h").className).toContain("text-primary")
    expect(within(rowFor("5m")).getByText("5m").className).not.toContain("text-primary")
  })

  it("names itself for a screen reader", () => {
    render(<ChartSetupPanel active={["5m"]} />)
    expect(screen.queryByRole("table", { name: /days of history/i })).not.toBeNull()
  })
})
