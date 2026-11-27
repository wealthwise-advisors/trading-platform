// @vitest-environment jsdom
import { describe, expect, it } from "vitest"
import { DEFAULT_STUDY_SETTINGS, STUDY_SETTINGS_KEY, mergeSettings, useStudySettings } from "./studySettingsStore"

describe("study settings", () => {
  it("fills anything missing from the defaults, section by section", () => {
    const m = mergeSettings({ mfi: { length: 14 }, junk: 1 })
    expect(m.mfi).toEqual({ ...DEFAULT_STUDY_SETTINGS.mfi, length: 14 })
    expect(m.rsi2).toEqual(DEFAULT_STUDY_SETTINGS.rsi2)
    expect(mergeSettings(null)).toEqual(DEFAULT_STUDY_SETTINGS)
  })
  it("saves a change, and Reset puts one study back", () => {
    useStudySettings.getState().update("delta", { filter: 70 })
    expect(JSON.parse(localStorage.getItem(STUDY_SETTINGS_KEY)!).delta.filter).toBe(70)
    useStudySettings.getState().reset("delta")
    expect(useStudySettings.getState().s.delta).toEqual(DEFAULT_STUDY_SETTINGS.delta)
  })
  it("an imported file only sets values of the right type; Reset all puts every study back", () => {
    useStudySettings.getState().importAll({ mfi: { length: "9; drop", overbought: 85, color: 12 }, rsi2: { length: Infinity } })
    const m = useStudySettings.getState().s
    expect(m.mfi).toEqual({ ...DEFAULT_STUDY_SETTINGS.mfi, overbought: 85 })
    expect(m.rsi2.length).toBe(2)
    useStudySettings.getState().resetAll()
    expect(useStudySettings.getState().s).toEqual(DEFAULT_STUDY_SETTINGS)
  })
})
