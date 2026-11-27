/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it } from "vitest"
import { FOCUS_KEY, useLayoutStore } from "./layoutStore"

describe("Focus mode", () => {
  beforeEach(() => { localStorage.clear(); useLayoutStore.getState().setFocus(false) })

  it("toggles, and is remembered across a reload", () => {
    useLayoutStore.getState().toggleFocus()
    expect(useLayoutStore.getState().focus).toBe(true)
    expect(localStorage.getItem(FOCUS_KEY)).toBe("1")
    useLayoutStore.getState().toggleFocus()
    expect(useLayoutStore.getState().focus).toBe(false)
    expect(localStorage.getItem(FOCUS_KEY)).toBe("0")
  })
})
