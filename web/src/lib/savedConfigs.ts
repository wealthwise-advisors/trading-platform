// Named backtest configs, persisted in the browser (localStorage) -- no
// backend needed, this is just sidebar form state, not trading data.

import type { ConfigSnapshot } from "@/store/configStore"

const STORAGE_KEY = "autotrader.savedConfigs"

export interface SavedConfig {
  name: string
  savedAt: string
  config: ConfigSnapshot
}

function readAll(): SavedConfig[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function writeAll(configs: SavedConfig[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(configs))
}

export function listSavedConfigs(): SavedConfig[] {
  return readAll().sort((a, b) => b.savedAt.localeCompare(a.savedAt))
}

export function saveConfig(name: string, config: ConfigSnapshot) {
  const rest = readAll().filter((c) => c.name !== name)
  rest.push({ name, savedAt: new Date().toISOString(), config })
  writeAll(rest)
}

export function deleteConfig(name: string) {
  writeAll(readAll().filter((c) => c.name !== name))
}
