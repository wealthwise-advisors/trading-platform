// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import axe from "axe-core"

import { VolumeProfilePlotTabs } from "./VolumeProfilePlotTabs"
import { defaultPlotStyles, type PlotStyles } from "@/lib/vpPlotStyles"

afterEach(cleanup)

const UNDECIDABLE_IN_JSDOM = {
  "color-contrast": { enabled: false },
  "page-has-heading-one": { enabled: false },
  "landmark-one-main": { enabled: false },
  region: { enabled: false },
}

function setup(styles: PlotStyles = defaultPlotStyles()) {
  const onChange = vi.fn()
  const view = render(<VolumeProfilePlotTabs styles={styles} onChange={onChange} />)
  return { onChange, container: view.container }
}

function showTab(name: string) {
  const tab = screen.getByRole("tab", { name })
  fireEvent.mouseDown(tab)
  fireEvent.click(tab)
}

describe("Volume Profile plot tabs", () => {
  it("has the five reference tabs, in order, and passes axe", async () => {
    const { container } = setup()
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(
      ["POC", "ProfileHigh", "ProfileLow", "VAHigh", "VALow"])
    const r = await axe.run(container, { rules: UNDECIDABLE_IN_JSDOM })
    expect(r.violations.map((v) => v.id)).toEqual([])
  })

  it("every field in a tab has a name a screen reader can read", () => {
    setup()
    for (const name of ["Values", "Draw as", "Style", "Width", "Colour", "Show plot", "Show bubble", "Show title"]) {
      expect(screen.getByLabelText(name)).toBeTruthy()
    }
  })

  it("opens on POC showing the defaults", () => {
    setup()
    expect((screen.getByLabelText("Values") as HTMLSelectElement).value).toBe("numerical")
    expect((screen.getByLabelText("Draw as") as HTMLSelectElement).value).toBe("line")
    expect((screen.getByLabelText("Style") as HTMLSelectElement).value).toBe("solid")
    expect((screen.getByLabelText("Width") as HTMLSelectElement).value).toBe("1")
    expect((screen.getByLabelText("Colour") as HTMLInputElement).value).toBe("#38bdf8")
    expect((screen.getByLabelText("Show plot") as HTMLInputElement).checked).toBe(true)
    expect((screen.getByLabelText("Show bubble") as HTMLInputElement).checked).toBe(true)
    expect((screen.getByLabelText("Show title") as HTMLInputElement).checked).toBe(true)
  })

  it("reports each edit against the plot whose tab is open", () => {
    const { onChange } = setup()
    fireEvent.change(screen.getByLabelText("Style"), { target: { value: "dot" } })
    expect(onChange).toHaveBeenLastCalledWith("poc", { style: "dot" })

    showTab("ProfileLow")
    expect((screen.getByLabelText("Show plot") as HTMLInputElement).checked).toBe(false)
    fireEvent.click(screen.getByLabelText("Show plot"))
    expect(onChange).toHaveBeenLastCalledWith("profileLow", { show: true })

    showTab("VAHigh")
    fireEvent.change(screen.getByLabelText("Width"), { target: { value: "4" } })
    expect(onChange).toHaveBeenLastCalledWith("vah", { width: 4 })
    fireEvent.change(screen.getByLabelText("Colour"), { target: { value: "#ff8800" } })
    expect(onChange).toHaveBeenLastCalledWith("vah", { color: "#ff8800" })
    fireEvent.click(screen.getByLabelText("Show bubble"))
    expect(onChange).toHaveBeenLastCalledWith("vah", { bubble: false })
  })

  it("disables Style when a plot is drawn as markers", () => {
    const s = defaultPlotStyles()
    s.poc.drawAs = "points"
    setup(s)
    expect((screen.getByLabelText("Style") as HTMLSelectElement).disabled).toBe(true)
  })
})
