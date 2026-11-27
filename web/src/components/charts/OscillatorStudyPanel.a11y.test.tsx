// @vitest-environment jsdom
// The oscillator settings are editable since 2026-11-27 (they were read-only).
import { afterEach, beforeEach, describe, expect, it } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import axe from "axe-core"

import { OscillatorStudyPanel } from "./OscillatorStudyPanel"
import type { OscKey } from "@/lib/oscillatorStudies"
import { DEFAULT_STUDY_SETTINGS, useStudySettings } from "@/store/studySettingsStore"

afterEach(cleanup)
beforeEach(() => { localStorage.clear(); useStudySettings.setState({ s: DEFAULT_STUDY_SETTINGS }) })

const UNDECIDABLE_IN_JSDOM = {
  "color-contrast": { enabled: false },
  "page-has-heading-one": { enabled: false },
  "landmark-one-main": { enabled: false },
  region: { enabled: false },
}

describe("Oscillator settings", () => {
  it.each(["rsi2", "stochrsi", "rsi13", "mfi"] as OscKey[])("%s: every field labelled, passes axe", async (study) => {
    const { container } = render(<OscillatorStudyPanel study={study} />)
    const r = await axe.run(container, { rules: UNDECIDABLE_IN_JSDOM })
    expect(r.violations.map((v) => v.id)).toEqual([])
  })

  it.each([["rsi2", 94, 5], ["stochrsi", 80, 20], ["rsi13", 55, 45], ["mfi", 80, 20]] as const)(
    "%s starts at the levels the chart has always drawn (%d / %d)",
    (study, ob, os) => {
      render(<OscillatorStudyPanel study={study} />)
      expect((screen.getByLabelText("overbought") as HTMLInputElement).valueAsNumber).toBe(ob)
      expect((screen.getByLabelText("oversold") as HTMLInputElement).valueAsNumber).toBe(os)
    },
  )

  it("MFI length and levels can be changed, kept in range, and Reset puts them back", () => {
    render(<OscillatorStudyPanel study="mfi" />)
    fireEvent.change(screen.getByLabelText("MFI length"), { target: { value: "14" } })
    fireEvent.change(screen.getByLabelText("overbought"), { target: { value: "250" } })
    expect(useStudySettings.getState().s.mfi).toMatchObject({ length: 14, overbought: 100 })
    fireEvent.click(screen.getByRole("button", { name: /Reset/ }))
    expect(useStudySettings.getState().s.mfi).toEqual(DEFAULT_STUDY_SETTINGS.mfi)
  })
})
