// Named backtest configs, stored against the ACCOUNT rather than the browser.
//
// These used to be localStorage, described here as "just sidebar form state,
// not trading data". Two things made that the wrong call. They are the setups a
// person builds up and reuses, so losing them to a cleared cache is a real
// loss, and they never followed anyone to a second machine. And because the
// server had never seen them, they sat outside every promise
// web/public/privacy.html makes -- closing an account could not delete them,
// and a data export could not include them.
//
// A ONE-WAY migration runs on first load: anything found under the old
// localStorage key is uploaded, then the key is cleared. It is one way on
// purpose -- writing back would resurrect deleted configs on the next device.

import { api } from "./api"
import type { ConfigSnapshot } from "@/store/configStore"

/** The pre-v8 browser key. Read once by migrateLegacyConfigs, then removed. */
const LEGACY_KEY = "autotrader.savedConfigs"

export interface SavedConfig {
  name: string
  savedAt: string
  config: ConfigSnapshot
}

export async function listSavedConfigs(): Promise<SavedConfig[]> {
  const rows = await api.listConfigs()
  return rows.map((r) => ({
    name: r.name,
    savedAt: r.saved_at,
    config: r.config as ConfigSnapshot,
  }))
}

export async function saveConfig(name: string, config: ConfigSnapshot): Promise<void> {
  await api.saveConfig(name, config as unknown as Record<string, unknown>)
}

export async function deleteConfig(name: string): Promise<void> {
  await api.deleteConfig(name)
}

/**
 * Move anything left in localStorage up to the account, once.
 *
 * Best effort throughout: a failure here must never stop the panel loading.
 * Someone whose upload fails still sees their server-side configs, and the
 * local copy is left alone so the next load can try again -- the key is only
 * cleared after every entry has been accepted.
 *
 * Returns how many were migrated, so the caller can say so.
 */
export async function migrateLegacyConfigs(): Promise<number> {
  let legacy: SavedConfig[] = []
  try {
    const raw = localStorage.getItem(LEGACY_KEY)
    if (!raw) return 0
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return 0
    legacy = parsed
  } catch {
    return 0                       // private mode, or unreadable JSON
  }
  if (legacy.length === 0) {
    try { localStorage.removeItem(LEGACY_KEY) } catch { /* nothing to clear */ }
    return 0
  }

  let moved = 0
  for (const entry of legacy) {
    if (!entry?.name || !entry?.config) continue
    try {
      await api.saveConfig(entry.name, entry.config as unknown as Record<string, unknown>)
      moved += 1
    } catch {
      // Leave the key in place so this is retried next time rather than
      // silently dropping somebody's saved setup.
      return moved
    }
  }
  try { localStorage.removeItem(LEGACY_KEY) } catch { /* already gone */ }
  return moved
}
