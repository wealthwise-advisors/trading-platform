/**
 * The chart settings an exported report is drawn with.
 *
 * The dashboard chart and the exported HTML report are drawn by separate code
 * (CandlestickChart.tsx and api/report/report.py). The report used to draw
 * fixed defaults of its own, so a report exported after switching MFI off or
 * recolouring the POC disagreed with the chart it was exported from. The chart
 * now publishes its current settings (store/chartSettingsStore.ts), Export
 * Report sends them with the download, and the report draws with them.
 *
 * The shape is api/schemas/chart_settings.py's ChartSettings. Both sides are
 * tested against tests/fixtures/chart_settings_factory.json, so a field added
 * to one and not the other fails a test instead of a download.
 */
import { OSC_ORDER, type OscToggles } from "./oscillatorStudies"
import type { RowHeightMode, TimePerProfile } from "./volumeProfile"
import { defaultPlotStyles, normalizePlotStyles, type PlotStyles } from "./vpPlotStyles"

/** Everything the Volume Profile dialog holds -- what "Save as default" stores. */
export interface VpDialogSettings {
  bins: number
  valueArea: number
  opacity: number
  rowMode: RowHeightMode
  rowHeight: number
  timePer: TimePerProfile
  multiplier: number
  maxProfiles: number
  onExpansion: boolean
  plots: PlotStyles
  showStudy: boolean
  showPlotNames: boolean
  showInputNames: boolean
  leftAxis: boolean
}

export interface ChartExportSettings {
  oscillators: OscToggles
  /** The dialog plus the Volume Profile checkbox itself, which is not saved. */
  volumeProfile: VpDialogSettings & { on: boolean }
}

export const VP_STORE_KEY = "autotrader.volumeProfile.defaults"

/** The oscillator rows a freshly mounted chart shows. */
export const DEFAULT_OSCILLATORS: OscToggles = { rsi2: true, stochrsi: true, rsi13: true, mfi: false }

export function vpFactorySettings(): VpDialogSettings {
  return {
    bins: 48, valueArea: 70, opacity: 50, rowMode: "AUTOMATIC",
    rowHeight: 1, timePer: "CHART", multiplier: 1,
    maxProfiles: 1000, onExpansion: true,
    plots: defaultPlotStyles(),
    showStudy: true, showPlotNames: true, showInputNames: true, leftAxis: false,
  }
}

/**
 * Only the dialog's own fields. A saved default can carry keys an older build
 * wrote (the five `show` booleans `plots` replaced); passing those on would be
 * refused by the report, which accepts nothing the chart does not draw with.
 */
export function pickVpSettings(v: VpDialogSettings): VpDialogSettings {
  return {
    bins: v.bins, valueArea: v.valueArea, opacity: v.opacity, rowMode: v.rowMode,
    rowHeight: v.rowHeight, timePer: v.timePer, multiplier: v.multiplier,
    maxProfiles: v.maxProfiles, onExpansion: v.onExpansion, plots: v.plots,
    showStudy: v.showStudy, showPlotNames: v.showPlotNames,
    showInputNames: v.showInputNames, leftAxis: v.leftAxis,
  }
}

/** The saved "Save as default" settings, or null when none are saved or storage is unavailable. */
export function loadSavedVpSettings(): VpDialogSettings | null {
  try {
    const raw = localStorage.getItem(VP_STORE_KEY)
    if (!raw) return null
    const saved = JSON.parse(raw)
    // `plots` replaced five `show` booleans. An older saved default's flags
    // are carried across rather than dropped.
    return pickVpSettings({ ...vpFactorySettings(), ...saved, plots: normalizePlotStyles(saved?.plots, saved?.show) })
  } catch {
    return null
  }
}

export function buildChartSettings(oscillators: OscToggles, vpOn: boolean, vp: VpDialogSettings): ChartExportSettings {
  return {
    oscillators: Object.fromEntries(OSC_ORDER.map((k) => [k, oscillators[k]])) as OscToggles,
    volumeProfile: { on: vpOn, ...pickVpSettings(vp) },
  }
}

/** What a report exported before the chart has mounted should be drawn with. */
export function initialChartSettings(): ChartExportSettings {
  return buildChartSettings(DEFAULT_OSCILLATORS, true, loadSavedVpSettings() ?? vpFactorySettings())
}
