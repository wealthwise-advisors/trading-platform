/**
 * @vitest-environment jsdom
 */

/**
 * The theme store, held to the two promises that matter.
 *
 * DARK IS THE DEFAULT. Not "dark unless the OS says otherwise" and not "dark
 * until something throws" -- dark, full stop, unless this browser has recorded
 * a deliberate choice of light. That is the whole point of an OPTIONAL theme,
 * and it is the kind of thing that decays silently: someone adds a
 * prefers-color-scheme read, and a trading terminal starts opening white on a
 * machine whose owner never asked for it.
 *
 * AND IT SURVIVES A RELOAD. A toggle that forgets is worse than no toggle.
 */

import { beforeEach, describe, expect, it, vi } from "vitest"
import { THEME_KEY, applyTheme, readStoredTheme } from "./themeStore"

beforeEach(() => {
  localStorage.clear()
  document.documentElement.className = ""
  delete document.documentElement.dataset.theme
})

describe("which theme a browser gets", () => {
  it("is dark when nothing has been chosen", () => {
    expect(readStoredTheme()).toBe("dark")
  })

  it("is dark when the stored value is junk", () => {
    localStorage.setItem(THEME_KEY, "solarized")
    expect(readStoredTheme()).toBe("dark")
  })

  it("is light only after light was chosen", () => {
    localStorage.setItem(THEME_KEY, "light")
    expect(readStoredTheme()).toBe("light")
  })

  it("is dark when storage itself throws", () => {
    // Private mode, blocked site data, or a browser that refuses storage.
    // "No preference recorded" is dark, and it must not be an exception.
    const spy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("access denied")
    })
    expect(readStoredTheme()).toBe("dark")
    spy.mockRestore()
  })
})

describe("applying a theme", () => {
  it("puts .dark on <html> for dark and takes it off for light", () => {
    applyTheme("dark")
    expect(document.documentElement.classList.contains("dark")).toBe(true)
    applyTheme("light")
    expect(document.documentElement.classList.contains("dark")).toBe(false)
  })

  it("writes data-theme too, which is what non-CSS code reads", () => {
    // lib/chartTheme.ts decides a Plotly palette from this attribute; a
    // className is not something it should have to parse.
    applyTheme("light")
    expect(document.documentElement.dataset.theme).toBe("light")
    applyTheme("dark")
    expect(document.documentElement.dataset.theme).toBe("dark")
  })

  it("remembers the choice, so a reload does not undo it", () => {
    applyTheme("light")
    expect(localStorage.getItem(THEME_KEY)).toBe("light")
    expect(readStoredTheme()).toBe("light")
  })

  it("still applies the theme when the choice cannot be stored", () => {
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota exceeded")
    })
    expect(() => applyTheme("light")).not.toThrow()
    expect(document.documentElement.dataset.theme).toBe("light")
    spy.mockRestore()
  })
})
