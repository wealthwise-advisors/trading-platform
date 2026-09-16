// @vitest-environment jsdom
//
// SliderField passed `aria-label` to <Slider> from the day it was written, and
// for all that time the thumb had no name: Radix puts role="slider" on the
// THUMB, and the label was landing on the root. A screen reader announced five
// controls in this panel as "slider", and nothing in the source looked wrong --
// the label was right there in the call.
//
// That is why these assertions read the rendered DOM rather than the props: the
// only way to catch a name that is passed and then dropped is to look at where
// it was supposed to end up.
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"
import axe from "axe-core"

import { SliderField } from "./ConfigParts"

beforeAll(() => {
  // Radix measures with ResizeObserver, which jsdom does not provide.
  if (!("ResizeObserver" in globalThis)) {
    ;(globalThis as { ResizeObserver?: unknown }).ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

afterEach(cleanup)

const UNDECIDABLE_IN_JSDOM = {
  "color-contrast": { enabled: false },
  "page-has-heading-one": { enabled: false },
  "landmark-one-main": { enabled: false },
  region: { enabled: false },
}

function renderField(help?: string) {
  render(
    <SliderField
      label="RSI Overbought"
      help={help}
      value={70}
      onChange={vi.fn()}
      min={50}
      max={99}
      step={1}
    />
  )
}

describe("SliderField", () => {
  it("names the THUMB, which is the element carrying role=slider", () => {
    renderField()
    const thumb = document.querySelector('[role="slider"]')
    expect(thumb).not.toBeNull()
    expect(thumb!.getAttribute("aria-label")).toBe("RSI Overbought")
  })

  it("names the number box too, so both ways in are announced", () => {
    renderField()
    expect(screen.getByRole("spinbutton", { name: "RSI Overbought" })).toBeTruthy()
  })

  it("puts help text in the DOM instead of aria-label on a bare span", () => {
    renderField("Level above which RSI counts as overbought.")
    // ARIA forbids aria-label on an element with no role. The text must still
    // reach a screen reader -- so it lives in the document, visually hidden.
    for (const span of document.querySelectorAll("span[aria-label]")) {
      expect(span.getAttribute("role")).toBeTruthy()
    }
    expect(document.body.textContent).toContain("Level above which RSI counts as overbought.")
  })

  it("passes axe", async () => {
    renderField("Level above which RSI counts as overbought.")
    const r = await axe.run(document.body, { rules: UNDECIDABLE_IN_JSDOM })
    expect(r.violations.map((v) => `${v.id} (${v.nodes.length})`)).toEqual([])
  })
})
