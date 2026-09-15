/**
 * Per-plot styling for the Volume Profile study: POC, ProfileHigh, ProfileLow,
 * VAHigh and VALow, each with Draw as / Style / Width / Colour and Show plot /
 * Show bubble / Show title -- the tab strip of the reference platform's study
 * dialog.
 *
 * DEFAULTS
 * --------
 * Colours, styles, widths and visibility are the levels as they were always
 * drawn: POC solid #38bdf8, VAHigh and VALow dashed #7dd3fc, ProfileHigh and
 * ProfileLow dotted #94a3b8 and hidden, all at 1.2px.
 *
 * Show bubble and Show title default to ON for every plot, as confirmed against
 * the reference study dialog, where both are ticked. They only draw for a plot
 * that is itself shown, so the hidden profile edges add nothing. Whether plot
 * names and input names should also default to on is still open.
 *
 * WHAT IS NOT HERE
 * ----------------
 * The reference dialog's "Values" field is not implemented -- whether it is
 * needed is awaiting a decision, and a control that does nothing would be worse
 * than no control.
 */
import type { Annotations, Data } from "plotly.js"
import type { ProfileLevelToggles } from "./volumeProfileShapes"

export type PlotKey = "poc" | "profileHigh" | "profileLow" | "vah" | "val"

/** Tab order, as the reference dialog lists them. */
export const PLOT_ORDER: PlotKey[] = ["poc", "profileHigh", "profileLow", "vah", "val"]

export const PLOT_LABEL: Record<PlotKey, string> = {
  poc: "POC", profileHigh: "ProfileHigh", profileLow: "ProfileLow", vah: "VAHigh", val: "VALow",
}

export const DRAW_AS = ["line", "points", "squares", "triangles"] as const
export type DrawAs = (typeof DRAW_AS)[number]
export const DRAW_AS_LABEL: Record<DrawAs, string> = {
  line: "Line", points: "Points", squares: "Squares", triangles: "Triangles",
}

/** Plotly dash names, which are also what gets stored. */
export const LINE_STYLES = ["solid", "longdash", "dash", "dot"] as const
export type LineStyle = (typeof LINE_STYLES)[number]
export const LINE_STYLE_LABEL: Record<LineStyle, string> = {
  solid: "Solid", longdash: "Long dash", dash: "Short dash", dot: "Dotted",
}

export const WIDTHS = [1, 2, 3, 4, 5] as const

export interface PlotStyle {
  show: boolean
  drawAs: DrawAs
  style: LineStyle
  width: number
  color: string
  bubble: boolean
  title: boolean
}
export type PlotStyles = Record<PlotKey, PlotStyle>

const DEFAULTS: PlotStyles = {
  poc:         { show: true,  drawAs: "line", style: "solid", width: 1, color: "#38bdf8", bubble: true, title: true },
  profileHigh: { show: false, drawAs: "line", style: "dot",   width: 1, color: "#94a3b8", bubble: true, title: true },
  profileLow:  { show: false, drawAs: "line", style: "dot",   width: 1, color: "#94a3b8", bubble: true, title: true },
  vah:         { show: true,  drawAs: "line", style: "dash",  width: 1, color: "#7dd3fc", bubble: true, title: true },
  val:         { show: true,  drawAs: "line", style: "dash",  width: 1, color: "#7dd3fc", bubble: true, title: true },
}

/** A fresh copy every call, so no caller can mutate the defaults. */
export function defaultPlotStyles(): PlotStyles {
  return Object.fromEntries(PLOT_ORDER.map((k) => [k, { ...DEFAULTS[k] }])) as PlotStyles
}

const isObj = (v: unknown): v is Record<string, unknown> =>
  !!v && typeof v === "object" && !Array.isArray(v)

/**
 * Coerce stored settings into valid styles.
 *
 * `legacyShow` is the `show` object older saved defaults carry -- five booleans
 * from when these were plain checkboxes. It seeds `show` so a saved default
 * survives the upgrade; a `plots` entry, when present, wins. Anything invalid
 * falls back to the default for that one field rather than discarding the rest.
 */
export function normalizePlotStyles(raw: unknown, legacyShow?: unknown): PlotStyles {
  const out = defaultPlotStyles()
  const r = isObj(raw) ? raw : {}
  const legacy = isObj(legacyShow) ? legacyShow : {}
  for (const key of PLOT_ORDER) {
    const d = out[key]
    const p = isObj(r[key]) ? r[key] : {}
    if (typeof legacy[key] === "boolean") d.show = legacy[key] as boolean
    if (typeof p.show === "boolean") d.show = p.show
    if (typeof p.drawAs === "string" && (DRAW_AS as readonly string[]).includes(p.drawAs)) d.drawAs = p.drawAs as DrawAs
    if (typeof p.style === "string" && (LINE_STYLES as readonly string[]).includes(p.style)) d.style = p.style as LineStyle
    if (typeof p.width === "number" && (WIDTHS as readonly number[]).includes(p.width)) d.width = p.width
    if (typeof p.color === "string" && /^#[0-9a-f]{6}$/i.test(p.color)) d.color = p.color.toLowerCase()
    if (typeof p.bubble === "boolean") d.bubble = p.bubble
    if (typeof p.title === "boolean") d.title = p.title
  }
  return out
}

/** The five show flags, for code that only needs to know what is visible. */
export function plotToggles(styles: PlotStyles): ProfileLevelToggles {
  return {
    poc: styles.poc.show, vah: styles.vah.show, val: styles.val.show,
    profileHigh: styles.profileHigh.show, profileLow: styles.profileLow.show,
  }
}

/** Width 1 is the 1.2px the levels have always been drawn at. */
export function lineWidthPx(width: number): number {
  return width <= 1 ? 1.2 : width
}

const MARKER: Record<Exclude<DrawAs, "line">, string> = {
  points: "circle", squares: "square", triangles: "triangle-up",
}

/** Most markers a level draws across the chart; more would read as a solid bar. */
export const MAX_LEVEL_MARKERS = 60

/**
 * One horizontal level as a Plotly trace.
 *
 * Drawn as a trace rather than a shape so it appears in the unified tooltip,
 * which is how the reference panel lists these values. Marker styles are
 * sampled to at most MAX_LEVEL_MARKERS points.
 */
export function levelTrace(label: string, value: number, xs: string[], style: PlotStyle): Data {
  const common = {
    type: "scatter", name: label, legendgroup: "vp", xaxis: "x", yaxis: "y",
    hovertemplate: `<b>${label}</b>: %{y:.2f}<extra></extra>`,
  }
  if (style.drawAs === "line") {
    return {
      ...common, mode: "lines", x: xs, y: xs.map(() => value),
      line: { color: style.color, width: lineWidthPx(style.width), dash: style.style },
    } as unknown as Data
  }
  const step = Math.max(1, Math.ceil(xs.length / MAX_LEVEL_MARKERS))
  const sx = xs.filter((_, i) => i % step === 0)
  return {
    ...common, mode: "markers", x: sx, y: sx.map(() => value),
    marker: { symbol: MARKER[style.drawAs], size: 3 + 2 * style.width, color: style.color },
  } as unknown as Data
}

/**
 * "Show bubble": the level's price in a tag on the price axis, filled with the
 * plot's colour. It sits just outside the plot area on whichever side the price
 * axis is ("Left axis" in the Options).
 */
export function bubbleAnnotation(value: number, style: PlotStyle, side: "left" | "right"): Partial<Annotations> {
  return {
    x: side === "left" ? 0 : 1, xref: "paper",
    xanchor: side === "left" ? "right" : "left",
    y: value, yref: "y", yanchor: "middle",
    text: value.toFixed(2), showarrow: false,
    font: { size: 10, color: "#0b0c10" },
    bgcolor: style.color, borderpad: 2,
  } as Partial<Annotations>
}

/**
 * "Show title": the plot's name and current value, in the study's title line.
 * Only plots that are shown, titled and have a value contribute, in tab order.
 */
export function titleEntries(styles: PlotStyles, values: Record<PlotKey, number | null>): string {
  return PLOT_ORDER
    .filter((k) => styles[k].show && styles[k].title && values[k] != null)
    .map((k) => `${PLOT_LABEL[k]}: ${(values[k] as number).toFixed(2)}`)
    .join("  ·  ")
}
