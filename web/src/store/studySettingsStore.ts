// Every study's own settings, edited in the Studies panel (user, 2026-11-27: "all the
// settings ... MFI settings ... CVD, CVD Divergence"). Defaults are what the chart drew
// before, sir's and thinkorswim's values; remembered per browser.
import { create } from "zustand"

/** A line's look: width in px and its dash. */
export type Dash = "solid" | "dash" | "dot"
export interface OscSet { length: number; overbought: number; oversold: number; color: string; width: number; dash: Dash }

export interface StudySettings {
  rsi2: OscSet
  rsi13: OscSet
  mfi: OscSet
  stochrsi: { rsiLength: number; kPeriod: number; dPeriod: number; slowing: number
              overbought: number; oversold: number; kColor: string; dColor: string; width: number; dash: Dash }
  /** RSI drawn over its lines past overbought / oversold. */
  zones: { above: string; below: string }
  delta: { filter: number; up: string; down: string; bigUp: string; bigDown: string }
  cvd: { up: string; down: string; confluence: string; line: string }
  div: { minStrength: number; strongAbove: number; swings: "10" | "3"
         regular: boolean; hidden: boolean; bull: string; bear: string }
  /** Economic events on the chart: high always, medium if this is on. */
  events: { medium: boolean }
}

export const DEFAULT_STUDY_SETTINGS: StudySettings = {
  rsi2: { length: 2, overbought: 94, oversold: 5, color: "#ffffff", width: 1.8, dash: "solid" },
  rsi13: { length: 13, overbought: 55, oversold: 45, color: "#ffffff", width: 1.8, dash: "solid" },
  mfi: { length: 9, overbought: 80, oversold: 20, color: "#e0a800", width: 1.6, dash: "solid" },
  stochrsi: { rsiLength: 14, kPeriod: 14, dPeriod: 3, slowing: 1, overbought: 80, oversold: 20,
              kColor: "#ff6b6b", dColor: "#e040fb", width: 1.5, dash: "solid" },
  zones: { above: "#ff5252", below: "#00c853" },
  delta: { filter: 60, up: "#00c853", down: "#ff5252", bigUp: "#2979ff", bigDown: "#ff9100" },
  cvd: { up: "#22d3ee", down: "#f472b6", confluence: "#ffd54f", line: "#22d3ee" },
  div: { minStrength: 1.5, strongAbove: 3, swings: "10", regular: true, hidden: true,
         bull: "#22c55e", bear: "#ef4444" },
  events: { medium: true },
}

export const STUDY_SETTINGS_KEY = "autotrader.studies.settings"
type Section = keyof StudySettings

/** Stored settings over the defaults, section by section, so a new field gets its default. */
export function mergeSettings(saved: unknown): StudySettings {
  const s = (saved && typeof saved === "object" ? saved : {}) as Record<string, unknown>
  return Object.fromEntries((Object.keys(DEFAULT_STUDY_SETTINGS) as Section[]).map((k) => {
    const def = DEFAULT_STUDY_SETTINGS[k] as Record<string, unknown>
    const got = (s[k] && typeof s[k] === "object" ? s[k] : {}) as Record<string, unknown>
    // Only a value of the default's own type is taken: an imported file is not trusted.
    const ok = (f: string) => typeof got[f] === typeof def[f] && (typeof got[f] !== "number" || Number.isFinite(got[f]))
    return [k, Object.fromEntries(Object.keys(def).map((f) => [f, ok(f) ? got[f] : def[f]]))]
  })) as unknown as StudySettings
}

function read(): StudySettings {
  try { return mergeSettings(JSON.parse(localStorage.getItem(STUDY_SETTINGS_KEY) ?? "{}")) }
  catch { return mergeSettings({}) }
}

interface StudySettingsState {
  s: StudySettings
  update: <K extends Section>(k: K, patch: Partial<StudySettings[K]>) => void
  reset: (k: Section) => void
  /** Every study back to its default. */
  resetAll: () => void
  /** Replace everything with saved settings (an imported file); unknown keys are ignored. */
  importAll: (saved: unknown) => void
}

export const useStudySettings = create<StudySettingsState>((set, get) => {
  const save = (s: StudySettings) => {
    try { localStorage.setItem(STUDY_SETTINGS_KEY, JSON.stringify(s)) } catch { /* still applies this session */ }
    set({ s })
  }
  return {
    s: read(),
    update: (k, patch) => save({ ...get().s, [k]: { ...get().s[k], ...patch } }),
    reset: (k) => save({ ...get().s, [k]: { ...DEFAULT_STUDY_SETTINGS[k] } }),
    resetAll: () => save(mergeSettings({})),
    importAll: (saved) => save(mergeSettings(saved)),
  }
})
