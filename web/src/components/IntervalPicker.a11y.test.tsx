// @vitest-environment jsdom
//
// The Interval Picker, measured with axe-core and driven the way a person would:
// by name, from the keyboard, across both tabs and the customize view. The rules
// jsdom cannot decide are disabled for the same reasons as in
// accessibility.a11y.test.tsx.
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import axe from "axe-core"

import { IntervalPicker } from "./IntervalPicker"
import { FAV_KEY, LAYOUT_KEY } from "@/lib/intervalPicker"

beforeAll(() => {
  // Radix positions the popup with ResizeObserver, which jsdom does not provide.
  if (!("ResizeObserver" in globalThis)) {
    ;(globalThis as { ResizeObserver?: unknown }).ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

afterEach(() => {
  cleanup()
  localStorage.clear()
})

const UNDECIDABLE_IN_JSDOM = {
  "color-contrast": { enabled: false },
  "page-has-heading-one": { enabled: false },
  "landmark-one-main": { enabled: false },
  region: { enabled: false },
}

async function violations(node: Element) {
  const r = await axe.run(node, { rules: UNDECIDABLE_IN_JSDOM })
  return r.violations.map((v) => `${v.id} (${v.nodes.length})`)
}

function setup(value = "5m") {
  const onChange = vi.fn()
  render(<IntervalPicker value={value} onChange={onChange} />)
  return { onChange, trigger: screen.getByRole("button", { name: `Interval: ${value}` }) }
}

function openPicker(trigger: HTMLElement) {
  fireEvent.click(trigger)
  return screen.getByRole("dialog", { name: "Interval picker" })
}

function showTab(name: RegExp) {
  const tab = screen.getByRole("tab", { name })
  fireEvent.mouseDown(tab)
  fireEvent.click(tab)
}

/** The row buttons in the active tab, in display order. */
function rowNames() {
  return within(screen.getByRole("tabpanel"))
    .getAllByRole("button")
    .map((b) => b.getAttribute("aria-label") ?? "")
    .filter((n) => !/^(Star|Unstar) /.test(n))
}

describe("Interval Picker", () => {
  it("the closed control names the current interval and passes axe", async () => {
    const { trigger } = setup("5m")
    expect(trigger.textContent).toContain("5m")
    expect(await violations(document.body)).toEqual([])
  })

  it("opens a labelled dialog with Favorites and Time frame tabs, passing axe", async () => {
    const { trigger } = setup()
    const dialog = openPicker(trigger)
    expect(screen.getByRole("tab", { name: /favorites/i })).toBeTruthy()
    expect(screen.getByRole("tab", { name: /time frame/i })).toBeTruthy()
    expect(await violations(dialog)).toEqual([])
  })

  it("lists all thirteen intervals as days : interval, straight from the table", () => {
    const { trigger } = setup()
    const dialog = openPicker(trigger)
    showTab(/time frame/i)
    expect(rowNames()).toEqual([
      "1m, 2 days", "2m", "5m, 2 days", "10m, 3 days", "15m, 4 days", "20m, 5 days",
      "25m", "30m, 10 days", "35m", "45m, 15 days", "1h, 25 days",
      "2h, 180 days", "4h, 180 days",
    ])
    const row1m = within(dialog).getByRole("button", { name: "1m, 2 days" })
    expect(row1m.textContent).toContain("2 D : 1m")
    // No day count in the table -> no number shown.
    expect(within(dialog).getByRole("button", { name: "2m" }).textContent).not.toMatch(/\d+ D/)
  })

  it("marks the current interval", () => {
    const { trigger } = setup("15m")
    const dialog = openPicker(trigger)
    showTab(/time frame/i)
    expect(within(dialog).getByRole("button", { name: "15m, 4 days" }).getAttribute("aria-current")).toBe("true")
  })

  it("picking a row reports the interval and closes the popup", () => {
    const { trigger, onChange } = setup()
    const dialog = openPicker(trigger)
    showTab(/time frame/i)
    fireEvent.click(within(dialog).getByRole("button", { name: "10m, 3 days" }))
    expect(onChange).toHaveBeenCalledWith("10m")
    expect(screen.queryByRole("dialog")).toBeNull()
  })

  it("a star persists per browser and fills the Favorites tab", () => {
    const { trigger } = setup()
    const dialog = openPicker(trigger)
    showTab(/time frame/i)
    const star = within(dialog).getByRole("button", { name: "Star 15m" })
    fireEvent.click(star)
    expect(within(dialog).getByRole("button", { name: "Unstar 15m" }).getAttribute("aria-pressed")).toBe("true")
    expect(JSON.parse(localStorage.getItem(FAV_KEY) ?? "[]")).toEqual(["15m"])
    showTab(/favorites/i)
    expect(rowNames()).toEqual(["15m, 4 days"])
  })

  it("an empty Favorites tab says how to fill it, and the popup opens on Time frame", () => {
    const { trigger } = setup()
    openPicker(trigger)
    expect(screen.getByRole("tab", { name: /time frame/i }).getAttribute("aria-selected")).toBe("true")
    showTab(/favorites/i)
    expect(screen.getByRole("tabpanel").textContent).toMatch(/star an interval/i)
  })

  it("opens on Favorites once there are some", () => {
    localStorage.setItem(FAV_KEY, JSON.stringify(["1m"]))
    const { trigger } = setup()
    openPicker(trigger)
    expect(screen.getByRole("tab", { name: /favorites/i }).getAttribute("aria-selected")).toBe("true")
    expect(rowNames()).toEqual(["1m, 2 days"])
  })

  it("Customize list hides and reorders rows, persists it, and passes axe", async () => {
    const { trigger } = setup()
    const dialog = openPicker(trigger)
    fireEvent.click(within(dialog).getByRole("button", { name: "Customize list…" }))
    expect(await violations(dialog)).toEqual([])

    fireEvent.click(within(dialog).getByRole("checkbox", { name: "Show 1m in the list" }))
    fireEvent.click(within(dialog).getByRole("button", { name: "Move 5m up" }))
    // No way to add an interval or type a day count.
    expect(within(dialog).queryByRole("textbox")).toBeNull()
    expect(within(dialog).queryByRole("spinbutton")).toBeNull()

    fireEvent.click(within(dialog).getByRole("button", { name: "Done" }))
    showTab(/time frame/i)
    const names = rowNames()
    expect(names).not.toContain("1m, 2 days")
    expect(names.indexOf("5m, 2 days")).toBeLessThan(names.indexOf("2m"))
    const stored = JSON.parse(localStorage.getItem(LAYOUT_KEY) ?? "{}")
    expect(stored.hidden).toEqual(["1m"])
  })

  it("keyboard: open from a focused button, Escape closes and returns focus to it", async () => {
    const { trigger } = setup()
    // A browser focuses a button before activating it from the keyboard; the
    // testing library does not, so focus it first -- the keyboard user's path.
    trigger.focus()
    const dialog = openPicker(trigger)
    fireEvent.keyDown(dialog, { key: "Escape" })
    expect(screen.queryByRole("dialog")).toBeNull()
    // Radix restores focus on a zero-delay timer after the popup unmounts,
    // so the check has to wait a tick rather than read it synchronously.
    await waitFor(() => expect(document.activeElement).toBe(trigger))
  })
})
