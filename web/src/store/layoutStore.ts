// Focus mode (2026-11-27): one switch that hides the backtest configuration, the
// metric cards and the market panels together, so the chart gets the whole screen.
// The panels keep their own open / closed state underneath; turning Focus off puts
// back exactly what was there. Remembered per browser.
import { create } from "zustand"

export const FOCUS_KEY = "autotrader.layout.focus"

function readFocus(): boolean {
  try { return localStorage.getItem(FOCUS_KEY) === "1" } catch { return false }
}

interface LayoutState {
  focus: boolean
  setFocus: (on: boolean) => void
  toggleFocus: () => void
}

export const useLayoutStore = create<LayoutState>((set, get) => ({
  focus: readFocus(),
  setFocus: (on) => {
    try { localStorage.setItem(FOCUS_KEY, on ? "1" : "0") } catch { /* the switch still works */ }
    set({ focus: on })
  },
  toggleFocus: () => get().setFocus(!get().focus),
}))
