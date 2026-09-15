// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import axe from "axe-core"

import { OscillatorStudyPanel } from "./OscillatorStudyPanel"
import { OSC_STUDIES, type OscKey } from "@/lib/oscillatorStudies"

afterEach(cleanup)

const UNDECIDABLE_IN_JSDOM = {
  "color-contrast": { enabled: false },
  "page-has-heading-one": { enabled: false },
  "landmark-one-main": { enabled: false },
  region: { enabled: false },
}

describe("Oscillator study panel", () => {
  it.each(["rsi2", "stoch", "rsi13", "mfi"] as OscKey[])("%s: labelled dialog, passes axe", async (study) => {
    const { container } = render(<OscillatorStudyPanel study={study} onClose={() => {}} />)
    expect(screen.getByRole("dialog", { name: `${OSC_STUDIES[study].label} settings` })).toBeTruthy()
    const r = await axe.run(container, { rules: UNDECIDABLE_IN_JSDOM })
    expect(r.violations.map((v) => v.id)).toEqual([])
  })

  it.each([["rsi2", "94", "2"], ["stoch", "80", "20"], ["rsi13", "70", "30"]])(
    "%s shows the levels actually drawn (%s / %s), read-only",
    (study, ob, os) => {
      render(<OscillatorStudyPanel study={study as OscKey} onClose={() => {}} />)
      const dialog = screen.getByRole("dialog")
      expect(dialog.textContent).toContain(`overbought${ob}`)
      expect(dialog.textContent).toContain(`oversold${os}`)
      expect(dialog.querySelectorAll("input, select, textarea").length).toBe(0)
    },
  )

  it("MFI says it is not built and shows no values", () => {
    render(<OscillatorStudyPanel study="mfi" onClose={() => {}} />)
    const dialog = screen.getByRole("dialog")
    expect(dialog.textContent).toMatch(/not built yet/)
    expect(dialog.textContent).not.toMatch(/overbought/)
  })

  it("focuses its close button on open; Escape and the button both close it", () => {
    const onClose = vi.fn()
    render(<OscillatorStudyPanel study="rsi2" onClose={onClose} />)
    const close = screen.getByRole("button", { name: "Close" })
    expect(document.activeElement).toBe(close)
    fireEvent.keyDown(close, { key: "Escape" })
    fireEvent.click(close)
    expect(onClose).toHaveBeenCalledTimes(2)
  })
})
