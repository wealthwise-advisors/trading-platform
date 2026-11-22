/**
 * Settings and chart templates on the server (upgrade plan, Feature 10).
 *
 * Chart style, VWAP levels, Volume Avg, Volume Profile defaults, colours, the time zone,
 * the watchlist, price alerts, favourites and the journal used to live only in this
 * browser's storage, so the owner's laptop and sir's browser showed different charts.
 * The server's settings document is now the source of truth; browser storage stays as
 * the cache every existing loader (loadChartStyle, loadVwapLevels ...) already reads.
 *
 *   pullSettings()  at start-up, before the app renders: server -> browser storage
 *                   (or, the very first time, this browser's settings -> server)
 *   startSync()     every change written to browser storage is saved back
 *   templates       named chart setups: capture, apply (remounts the chart), default
 *
 * Values travel as the exact strings browser storage holds, so nothing is re-encoded
 * on the way and every loader's own validation still applies when it reads them.
 */
import { create } from "zustand"
import { api, type ChartTemplate } from "@/lib/api"
import { CHART_STYLE_STORE_KEY } from "@/lib/chartStyle"
import { VWAP_LEVELS_STORE_KEY } from "@/lib/vwapLevels"
import { VOLUME_AVG_STORE_KEY } from "@/lib/volumeAverage"
import { VP_STORE_KEY } from "@/lib/chartExportSettings"
import { DEVIATION_COLOR_STORE_KEY } from "@/lib/deviationColorSettings"
import { ZONE_KEY } from "@/lib/sessionZone"

/** Which studies are on: written by a template, read when the chart mounts. */
export const STUDIES_STORE_KEY = "autotrader.chartStudies"

/** Setting name on the server -> key in browser storage. */
export const SETTING_STORE_KEYS: Record<string, string> = {
  chartStyle: CHART_STYLE_STORE_KEY,
  vwapLevels: VWAP_LEVELS_STORE_KEY,
  volumeAvg: VOLUME_AVG_STORE_KEY,
  volumeProfile: VP_STORE_KEY,
  deviationColors: DEVIATION_COLOR_STORE_KEY,
  zone: ZONE_KEY,
  watchlist: "watchlist-symbols",         // components/panels/MarketPanels.tsx
  priceAlerts: "price-alerts",            // lib/priceAlerts.ts
  favourites: "instrument-favourites",    // components/InstrumentPicker.tsx
  journal: "trading-journal",             // components/tables/TradingPanels.tsx
}

/** The part of the settings a chart template carries, plus its studies. */
export const TEMPLATE_SETTINGS = ["chartStyle", "vwapLevels", "volumeAvg", "volumeProfile", "deviationColors"] as const

export type Studies = Partial<Record<"vwap" | "bb" | "swingLevels" | "volumeProfile" | "rsi2" | "stochrsi" | "rsi13" | "mfi", boolean>>

function read(key: string): string | null {
  try { return localStorage.getItem(key) } catch { return null }
}
function write(key: string, value: unknown) {
  try {
    if (typeof value === "string") localStorage.setItem(key, value)
    else if (value == null) localStorage.removeItem(key)
  } catch { /* private mode: the app still works, it just does not remember */ }
}

/** Every synced setting this browser holds, as the strings it holds them. */
export function snapshot(): Record<string, string> {
  const out: Record<string, string> = {}
  for (const [name, key] of Object.entries(SETTING_STORE_KEYS)) {
    const v = read(key)
    if (v != null) out[name] = v
  }
  return out
}

/** Server copy -> browser storage. Adds and updates, never removes: a setting only this
 *  browser has is kept (and sent up on the next sync) rather than wiped because another
 *  browser saved first without it.
 *  shortcut: removing a setting therefore does not travel between browsers; add a
 *  tombstone if that is ever needed. */
function applyToStorage(settings: Record<string, unknown>) {
  for (const [name, key] of Object.entries(SETTING_STORE_KEYS)) {
    if (typeof settings[name] === "string") write(key, settings[name])
  }
}

// ── settings document: pull at start-up, push on change ─────────────────────

let version = 0
let lastPushed = ""

/** The copy last agreed with the server, kept in browser storage so it outlives a reload:
 *  a setting that differs from it was changed here and not yet saved. */
const SYNCED_KEY = "autotrader.settingsSynced"
function readSynced(): Record<string, string> | null {
  try { return JSON.parse(read(SYNCED_KEY) ?? "null") } catch { return null }
}
function setSynced(settings: Record<string, unknown>) {
  lastPushed = JSON.stringify(settings)
  write(SYNCED_KEY, lastPushed)
}

/** Start-up: the server's copy, except settings changed here since the last agreed copy
 *  (e.g. a reload within the 2 s before the sync ran) -- those are kept and saved next. */
function mergeFromServer(settings: Record<string, unknown>) {
  const base = readSynced()
  const local = snapshot()
  for (const [name, key] of Object.entries(SETTING_STORE_KEYS)) {
    const pending = base != null && name in local && local[name] !== base[name]
    if (!pending && typeof settings[name] === "string") write(key, settings[name])
  }
}

/** Server -> browser storage, before anything reads it. Never throws: without the server the
 *  app simply runs on what this browser already has, as it always did. */
export async function pullSettings(): Promise<void> {
  try {
    const doc = await api.getSettings()
    if (doc.version > 0) {
      mergeFromServer(doc.settings)
      version = doc.version
      setSynced(doc.settings)                     // anything only this browser has goes up now
      await pushSettings()
    } else {
      // Nothing on the server yet: this browser's settings become the account's, once.
      // From version 0: a stale number here would read as a conflict and wipe them.
      version = 0
      lastPushed = ""
      // A browser with nothing of its own saves nothing: an empty first save would be
      // the copy every other browser then loads.
      if (Object.keys(snapshot()).length) await pushSettings()
      else setSynced({})
    }
    const def = (await api.listTemplates()).find((t) => t.is_default)
    if (def) writeTemplate(def.template)
  } catch {
    /* offline or an older server: keep this browser's own settings */
  }
}

async function pushSettings(): Promise<void> {
  const current = snapshot()
  const json = JSON.stringify(current)
  if (json === lastPushed || !Object.keys(current).length) return
  const res = await fetch("/api/account/settings", {
    method: "PUT", headers: { "Content-Type": "application/json" }, credentials: "same-origin",
    body: JSON.stringify({ settings: current, version }),
  })
  if (res.status === 409) {
    // Saved elsewhere in between: take that copy rather than overwrite it, and say so.
    const doc = await api.getSettings()
    applyToStorage(doc.settings)
    version = doc.version
    setSynced(doc.settings)                     // anything only this browser has goes up next time
    useSettingsNotice.getState().set("Your settings were changed in another tab or on another device; "
                                      + "that copy is loaded. Reload the page to see it everywhere.")
    return
  }
  if (!res.ok) return                       // try again on the next change
  const saved = (await res.json()) as { version: number }
  version = saved.version
  setSynced(current)
}

let timer: ReturnType<typeof setInterval> | undefined
/** Save changes back. Polling browser storage every 2 s catches every writer, including
 *  the ones that know nothing about the server, without touching them. */
export function startSync(everyMs = 2000): () => void {
  clearInterval(timer)
  let busy = false
  timer = setInterval(() => {
    if (busy) return
    busy = true
    pushSettings().catch(() => {}).finally(() => { busy = false })
  }, everyMs)
  return () => clearInterval(timer)
}

/** A one-line notice the app shows when another device's settings were loaded. */
export const useSettingsNotice = create<{ text: string; set: (t: string) => void }>((set) => ({
  text: "", set: (text) => set({ text }),
}))

// ── chart templates ──────────────────────────────────────────────────────────

/** Bumped on apply: the chart is remounted, so it re-reads every setting from storage. */
export const useChartTemplateEpoch = create<{ epoch: number; bump: () => void }>((set) => ({
  epoch: 0, bump: () => set((s) => ({ epoch: s.epoch + 1 })),
}))

export function loadStudies(): Studies {
  try { return JSON.parse(read(STUDIES_STORE_KEY) ?? "{}") as Studies } catch { return {} }
}

/** The chart as it is now: its stored settings, the live Volume Profile settings and the
 *  studies that are on. */
export function captureTemplate(studies: Studies, volumeProfile: Record<string, unknown>): Record<string, unknown> {
  const t: Record<string, unknown> = { studies, volumeProfile: JSON.stringify(volumeProfile) }
  for (const name of TEMPLATE_SETTINGS) {
    if (name === "volumeProfile") continue
    const v = read(SETTING_STORE_KEYS[name])
    if (v != null) t[name] = v
  }
  return t
}

function writeTemplate(t: Record<string, unknown>) {
  for (const name of TEMPLATE_SETTINGS) if (typeof t[name] === "string") write(SETTING_STORE_KEYS[name], t[name])
  if (t.studies && typeof t.studies === "object") write(STUDIES_STORE_KEY, JSON.stringify(t.studies))
}

/** Put a template on the chart now. */
export function applyTemplate(t: ChartTemplate) {
  writeTemplate(t.template)
  useChartTemplateEpoch.getState().bump()
}
