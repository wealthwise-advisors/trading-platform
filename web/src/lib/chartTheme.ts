// The colours a Plotly chart is drawn in, for the current theme.
//
// WHY THIS EXISTS. Four charts -- CandlestickChart, ElliottWaveChart,
// EquityChart and PnlDistributionChart -- each declared their own
// `const BG = "#14151c"` and `const GRID = "#1a2340"`, plus axis, tick,
// title and hover colours typed out at the call site. A Plotly layout is a
// JavaScript object, not CSS, so a stylesheet cannot reach any of it: under a
// light theme all four kept painting a near-black rectangle in the middle of
// a white page.
//
// One module, read from the stylesheet. The values live in index.css beside
// every other token (--chart-paper, --chart-grid, --chart-ink, --chart-ink-dim,
// --chart-hover), so the two themes are defined in one place rather than in
// CSS for the chrome and in TypeScript for the plots.
//
// WHAT IS DELIBERATELY NOT HERE: series colours. EMA yellow, VWAP magenta,
// the ZigZag legs, candle green and red, the Elliott Wave labels -- those are
// DATA, not chrome. A trader reads them by hue, and a hue that changes with
// the theme is a different reading. They stay exactly as they are in both
// themes; this module only changes what they are drawn ON, which is the part
// that has to change for them to stay readable.

export interface ChartTheme {
  /** Page and plotting-area background. */
  paper: string
  /** Grid and axis lines. */
  grid: string
  /** Axis labels, titles, tick text. */
  ink: string
  /** Secondary text: row titles, sub-labels. */
  inkDim: string
  /** Hover-label and inset-annotation background. */
  hover: string
  /** "dark" | "light" -- for the rare branch that needs to know. */
  name: "dark" | "light"
}

const FALLBACK: ChartTheme = {
  paper: "#14151c",
  grid: "#1a2340",
  ink: "#d4d6e4",
  inkDim: "#8b8ba0",
  hover: "rgba(20, 21, 28, 0.92)",
  name: "dark",
}

/**
 * Read the live values off <html>.
 *
 * Not cached. getComputedStyle is a handful of microseconds and a chart
 * re-layout is orders of magnitude more, so caching would buy nothing and
 * cost a stale palette the first time someone flips the toggle.
 *
 * Every lookup falls back to the dark value. In jsdom -- which is where the
 * chart tests run -- the stylesheet is never loaded and every custom property
 * resolves to the empty string; without the fallback the charts would render
 * with `background: ""` and the tests would assert on nothing.
 */
export function chartTheme(): ChartTheme {
  if (typeof document === "undefined") return FALLBACK
  const css = getComputedStyle(document.documentElement)
  const read = (name: string, fallback: string) =>
    css.getPropertyValue(name).trim() || fallback
  return {
    paper: read("--chart-paper", FALLBACK.paper),
    grid: read("--chart-grid", FALLBACK.grid),
    ink: read("--chart-ink", FALLBACK.ink),
    inkDim: read("--chart-ink-dim", FALLBACK.inkDim),
    hover: read("--chart-hover", FALLBACK.hover),
    name: document.documentElement.dataset.theme === "light" ? "light" : "dark",
  }
}
