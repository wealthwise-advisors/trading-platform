// The price chart's current display settings, published by CandlestickChart
// and read by Export Report so the exported report is drawn the same way.
// Not persisted: the chart owns persistence ("Save as default"), and the
// initial value already reads what it saved -- see lib/chartExportSettings.ts.

import { create } from "zustand"
import { initialChartSettings, type ChartExportSettings } from "@/lib/chartExportSettings"

interface ChartSettingsState {
  settings: ChartExportSettings
  setSettings: (settings: ChartExportSettings) => void
}

export const useChartSettingsStore = create<ChartSettingsState>((set) => ({
  settings: initialChartSettings(),
  setSettings: (settings) => set({ settings }),
}))
