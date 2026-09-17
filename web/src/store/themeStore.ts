// Which palette the app is drawn in.
//
// DARK IS THE DEFAULT AND STAYS THE DEFAULT. This store's only job is to let
// someone opt out of it; a fresh browser with nothing stored gets dark, and
// so does a browser where localStorage throws.
//
// The class on <html> is the single switch: `.dark` is what Tailwind's
// `@custom-variant dark` matches and what every token override in index.css
// keys off. `data-theme` is written alongside it purely so non-CSS code --
// the Plotly charts, mainly -- can read the current theme without parsing a
// className, and so a test can assert on something explicit.
//
// The FIRST application does not happen here. It happens in a small inline
// script in index.html, before React mounts, because a store that applies the
// class on mount paints one dark frame first: a white-to-dark flash on every
// reload for the person who chose light. This store reads back what that
// script already decided rather than deciding again.

import { create } from "zustand"

export type Theme = "dark" | "light"

/** Where the choice is remembered. Shared with the inline script in index.html. */
export const THEME_KEY = "autotrader.theme"

/** Dark unless something valid says otherwise. */
export function readStoredTheme(): Theme {
  try {
    return localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark"
  } catch {
    // Private mode, blocked site data, or a browser that refuses storage.
    // Not a failure -- it means "no preference recorded", which is dark.
    return "dark"
  }
}

/** Put the theme on <html>. The one place the DOM is touched. */
export function applyTheme(theme: Theme) {
  const root = document.documentElement
  root.classList.toggle("dark", theme === "dark")
  root.dataset.theme = theme
  try {
    localStorage.setItem(THEME_KEY, theme)
  } catch {
    // The theme still applies for this page; it just will not be remembered.
  }
}

interface ThemeState {
  theme: Theme
  setTheme: (theme: Theme) => void
  toggle: () => void
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  // What index.html already put on <html>, so the store and the DOM agree from
  // the first render rather than after an effect.
  theme: typeof document !== "undefined" && !document.documentElement.classList.contains("dark")
    ? "light"
    : "dark",
  setTheme: (theme) => {
    applyTheme(theme)
    set({ theme })
  },
  toggle: () => get().setTheme(get().theme === "dark" ? "light" : "dark"),
}))
