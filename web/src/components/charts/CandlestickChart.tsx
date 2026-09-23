// Full-fidelity port of ui/components/charts.py's candlestick_with_trades().
// Indicator math (EMA/RSI/StochRSI) is computed server-side (api/serializers.py)
// and delivered as arrays — this component only handles the plotting/shape/
// annotation logic, mirroring the Python trace-by-trace.

import { useEffect, useMemo, useRef, useState } from "react"
import Plot from "@/lib/plot"
import { chartTheme } from "@/lib/chartTheme"
import { ChartHeader } from "@/components/charts/ChartHeader"
import { ChartLegendMenu, type LegendEntry } from "@/components/charts/ChartLegendMenu"
import { ChartToolRail, type ToolSpec } from "@/components/charts/ChartToolRail"
import { ChartToolbar } from "@/components/charts/ChartToolbar"
import { ChartRangeBar } from "@/components/charts/ChartRangeBar"
import { loadAlerts } from "@/lib/priceAlerts"

/** What Plotly's `dragmode` may be set to here. Plotly's own type is a wide
 *  union including modes this chart never uses (lasso, orbit, turntable). */
type DragMode =
  | "pan" | "zoom" | "select"
  | "drawline" | "drawrect" | "drawcircle" | "drawopenpath"
import { useThemeStore } from "@/store/themeStore"
import type { Data, Layout, Shape, Annotations, PlotRelayoutEvent } from "plotly.js"
import type { OHLCVRecord, IndicatorSeries, ZigZagResponse, TradeRecord, ZigZagPoint } from "@/lib/types"
import { computeRangebreaks } from "@/lib/rangebreaks"
import { ChevronDown, Maximize, Minimize, Save } from "lucide-react"
import { toNaiveString } from "@/lib/isoTime"
import { resampleOHLC, displayBucketMinutes } from "@/lib/resample"
import { buildSessionProfileShapes } from "@/lib/volumeProfileShapes"
import { computeVolumeProfiles } from "@/lib/volumeProfile"
import { DEFAULT_WINDOW_MS, barStepMs, defaultAggregationSpanMs, defaultWindowMs } from "@/lib/chartWindow"
import type { TimePerProfile, RowHeightMode } from "@/lib/volumeProfile"
import {
  PLOT_LABEL, applyPlotPatch, bubbleAnnotation, defaultPlotStyles, levelTrace,
  plotToggles, setShowValueArea, showValueArea, titleEntries,
  type PlotKey, type PlotStyle, type PlotStyles,
} from "@/lib/vpPlotStyles"
import {
  VP_STORE_KEY, buildChartSettings, loadSavedVpSettings, vpFactorySettings,
} from "@/lib/chartExportSettings"
import { useChartSettingsStore } from "@/store/chartSettingsStore"
import {
  OSC_ORDER, OSC_STUDIES, activeOscillatorRows, levelLines, oscillatorRowHeights,
  type OscKey, type OscToggles,
} from "@/lib/oscillatorStudies"
import { VolumeProfilePlotTabs } from "@/components/charts/VolumeProfilePlotTabs"
import { OscillatorStudyPanel } from "@/components/charts/OscillatorStudyPanel"

const GREEN = "#2dd4bf"
const RED = "#f0576b"
// Chart chrome comes from the theme, not from a literal here. BG and GRID used
// to be module constants, which meant a light theme still painted a near-black
// rectangle in the middle of a white page -- a Plotly layout is a JavaScript
// object and no stylesheet can reach it. Series colours are NOT themed: see
// the note in lib/chartTheme.ts for why a trader's hues must not move.
const SWING_COLORS = ["#ffd23f", "#c77dff", "#4cc9f0", "#7ee787"]

interface CandlestickChartProps {
  symbol: string
  strategyName: string
  bars: OHLCVRecord[]
  indicators: IndicatorSeries
  zigzag: ZigZagResponse
  trades: TradeRecord[]
  showZigzag?: boolean
  /** Initial state of the StochRSI panel's checkbox. */
  showStochRsi?: boolean
  // Session VWAP with ±2σ bands, overlaid on the price panel. Same
  // opt-out shape as showStochRsi. Draws nothing when the dataset has no
  // volume, regardless of this flag.
  showVwap?: boolean
  /** Initial state of the Volume Profile toggle. The profile itself is
   *  computed in-component from `bars` so its settings can redraw without a
   *  refetch — see lib/volumeProfile.ts. */
  showVolumeProfile?: boolean
  /** The instrument's full name and venue, for the header line. Optional and
   *  omitted rather than guessed when the catalogue has not got them. */
  description?: string | null
  exchange?: string | null
  /** Bar interval, as the header prints it. */
  interval: string
}


/** The last non-null reading of a series, or null when it has none.
 *  null means "nothing to show", which prints as an em dash -- never as 0,
 *  which would claim a measurement that was never taken. */
function lastReading(xs?: (number | null)[]): number | null {
  if (!xs) return null
  for (let i = xs.length - 1; i >= 0; i--) if (xs[i] != null) return xs[i] as number
  return null
}

const fmtPrice = (n: number | null | undefined) =>
  n == null ? "—" : n.toLocaleString(undefined,
    { minimumFractionDigits: 2, maximumFractionDigits: 2 })

/** Width reserved for the price-axis tick labels, in pixels.
 *  Five digits and a separator at 11px; 52 clears "7,713.31" with room. */
const AXIS_W = 52
/** Width reserved for the on-chart legend when it is showing, in pixels.
 *  Wide enough for the longest entry this chart produces ("Volume Profile")
 *  at 10px plus its marker column. Only applied while the legend is on. */
const LEGEND_W = 104
// Default view opens on the last ~2 hours rather than the whole session, or on
// the last 40 bars once a bar is two hours wide -- see lib/chartWindow.ts. It is
// worked out once per render (`defaultWindow`) because swing-header collision
// detection, candle aggregation and both axis ranges must use the same window.

// Mirrors Plotly's make_subplots(row_heights=[...], vertical_spacing=v)
// domain math — returns [[y0,y1], ...] top-to-bottom for each row.
function rowDomains(heights: number[], spacing: number): [number, number][] {
  const total = heights.reduce((a, b) => a + b, 0)
  const available = 1 - (heights.length - 1) * spacing
  const domains: [number, number][] = []
  let yTop = 1
  for (const h of heights) {
    const rowHeight = (h / total) * available
    const y0 = yTop - rowHeight
    domains.push([y0, yTop])
    yTop = y0 - spacing
  }
  return domains
}


/** One study in the Indicators menu: a checkbox row that reads as a menu item. */
function MenuToggle({
  label, checked, onChange, disabled, hint,
}: {
  label: string
  checked: boolean
  onChange: (v: boolean) => void
  disabled?: boolean
  hint?: string
}) {
  return (
    <label role="menuitemcheckbox" aria-checked={checked}
           title={hint}
           className={`flex items-center gap-2 px-3 py-1.5 ${disabled
             ? "opacity-60 cursor-not-allowed" : "cursor-pointer hover:bg-[color:var(--raise-3)]"}`}>
      <input type="checkbox" checked={checked} disabled={disabled}
             onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  )
}

export function CandlestickChart({
  // strategyName is still part of the props -- every caller passes it and the
  // export path reads the same shape -- but nothing in here draws it: the
  // strategy and run date are named by the status bar.
  //
  // symbol, description, exchange and interval ARE drawn now: this component
  // renders ChartHeader itself, so that the instrument line and the chart's
  // own controls can share one row rather than being two siblings in a page
  // that cannot put them on the same line.
  symbol, bars, indicators, zigzag, trades, showZigzag = true,
  showStochRsi = true, showVwap = true, showVolumeProfile = true,
  description, exchange, interval,
}: CandlestickChartProps) {
  // Subscribing (rather than only calling chartTheme()) is what makes the
  // header toggle repaint an open chart: without it the plot keeps the
  // palette it was first built with until something else re-renders it.
  useThemeStore((st) => st.theme)
  const { paper: BG, grid: GRID, ink: INK, inkDim: INK_DIM, hover: HOVER } = chartTheme()
  // react-plotly.js's useResizeHandler only listens for window "resize"
  // events -- it never fires when the CONTAINER grows/shrinks from a pure
  // CSS/flex change (KPI row shrinking, footer removal, etc., all of which
  // happened repeatedly this session). That's why "unused space below the
  // indicator panels" kept recurring even as the surrounding layout genuinely
  // got taller: the Card grew, but the already-mounted Plot never learned
  // its container had more room.
  //
  // A ResizeObserver on the wrapping div catches every resize source (flex,
  // grid, KPI/footer changes), not just the browser window -- but calling
  // Plotly.Plots.resize() directly requires importing the full "plotly.js"
  // package a second time (separately from whatever react-plotly.js already
  // resolves internally), which broke the whole page (blank screen) when
  // tried. Dispatching a synthetic window "resize" event instead piggybacks
  // on react-plotly.js's own existing, already-working resize handling --
  // same practical effect, no second Plotly import, no risk.
  // ── VWAP settings (session-only, deliberately not persisted) ───────────
  // The server delivers VWAP at a fixed ±2σ. Rather than refetch when the
  // user changes a deviation, sigma is recovered from that payload --
  // sigma = (upper − vwap) / 2 -- and the bands are rebuilt for any
  // multiplier. Verified exact against a server-side recomputation at 3σ:
  // maximum difference 0.0000000000. So the redraw is instant, needs no round
  // trip, and does not fork the VWAP maths into TypeScript.
  const [vwapOn, setVwapOn] = useState(showVwap)
  // Bollinger Bands (20, 2). Off by default: the price panel already carries
  // VWAP and its bands, and stacking a second envelope on top of that without
  // being asked makes the candles harder to read, not easier.
  const [bbOn, setBbOn] = useState(false)
  const [vwapPanelOpen, setVwapPanelOpen] = useState(false)
  /**
   * Whether Plotly's own legend is drawn beside the plot.
   *
   * OFF by default, which is what buys the chart its extra width: measured
   * at 1536px the legend column and its clearance were 139px of a 907px
   * figure -- 15% of the plot spent restating what the Legend menu on the
   * header row now says on demand. It is a toggle in that menu rather than a
   * deletion: on a wide screen a legend you can read without leaving the
   * candles is worth the space, and that is a judgement about the window,
   * not about the app.
   */
  const [legendOnChart, setLegendOnChart] = useState(false)

  /* ── Drawing rail state ───────────────────────────────────────────────
     `drawTool` is which rail button is lit; `dragMode` is what Plotly does
     with the mouse. They are separate because two rail buttons -- the
     horizontal line and the note -- are ACTIONS that add a shape and then
     hand the mouse back, rather than modes the chart stays in.

     `userShapes` holds only what the user drew. It is kept apart from the
     `shapes` the chart builds for VWAP bands, the value area and the swing
     structure, so Clear All removes the user's drawings and cannot wipe a
     study the chart is responsible for. */
  const [drawTool, setDrawTool] = useState<string>("pan")
  const [dragMode, setDragMode] = useState<DragMode>("pan")
  const [userShapes, setUserShapes] = useState<Partial<Shape>[]>([])
  const [userNotes, setUserNotes] = useState<Partial<Annotations>[]>([])
  /** How many shapes/annotations the CHART built this render. The relayout
   *  handler slices at these to tell the user's drawings from the studies. */
  const builtInShapeCount = useRef(0)
  const builtInNoteCount = useRef(0)
  /** Which collection the last drawing went into, so Undo removes the thing
   *  the user actually added last rather than always a shape. */
  const lastDrawn = useRef<"shape" | "note">("shape")
  /** Undone drawings, newest last. Cleared as soon as a NEW drawing is made:
   *  redoing onto a changed chart would put a shape back into a history that
   *  no longer leads to it, which is how redo stacks produce surprises. */
  const [redoStack, setRedoStack] = useState<Partial<Shape>[]>([])

  /** Price alerts, drawn as levels. Re-read rather than held as the source of
   *  truth, so the Alerts rail panel and the chart cannot disagree. */
  const [alertTick, setAlertTick] = useState(0)
  const alerts = useMemo(() => loadAlerts(), [alertTick])

  /** Bottom bar state. `activeRange` only lights a button; the window itself
   *  lives in visibleRange, so a mouse pan un-lights the preset it no longer
   *  matches rather than leaving a button claiming a range that is not shown. */
  const [activeRange, setActiveRange] = useState<string | null>(null)
  const [logScale, setLogScale] = useState(false)
  const [devUp, setDevUp] = useState(2)
  const [devDn, setDevDn] = useState(-2)
  // "DAY" is the only timeframe the engine implements -- VWAP resets on the
  // calendar date. It is surfaced as a labelled control anyway so the reset
  // behaviour is visible rather than an unstated assumption.
  const [vwapTimeframe] = useState("DAY")
  const [vwapStyle, setVwapStyle] = useState({
    vwap: { color: "#e879f9", width: 1.8, dash: "solid" },
    upper: { color: "#fde047", width: 1.5, dash: "solid" },
    lower: { color: "#f472b6", width: 1.5, dash: "solid" },
  })

  // ── Volume Profile settings (session-only) ─────────────────────────────
  // Computed locally rather than refetched: bins re-bucket from raw bars, which
  // the delivered histogram cannot reconstruct. See lib/volumeProfile.ts.
  const [vpOn, setVpOn] = useState(showVolumeProfile)
  const [vpPanelOpen, setVpPanelOpen] = useState(false)
  const [vpBins, setVpBins] = useState(48)
  const [vpValueArea, setVpValueArea] = useState(70)
  const [vpOpacity, setVpOpacity] = useState(50)
  // Per-plot styles for POC, ProfileHigh, ProfileLow, VAHigh and VALow. The
  // defaults are the look these levels always had -- see lib/vpPlotStyles.ts.
  const [vpPlots, setVpPlots] = useState<PlotStyles>(defaultPlotStyles)
  const vpShow = plotToggles(vpPlots)
  // applyPlotPatch, not a plain merge: showing or hiding either edge of the
  // value area moves both, so the "show value area" input below and the VAHigh
  // and VALow tabs can never disagree.
  const setVpPlot = (key: PlotKey, patch: Partial<PlotStyle>) =>
    setVpPlots((s) => applyPlotPatch(s, key, patch))
  // Oscillator panels as opt-in studies, the way VWAP and Volume Profile work.
  // RSI(2), StochRSI and RSI(13) start on. MFI starts off: four oscillator rows
  // at once are too short to read, which is why each has its own checkbox.
  const [osc, setOsc] = useState<OscToggles>({ rsi2: true, stochrsi: showStochRsi, rsi13: true, mfi: false })
  const [oscPanel, setOscPanel] = useState<OscKey | null>(null)
  const [vpRowMode, setVpRowMode] = useState<RowHeightMode>("AUTOMATIC")
  const [vpRowHeight, setVpRowHeight] = useState(1)
  const [vpTimePer, setVpTimePer] = useState<TimePerProfile>("CHART")
  const [vpMultiplier, setVpMultiplier] = useState(1)
  const [vpMaxProfiles, setVpMaxProfiles] = useState(1000)
  const [vpOnExpansion, setVpOnExpansion] = useState(true)
  // Options column of the reference dialog.
  const [vpShowStudy, setVpShowStudy] = useState(true)
  // Both on by default, as in the reference dialog.
  const [vpShowPlotNames, setVpShowPlotNames] = useState(true)
  const [vpShowInputNames, setVpShowInputNames] = useState(true)
  // false: the reference puts the price scale on the RIGHT, which is also
  // where every trading terminal puts it. Still a tick in the Volume Profile
  // dialog ("Left axis"), so anyone who wants it back has it.
  const [vpLeftAxis, setVpLeftAxis] = useState(false)
  const [vpSavedNote, setVpSavedNote] = useState("")
  const [indicatorMenu, setIndicatorMenu] = useState(false)
  const [saveMenu, setSaveMenu] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)

  // Fullscreen is driven by the BROWSER, not by this state -- Escape and the
  // F11 key both exit it without going through the button, so the flag has to
  // follow the document rather than be toggled optimistically.
  useEffect(() => {
    const sync = () => setIsFullscreen(document.fullscreenElement === containerRef.current)
    document.addEventListener("fullscreenchange", sync)
    return () => document.removeEventListener("fullscreenchange", sync)
  }, [])

  const toggleFullscreen = () => {
    const el = containerRef.current
    if (!el) return
    // A rejected request (an iframe without allowfullscreen, a browser that
    // refuses it) must not leave the button claiming a state it is not in.
    if (document.fullscreenElement === el) void document.exitFullscreen().catch(() => {})
    else void el.requestFullscreen?.().catch(() => {})
  }

  /** Plotly's own PNG export, from the menu rather than only the modebar. */
  const downloadPng = () => {
    const plot = containerRef.current?.querySelector<HTMLElement>(".js-plotly-plot")
    const btn = plot?.querySelector<HTMLElement>('[data-title="Download plot as a PNG"]')
    btn?.click()
  }

  // ── Save as default / Reset to factory default ─────────────────────────
  // Factory values live here so "reset" has something authoritative to return
  // to; "save as default" writes the current set to localStorage and it is
  // restored on the next mount.
  // The values themselves live in lib/chartExportSettings.ts, which the export
  // request and the report's contract test read too.
  const VP_FACTORY = vpFactorySettings()

  const applyVpSettings = (v: typeof VP_FACTORY) => {
    setVpBins(v.bins); setVpValueArea(v.valueArea); setVpOpacity(v.opacity)
    setVpRowMode(v.rowMode); setVpRowHeight(v.rowHeight); setVpTimePer(v.timePer)
    setVpMultiplier(v.multiplier); setVpMaxProfiles(v.maxProfiles)
    setVpOnExpansion(v.onExpansion); setVpPlots(v.plots)
    setVpShowStudy(v.showStudy); setVpShowPlotNames(v.showPlotNames)
    setVpShowInputNames(v.showInputNames); setVpLeftAxis(v.leftAxis)
  }

  useEffect(() => {
    // Corrupt or unavailable storage just means factory defaults.
    const saved = loadSavedVpSettings()
    if (saved) applyVpSettings(saved)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const saveVpDefaults = () => {
    const payload = {
      bins: vpBins, valueArea: vpValueArea, opacity: vpOpacity,
      rowMode: vpRowMode, rowHeight: vpRowHeight, timePer: vpTimePer,
      multiplier: vpMultiplier, maxProfiles: vpMaxProfiles,
      onExpansion: vpOnExpansion, plots: vpPlots, showStudy: vpShowStudy,
      showPlotNames: vpShowPlotNames, showInputNames: vpShowInputNames,
      leftAxis: vpLeftAxis,
    }
    try {
      localStorage.setItem(VP_STORE_KEY, JSON.stringify(payload))
      setVpSavedNote("Saved — these settings will load next time.")
    } catch {
      setVpSavedNote("Could not save (browser storage unavailable).")
    }
    setTimeout(() => setVpSavedNote(""), 3000)
  }

  const resetVpFactory = () => {
    try { localStorage.removeItem(VP_STORE_KEY) } catch { /* nothing to clear */ }
    applyVpSettings(VP_FACTORY)
    setVpSavedNote("Reset to factory defaults.")
    setTimeout(() => setVpSavedNote(""), 3000)
  }

  // ── What the chart is drawing with, for Export Report ──────────────────
  // Published on every change, so the report downloaded next is drawn with the
  // same oscillator rows and Volume Profile settings -- see
  // lib/chartExportSettings.ts. Left in place on unmount: switching to another
  // results tab and exporting from there still describes the chart as last seen.
  const publishChartSettings = useChartSettingsStore((s) => s.setSettings)
  useEffect(() => {
    publishChartSettings(buildChartSettings(osc, vpOn, {
      bins: vpBins, valueArea: vpValueArea, opacity: vpOpacity, rowMode: vpRowMode,
      rowHeight: vpRowHeight, timePer: vpTimePer, multiplier: vpMultiplier,
      maxProfiles: vpMaxProfiles, onExpansion: vpOnExpansion, plots: vpPlots,
      showStudy: vpShowStudy, showPlotNames: vpShowPlotNames,
      showInputNames: vpShowInputNames, leftAxis: vpLeftAxis,
    }))
  }, [publishChartSettings, osc, vpOn, vpBins, vpValueArea, vpOpacity, vpRowMode, vpRowHeight,
      vpTimePer, vpMultiplier, vpMaxProfiles, vpOnExpansion, vpPlots, vpShowStudy,
      vpShowPlotNames, vpShowInputNames, vpLeftAxis])

  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      window.dispatchEvent(new Event("resize"))
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Tracks the user's current x-axis zoom (range-selector button, scroll
  // zoom, or pan), null meaning "no interaction yet, use the default 2-hour
  // window". Needed because the price y-axis range below must be computed
  // from whatever's actually visible on screen -- without this, the y-range
  // stayed permanently locked to the initial 2-hour window's price band, so
  // zooming/panning out (e.g. clicking "All") revealed candles priced
  // outside that band only as blank space: their x/y data was correct, they
  // were just plotted above/below the fixed, now-stale y-axis bounds.
  const [visibleRange, setVisibleRange] = useState<{ start: number; end: number } | null>(null)
  useEffect(() => setVisibleRange(null), [bars])

  /**
   * A rail button was pressed.
   *
   * Most tools just set the dragmode and stay lit until another is picked --
   * that is how a drawing tool behaves. Three do something else:
   *
   *   hline   adds a horizontal level immediately. There is no Plotly
   *           dragmode for "horizontal line", and asking the user to drag a
   *           perfectly level line by hand is the wrong tool for the job, so
   *           this drops one at the last close and leaves it draggable.
   *   text    pins a note. Plotly has no draw-text mode either; the label is
   *           an annotation, editable in place once placed.
   *   clear   removes the user's drawings, and returns the mouse to Pan so
   *           the chart is not left in a draw mode with nothing to erase.
   */
  /**
   * Undo the most recent drawing, whichever kind it was.
   *
   * Notes and shapes are separate Plotly collections with no shared ordering,
   * so "most recent" is decided by which list was last added to -- tracked in
   * lastDrawn rather than guessed from array lengths. Only shapes go on the
   * redo stack: an undone annotation carries text the user may have edited in
   * place, and restoring a stale copy of it would silently discard that edit.
   */
  const undoDrawing = () => {
    if (lastDrawn.current === "note" && userNotes.length) {
      setUserNotes((n) => n.slice(0, -1))
      if (userNotes.length === 1) lastDrawn.current = "shape"
      return
    }
    if (userShapes.length) {
      setRedoStack((r) => [...r, userShapes[userShapes.length - 1]])
      setUserShapes((s) => s.slice(0, -1))
      return
    }
    if (userNotes.length) setUserNotes((n) => n.slice(0, -1))
  }

  const redoDrawing = () => {
    if (!redoStack.length) return
    setUserShapes((s) => [...s, redoStack[redoStack.length - 1]])
    setRedoStack((r) => r.slice(0, -1))
    lastDrawn.current = "shape"
  }

  const pickTool = (t: ToolSpec) => {
    if (t.id === "clear") {
      setRedoStack([])
      setUserShapes([])
      setUserNotes([])
      setDrawTool("pan")
      setDragMode("pan")
      return
    }
    if (t.id === "erase") { undoDrawing(); return }
    if (t.id === "hline") {
      const last = bars.length ? bars[bars.length - 1].c : null
      if (last == null) return          // nothing to anchor to; do nothing rather than draw at 0
      setUserShapes((s) => [...s, {
        type: "line", xref: "paper", x0: 0, x1: 1, yref: "y", y0: last, y1: last,
        line: { color: "#38bdf8", width: 1, dash: "dot" },
        editable: true,
      } as Partial<Shape>])
      lastDrawn.current = "shape"
      return                            // an action, not a mode: the rail stays where it was
    }
    if (t.id === "text") {
      const last = bars.length ? bars[bars.length - 1] : null
      if (!last) return
      setUserNotes((n) => [...n, {
        x: toNaiveString(new Date(last.t).getTime()), y: last.c, xref: "x", yref: "y",
        text: "Note", showarrow: true, arrowhead: 2, ax: 0, ay: -30,
        font: { color: "#38bdf8", size: 11 },
        bgcolor: "rgba(15,23,42,0.85)", bordercolor: "#38bdf8", borderwidth: 1,
        captureevents: true,
      } as Partial<Annotations>])
      lastDrawn.current = "note"
      return
    }
    if (t.mode) {
      setDrawTool(t.id)
      setDragMode(t.mode as DragMode)
    }
  }

  const handleRelayout = (ev: PlotRelayoutEvent) => {
    const e = ev as unknown as Record<string, unknown>

    /* A shape was drawn, dragged or erased.
       Plotly hands back the WHOLE shapes array, which is the chart's own
       study shapes followed by the user's. Everything past the built-in
       count is the user's, so slicing there keeps their drawings without
       ever copying a VWAP band or a value-area rectangle into user state --
       which would duplicate it on the next render and make it un-erasable.

       ONLY WHEN IT ACTUALLY CHANGED. Plotly includes `shapes` on relayouts
       that have nothing to do with drawing -- a pan recomputes every
       paper-referenced shape and reports the lot. Setting state
       unconditionally there queued a re-render mid-drag on every pointer
       move, and the chart stopped panning: e2e's "dragging the chart still
       pans it" caught exactly that. Comparing first makes a pan a no-op here
       while a real edit still lands. */
    if (Array.isArray(e.shapes)) {
      // `editable` is stamped on here rather than via a global `edits` config,
      // so a drawing can be dragged and reshaped afterwards while the chart's
      // own study shapes stay fixed -- see the config block for why that
      // distinction matters to panning.
      const next = (e.shapes as Partial<Shape>[])
        .slice(builtInShapeCount.current)
        .map((sh) => ({ ...sh, editable: true }) as Partial<Shape>)
      if (JSON.stringify(next) !== JSON.stringify(userShapes)) setUserShapes(next)
    }
    /* A note was moved or its text edited. Same slice, same guard. */
    if (Array.isArray(e.annotations)) {
      const next = (e.annotations as Partial<Annotations>[]).slice(builtInNoteCount.current)
      if (JSON.stringify(next) !== JSON.stringify(userNotes)) setUserNotes(next)
    }

    if (e["xaxis.autorange"]) {
      if (!bars.length) return
      setVisibleRange({ start: new Date(bars[0].t).getTime(), end: new Date(bars[bars.length - 1].t).getTime() })
      setActiveRange("All")     // autorange IS the whole range
      return
    }
    const r0 = e["xaxis.range[0]"]
    const r1 = e["xaxis.range[1]"]
    if (typeof r0 === "string" && typeof r1 === "string") {
      setVisibleRange({ start: new Date(r0).getTime(), end: new Date(r1).getTime() })
      // Dragged or zoomed by hand: whatever preset was lit no longer
      // describes what is on screen, so nothing is lit.
      setActiveRange(null)
    }
  }

  const t = bars.map((b) => b.t)
  const defaultWindow = defaultWindowMs(t)
  // Display candles are aggregated to suit the VISIBLE window, not to a fixed
  // bucket. This used to be resampleOHLC(bars, 9), which is comfortable in the
  // default 2-hour window but collapses when zoomed out: a 37-hour Globex
  // range put 217 candles in the panel at 2.48px each, so they read as
  // hairlines under the 12px trade markers. The window used here must match
  // the one xRange applies below, or the aggregation and the axis disagree
  // about what is on screen.
  // The default view is handed over as a bar count for 2h and 4h bars (see
  // defaultAggregationSpanMs): the clock window spans overnight gaps, which the
  // aggregation would count as bars and merge 2h candles into 4h ones.
  const aggregationDefault = defaultAggregationSpanMs(t)
  const displayWindowMs = (() => {
    if (bars.length < 2) return aggregationDefault
    const first = new Date(bars[0].t).getTime()
    const last = new Date(bars[bars.length - 1].t).getTime()
    if (visibleRange) {
      return Math.max(1, Math.min(last, visibleRange.end) - Math.max(first, visibleRange.start))
    }
    return Math.min(aggregationDefault, last - first || aggregationDefault)
  })()
  const candleBars = resampleOHLC(bars, displayBucketMinutes(bars, displayWindowMs))

  // Row layout is built dynamically: price is always row 1, then one row per
  // oscillator switched on, in the order RSI(2) / StochRSI / RSI(13) / MFI. Axis
  // suffixes are assigned by position, so a row below one that is switched off
  // moves up a slot. See lib/oscillatorStudies.ts.
  const indicatorRows = activeOscillatorRows(osc)
  const totalRows = 1 + indicatorRows.length
  const axisSuffix = ["", "2", "3", "4", "5"].slice(0, totalRows)
  const rowIndexOf = (name: (typeof indicatorRows)[number]) => 1 + indicatorRows.indexOf(name)
  const suffixOf = (name: (typeof indicatorRows)[number]) => axisSuffix[rowIndexOf(name)]

  // Price panel stays the dominant focus; the rest splits evenly across the
  // active indicator rows.
  //
  // Raised 0.55 -> 0.62 (candles read as too compact against the three
  // indicator rows). These are SHARES of the plotting area, so on their own a
  // bigger price share can only shrink the indicator rows. Their absolute
  // height is clawed back from three places that all freed real estate:
  // tighter inter-row spacing (0.05 -> 0.035), the range-selector no longer
  // occupying a margin row of its own, and swing headers capped at two
  // stacked rows instead of climbing to five.
  //
  // Raised again 0.62 -> 0.68 on a follow-up pass, with row spacing tightened
  // 0.035 -> 0.028 to keep the indicator rows off the floor. Measured at a
  // 683px container across the three passes:
  //
  //   price panel      221px -> 312px -> 350px   (+58% overall)
  //   each indicator    60px ->  64px ->  55px
  //
  // 55px still shows an RSI trace against its 0/50/100 gridlines, which is
  // what those rows are for. Going further starts costing legibility rather
  // than whitespace, so this is the last increase without a taller container.
  //
  // Total height is deliberately NOT increased -- see the minHeight note on
  // the wrapper div; forcing this taller than the parent Card clips the
  // bottom rows off entirely rather than shrinking them.
  const PRICE_WEIGHT = 0.68
  const ROW_SPACING = 0.028
  // With every oscillator off, price takes the whole chart instead of dividing
  // the indicator share by zero rows.
  const domains = rowDomains(oscillatorRowHeights(indicatorRows.length, PRICE_WEIGHT), ROW_SPACING)

  // The x-axis only shows a date label where the visible range crosses a day
  // boundary (Plotly's default date-axis behavior) -- when zoomed into a

  const data: Data[] = []
  const shapes: Partial<Shape>[] = []

  /* Price alerts for THIS instrument, drawn as dashed levels across the plot.
     Filtered by symbol so an ES alert does not appear on an NQ chart. Amber
     rather than the drawing rail's blue: an alert is the chart telling the
     user something, not something the user drew. */
  const alertShapes: Partial<Shape>[] = alerts
    .filter((a) => !symbol || a.symbol === symbol)
    .map((a) => ({
      type: "line", xref: "paper", x0: 0, x1: 1, yref: "y", y0: a.price, y1: a.price,
      line: { color: "#f59e0b", width: 1, dash: "dash" },
      layer: "above",
    } as Partial<Shape>))
  const annotations: Partial<Annotations>[] = []

  // ── Row 1: Candlestick (9-min display bars) + EMA9/21 (still per-minute) ──
  data.push({
    type: "candlestick",
    x: candleBars.map((b) => b.t), open: candleBars.map((b) => b.o), high: candleBars.map((b) => b.h),
    low: candleBars.map((b) => b.l), close: candleBars.map((b) => b.c),
    name: "Price", showlegend: false,
    increasing: { line: { color: GREEN, width: 1.3 } }, decreasing: { line: { color: RED, width: 1.3 } },
    xaxis: "x", yaxis: "y",
  } as unknown as Data)

  // EMA lines kept thinner than the candles (1.0 vs 1.7) so candlesticks
  // stay the primary price representation, but clearly visible in their
  // own right rather than faded out.
  data.push(
    { type: "scatter", mode: "lines", x: t, y: indicators.ema9, name: "EMA9",
      line: { color: "#ffab40", width: 1.0 }, opacity: 0.85, xaxis: "x", yaxis: "y" } as unknown as Data,
    { type: "scatter", mode: "lines", x: t, y: indicators.ema21, name: "EMA21",
      line: { color: "#80cbc4", width: 1.0 }, opacity: 0.85, xaxis: "x", yaxis: "y" } as unknown as Data,
  )

  // ── Session VWAP ±2σ ──────────────────────────────────────────────────
  // Magenta: distinct from EMA9 orange, EMA21 teal, both ZigZags (yellow /
  // sky blue) and every SWING_COLORS entry.
  //
  // The bands are drawn first so the VWAP line sits on top of them, and the
  // upper band fills down to the lower one via fill:"tonexty" -- which
  // requires the two to be adjacent traces in this order.
  //
  // A dataset with no volume serialises these as all-null, so the guard is on
  // the DATA, not just the prop: an explicit showVwap can't force a line that
  // has nothing behind it.
  const vwapHasData = (indicators.vwap ?? []).some((v) => v != null)
  // The last reading of each band, captured from the arrays the traces are
  // actually built from. The Legend menu prints these; recomputing them there
  // would be a second copy of the sigma maths, free to drift from this one.
  let bandUpperNow: number | null = null
  let bandLowerNow: number | null = null
  if (vwapOn && vwapHasData) {
    // Rebuild each band at the user's multiplier. devDn is stored negative,
    // matching the reference dialog's "num dev dn = -2.0" convention, so it is
    // added rather than subtracted.
    const base = indicators.vwap ?? []
    const shipped = indicators.vwap_upper ?? []
    const atDev = (mult: number) =>
      base.map((v, i) => {
        const u = shipped[i]
        if (v == null || u == null) return null
        return v + mult * ((u - v) / 2)
      })

    const upper = atDev(devUp)
    const lower = atDev(devDn)
    bandUpperNow = lastReading(upper)
    bandLowerNow = lastReading(lower)
    const hover = (label: string) => `<b>${label}</b>: %{y:.2f}<extra></extra>`
    data.push(
      { type: "scatter", mode: "lines", x: t, y: upper, name: "UpperBand",
        line: { color: vwapStyle.upper.color, width: vwapStyle.upper.width,
                dash: vwapStyle.upper.dash },
        hovertemplate: hover("UpperBand"),
        legendgroup: "vwap", xaxis: "x", yaxis: "y" } as unknown as Data,
      { type: "scatter", mode: "lines", x: t, y: lower, name: "LowerBand",
        line: { color: vwapStyle.lower.color, width: vwapStyle.lower.width,
                dash: vwapStyle.lower.dash },
        hovertemplate: hover("LowerBand"),
        legendgroup: "vwap", xaxis: "x", yaxis: "y" } as unknown as Data,
      { type: "scatter", mode: "lines", x: t, y: indicators.vwap, name: "VWAP",
        line: { color: vwapStyle.vwap.color, width: vwapStyle.vwap.width,
                dash: vwapStyle.vwap.dash },
        hovertemplate: hover("VWAP"),
        legendgroup: "vwap", xaxis: "x", yaxis: "y" } as unknown as Data,
    )
  }

  // ── Bollinger Bands (20, 2) ───────────────────────────────────────────
  // A REAL indicator, not the VWAP bands wearing a different name. These are
  // a 20-bar simple moving average with population-sigma envelopes
  // (src/analysis/indicators.py::calc_bollinger_bands); the VWAP bands above
  // are volume-weighted and reset every session. They sit at different prices
  // and they are labelled differently for that reason.
  //
  // Dashed and dimmer than VWAP so that with both on, the eye can still tell
  // which envelope is which.
  const bbHasData = (indicators.bb_middle ?? []).some((v) => v != null)
  if (bbOn && bbHasData) {
    const bbHover = (n: string) => `${n}: %{y:.2f}<extra></extra>`
    data.push(
      { type: "scatter", mode: "lines", x: t, y: indicators.bb_upper, name: "BB Upper",
        line: { color: "#8b9dc3", width: 1, dash: "dash" }, hovertemplate: bbHover("BB Upper"),
        legendgroup: "bb", xaxis: "x", yaxis: "y" } as unknown as Data,
      { type: "scatter", mode: "lines", x: t, y: indicators.bb_lower, name: "BB Lower",
        line: { color: "#8b9dc3", width: 1, dash: "dash" }, hovertemplate: bbHover("BB Lower"),
        legendgroup: "bb", xaxis: "x", yaxis: "y" } as unknown as Data,
      { type: "scatter", mode: "lines", x: t, y: indicators.bb_middle, name: "BB 20 2",
        line: { color: "#6b7fa8", width: 1.2 }, hovertemplate: bbHover("BB Basis"),
        legendgroup: "bb", xaxis: "x", yaxis: "y" } as unknown as Data,
    )
  }

  // ── Volume Profile ────────────────────────────────────────────────────
  // Drawn on its own x-axis (xaxis9) that OVERLAYS the price row rather than
  // taking a subplot column of its own. A column would cost ~15% of the chart
  // width permanently and force the three indicator rows to shrink to match,
  // or they would misalign with the candles above them. Overlaying keeps the
  // full price width and is what TradingView and thinkorswim do.
  //
  // The overlay axis is reversed, so bars grow leftward from the right edge
  // and stay out of the way of recent price action. It is capped at a third of
  // a quarter of the plot so the histogram cannot swamp the candles behind it.
  // Local recomputation, so bins / value-area% / opacity all redraw instantly.
  // Falls back to the server's profile only to decide whether volume exists at
  // all; with no volume both produce nothing.
  const vpSlices = useMemo(
    () => computeVolumeProfiles(bars, {
      timePer: vpTimePer, multiplier: vpMultiplier, maxProfiles: vpMaxProfiles,
      rowMode: vpRowMode, customRowHeight: vpRowHeight,
      bins: vpBins, valueAreaPct: vpValueArea / 100,
    }),
    [bars, vpTimePer, vpMultiplier, vpMaxProfiles, vpRowMode, vpRowHeight,
     vpBins, vpValueArea],
  )
  // The right-hand overlay only makes sense for a single whole-chart profile.
  // Per-session profiles are anchored in time instead, each inside its own
  // session's x-range, which is the only way several of them can coexist.
  const vpSingle = vpTimePer === "CHART" && vpSlices.length === 1
  const vpLocal = vpSlices.length ? vpSlices[vpSlices.length - 1].profile
                                  : { prices: [], volumes: [], poc: null, val: null,
                                      vah: null, binSize: null }
  const vpVisible = vpOn && vpShowStudy && vpSingle && vpOnExpansion && vpLocal.prices.length > 0
  if (vpVisible) {
    const vp = { ...vpLocal, bin_size: vpLocal.binSize }
    const inValueArea = (p: number) =>
      vp.val != null && vp.vah != null && p >= vp.val && p <= vp.vah
    data.push({
      type: "bar", orientation: "h",
      x: vp.volumes, y: vp.prices,
      width: vp.bin_size ?? undefined,
      // Value-area buckets are brighter; the rest recede. Same hue so the
      // profile still reads as one object.
      marker: {
        // One opacity control drives both tiers; outside-the-area buckets keep
        // a fixed fraction of it so the value area stays distinguishable at
        // any setting.
        color: vp.prices.map((p) => {
          const a = vpOpacity / 100
          return inValueArea(p)
            ? `rgba(56,189,248,${(a * 0.68).toFixed(3)})`
            : `rgba(56,189,248,${(a * 0.26).toFixed(3)})`
        }),
      },
      name: "Volume Profile",
      hovertemplate: "<b>Volume Profile</b><br>%{y:.2f}: %{x:,.0f}<extra></extra>",
      // Axis 9, not 5: the price row and four oscillator rows use axes 1 to 5.
      xaxis: "x9", yaxis: "y", showlegend: true,
    } as unknown as Data)
  }


  // Session-anchored profiles (time per profile = DAY / WEEK). Geometry lives
  // in lib/volumeProfileShapes.ts so its x-boundary handling can be tested.
  if (vpOn && vpShowStudy && !vpSingle && vpSlices.length) {
    shapes.push(...buildSessionProfileShapes(vpSlices, vpOpacity, vpShow, vpPlots))
  }

  // ── ZigZag overlay with per-swing numbering ───────────────────────────
  const zz10 = showZigzag ? zigzag.zigzag_10 : []
  const zz3 = showZigzag ? zigzag.zigzag_3 : []

  // 10-leg swing group boundaries, computed once up front -- used to draw
  // the swing rectangles further below. The 3-leg zigzag's own `swing` field
  // is its TRUE parent major swing -- computed server-side by
  // calc_nested_zigzag() (api/serializers.py), which runs the minor zigzag
  // independently within each major swing's own bar window, so containment
  // (never bleeding into the next swing) and the letter reset are already
  // guaranteed by construction. No client-side time-boundary lookup needed.
  const bySwing10 = new Map<number, ZigZagPoint[]>()
  for (const p of zz10) {
    if (!bySwing10.has(p.swing)) bySwing10.set(p.swing, [])
    bySwing10.get(p.swing)!.push(p)
  }
  const swingGroups = [...bySwing10.entries()].sort((a, b) => a[0] - b[0])

  // Every 10-leg point is ALSO a 3-leg point at the exact same price/time
  // (a major swing extreme is always also a minor one) -- that shared point
  // is already labeled by the 10-leg overlay's own circle, so it's excluded
  // here entirely (no letter, no circle) rather than drawn a second time.
  const zz10TimeSet = new Set(zz10.map((p) => p.t))
  const zz3Labelable = zz3.filter((p) => !zz10TimeSet.has(p.t))
  // Per parent swing, the ordered list of 3-leg letters inside it -- lets
  // the swing header show "3 Leg Dev (A to H)" alongside the existing
  // "(1.1 to 1.5)" range.
  const regionLettersBySwing = new Map<number, string[]>()
  for (const p of zz3Labelable) {
    if (!regionLettersBySwing.has(p.swing)) regionLettersBySwing.set(p.swing, [])
    regionLettersBySwing.get(p.swing)!.push(p.label)
  }
  const regionLetters: string[][] = swingGroups.map(([swingNum]) => regionLettersBySwing.get(swingNum) ?? [])

  if (zz3.length) {
    data.push({
      type: "scatter", mode: "lines", x: zz3.map((p) => p.t), y: zz3.map((p) => p.price),
      name: "ZigZag (3L)", line: { color: "#f0c040", width: 1.0, dash: "dot" },
      hoverinfo: "skip", xaxis: "x", yaxis: "y",
    } as unknown as Data)
    for (const [ptype, color] of [["H", "#ff6b6b"], ["L", "#69f0ae"]] as const) {
      const pts = zz3Labelable.filter((p) => p.type === ptype)
      if (pts.length) {
        data.push({
          type: "scatter", mode: "text+markers", x: pts.map((p) => p.t), y: pts.map((p) => p.price),
          marker: { symbol: "circle", size: 23, color: BG, line: { color, width: 1.6 } },
          text: pts.map((p) => p.label), textposition: "middle center",
          textfont: { color: "white", size: 10, family: "Arial" },
          showlegend: false,
          hovertemplate: `<b>${ptype === "H" ? "High" : "Low"} (3L) %{text}</b><br>%{x}<br>@ %{y:.2f}<extra></extra>`,
          xaxis: "x", yaxis: "y",
        } as unknown as Data)
      }
    }
  }

  // Hoisted out of the `if` block below so the layout/margin/title code
  // further down (which needs to reserve enough vertical room for however
  // many swing-header rows collision avoidance actually produced) can read
  // the final value. HEADER_LEVEL_HEIGHT is hoisted alongside it so the
  // title/range-selector's own upward scaling grows at the EXACT same rate
  // as the header rows themselves -- two independent literals here drifting
  // apart is exactly what caused the title-collides-with-tallest-header bug
  // this was fixed for (2026-08-02).
  let maxHeaderLevel = 0
  const HEADER_LEVEL_HEIGHT = 0.036

  if (zz10.length) {
    data.push({
      type: "scatter", mode: "lines", x: zz10.map((p) => p.t), y: zz10.map((p) => p.price),
      name: "ZigZag (10L)", line: { color: "#2196f3", width: 1.2, dash: "dot" },
      hoverinfo: "skip", xaxis: "x", yaxis: "y",
    } as unknown as Data)

    // ── Swing boundary rectangles + headers (span all 4 panels via yref="paper") ──

    const totalSpanMs = t.length > 1 ? new Date(t[t.length - 1]).getTime() - new Date(t[0]).getTime() : 0
    // Two headers overlap or not according to how far apart they are ON
    // SCREEN, which is governed by the visible window -- not by the full
    // session. Measuring against totalSpanMs was the real cause of the
    // climbing-staircase labels: the chart opens on a 2-hour window, so on a
    // full trading session 8% of the TOTAL span is wider than everything
    // actually on screen, every header "collided" with every other, and each
    // one was pushed a row higher than the last.
    const visibleSpanMs = visibleRange
      ? visibleRange.end - visibleRange.start
      : Math.min(defaultWindow, totalSpanMs || defaultWindow)

    // ── Collision avoidance for swing headers ──────────────────────────
    // Every swing gets a header (never omitted), placed at the base row by
    // default. A header only moves to a HIGHER row when it's genuinely
    // close enough in time to an already-placed header to collide with it
    // -- never as a blanket "every other swing" rule (tried and reverted:
    // that changed swing 2's treatment for no reason tied to swing 2
    // itself). This is the same proximity-based stacking pattern used
    // elsewhere in this codebase for decluttering point labels, applied
    // here to header annotations instead.
    // How close two headers' xMid positions can be (as a fraction of the
    // whole chart's visible time range) before they're considered a real
    // collision needing a row bump -- text content/format never changes,
    // only which row a header lands on. 0.03 (tuned back when short swings
    // got an abbreviated, narrower header) was too small once EVERY header
    // became full-length text (2026-08-02, full-audit): dense clusters of
    // full "Swing N (X to Y) | 3 Leg Dev (...)" headers still overlapped
    // on the same row because the threshold didn't reflect how much wider
    // full-length text actually needs. Widened to a value that keeps
    // typical full-header text clear of its neighbor at realistic chart
    // widths -- an approximation (no live text-width measurement is
    // available before Plotly renders), not a pixel-exact bound.
    // As a fraction of the VISIBLE window. A full header is roughly
    // "(9.0 to 9.1) | 3 Leg Dev (A to H)" -- about a seventh of the plot
    // width at this font size, so headers closer than that genuinely need
    // separating and anything further apart can share row 0.
    const MIN_HEADER_SPACING_FRACTION = 0.14
    const placedHeaderXs: { xMs: number; level: number }[] = []
    function placeHeaderLevel(xMs: number): number {
      const thresholdMs = visibleSpanMs * MIN_HEADER_SPACING_FRACTION
      const colliders = placedHeaderXs.filter((p) => Math.abs(p.xMs - xMs) < thresholdMs)
      // Take the LOWEST row this header can occupy without hitting a
      // neighbour -- not one above the highest collider.
      //
      // `max(collider levels) + 1` made a run of evenly-spaced swings climb
      // monotonically: swing 5 at row 0, 6 at row 1, 7 at row 2, and so on,
      // because each new header collided with the one before it and stepped
      // above it. Visually that reads as swing labels drifting further and
      // further from the chart as the number goes up -- reported as
      // inconsistent label spacing, and the reason swing 5 looked "right"
      // while 6 through 9 did not.
      //
      // A header only actually needs to clear the rows its OWN colliders sit
      // on. Once a header is far enough from row 0's occupant, row 0 is free
      // again, so a dense run settles into 0,1,0,1 instead of 0,1,2,3.
      // ...but never more than two rows deep. An unbounded search still
      // produced a staircase wherever three or more headers fell inside one
      // threshold width (swings 5, 6 and 7 landed on rows 2, 3 and 4), which
      // is the drift being reported. Two alternating rows read as a regular
      // pattern; a five-step climb reads as a bug. When every row is already
      // occupied by a collider, take the one whose nearest neighbour is
      // furthest away -- the least-bad slot rather than a brand new row.
      const MAX_HEADER_LEVELS = 2
      const taken = new Set(colliders.map((p) => p.level))
      let level = 0
      while (level < MAX_HEADER_LEVELS && taken.has(level)) level++
      if (level >= MAX_HEADER_LEVELS) {
        let bestLevel = 0
        let bestGap = -1
        for (let l = 0; l < MAX_HEADER_LEVELS; l++) {
          const onRow = colliders.filter((p) => p.level === l)
          const gap = onRow.length
            ? Math.min(...onRow.map((p) => Math.abs(p.xMs - xMs)))
            : Number.POSITIVE_INFINITY
          if (gap > bestGap) { bestGap = gap; bestLevel = l }
        }
        level = bestLevel
      }
      placedHeaderXs.push({ xMs, level })
      maxHeaderLevel = Math.max(maxHeaderLevel, level)
      return level
    }

    swingGroups.forEach(([swingNum, grp], i) => {
      const x0 = grp[0].t
      const x1 = i + 1 < swingGroups.length ? swingGroups[i + 1][1][0].t : t[t.length - 1]
      const color = SWING_COLORS[(swingNum - 1) % SWING_COLORS.length]

      shapes.push({
        type: "rect", xref: "x", yref: "paper",
        x0, x1, y0: 0, y1: 1,
        fillcolor: "rgba(0,0,0,0)",
        line: { color, width: 1.1, dash: "dot" },
        layer: "below",
      })
      const firstLabel = grp[0].label
      const lastLabel = grp[grp.length - 1].label
      const xMid = grp[Math.floor(grp.length / 2)].t
      // Every swing header uses the IDENTICAL format, font, color, and
      // alignment -- full text always, no abbreviation. The only thing that
      // ever varies is which row it sits on, when a real neighbor is too
      // close (placeHeaderLevel(), below).
      //
      // A 2-way vertical stagger was tried and reverted (made alternating
      // swings float inconsistently into the toolbar row) because it
      // staggered EVERY swing by parity, not just the ones that actually
      // collided. An arbitrary "every other swing" skip/abbreviate rule was
      // also tried and reverted, as was a proportional width-based
      // abbreviation rule (2026-08-02): both made SOME swings render a
      // shorter header than others (including swing 1 itself, once it was
      // narrow enough) -- inconsistent formatting read as a bug regardless
      // of how principled the underlying rule was. Collision avoidance is
      // now handled ENTIRELY by row placement instead: text format is never
      // the variable, so every header is always identical to swing 1's.
      const letters = regionLetters[i]
      const legPart = letters.length
        ? ` | 3 Leg Dev (${letters[0]} to ${letters[letters.length - 1]})`
        : ""
      const headerText = `<b>Swing ${swingNum}</b><br>(${firstLabel} to ${lastLabel})${legPart}`
      const headerLevel = placeHeaderLevel(new Date(xMid).getTime())
      annotations.push({
        x: xMid, y: 1.015 + headerLevel * HEADER_LEVEL_HEIGHT, xref: "x", yref: "paper", yanchor: "bottom",
        text: headerText,
        showarrow: false, font: { color, size: 10 }, align: "center",
      })
      data.push({
        type: "scatter", mode: "markers", x: [x0], y: [grp[0].price],
        marker: { symbol: "star", size: 10, color, line: { color: "white", width: 0.6 } },
        showlegend: false, hoverinfo: "skip", xaxis: "x", yaxis: "y",
      } as unknown as Data)
    })

    // ── Decimal-labeled circles on the price chart ──
    for (const [ptype, color] of [["H", RED], ["L", GREEN]] as const) {
      const pts = zz10.filter((p) => p.type === ptype)
      if (!pts.length) continue
      data.push({
        type: "scatter", mode: "text+markers",
        x: pts.map((p) => p.t), y: pts.map((p) => p.price),
        name: ptype === "H" ? "Swing High" : "Swing Low",
        marker: { symbol: "circle", size: 24, color: BG, line: { color, width: 1.8 } },
        text: pts.map((p) => p.label), textposition: "middle center",
        textfont: { color: "white", size: 10, family: "Arial" },
        hovertemplate: "<b>Swing %{text}</b><br>%{x}<br>@ %{y:.2f}<extra></extra>",
        xaxis: "x", yaxis: "y",
      } as unknown as Data)
    }

    // ── Same decimal labels mirrored on whichever indicator rows are active ──
    const byTime = new Map(t.map((ts, i) => [ts, i]))
    const nearestIdx = (ts: string) => byTime.get(ts) ?? 0
    const borderColors = zz10.map((p) => (p.type === "H" ? RED : GREEN))
    const panelValues: Record<(typeof indicatorRows)[number], (number | null)[]> = {
      rsi2: indicators.rsi2, stochrsi: indicators.stochrsi_k, rsi13: indicators.rsi13,
      mfi: indicators.mfi ?? [],
    }
    for (const name of indicatorRows) {
      const suffix = suffixOf(name)
      const vals = panelValues[name]
      data.push({
        type: "scatter", mode: "text+markers",
        x: zz10.map((p) => p.t), y: zz10.map((p) => vals[nearestIdx(p.t)]),
        marker: { size: 20, color: BG, line: { color: borderColors, width: 1.6 } },
        text: zz10.map((p) => p.label), textposition: "middle center",
        textfont: { size: 9, color: "white", family: "Arial" },
        showlegend: false, cliponaxis: false,
        hovertemplate: "<b>Swing %{text}</b><br>%{y:.1f}<extra></extra>",
        xaxis: `x${suffix}`, yaxis: `y${suffix}`,
      } as unknown as Data)
    }
  }

  // ── Trade entry / exit markers ─────────────────────────────────────────
  const barTimes = new Set(t)
  const longs = trades.filter((tr) => tr.direction === "LONG" && barTimes.has(tr.entry_time))
  const shorts = trades.filter((tr) => tr.direction === "SHORT" && barTimes.has(tr.entry_time))
  const exits = trades.filter((tr) => tr.exit_time && barTimes.has(tr.exit_time))

  if (longs.length) {
    data.push({
      type: "scatter", mode: "markers",
      x: longs.map((tr) => tr.entry_time), y: longs.map((tr) => tr.entry_price * 0.9985),
      name: "Long Entry",
      marker: { symbol: "triangle-up", size: 13, color: GREEN, line: { color: "white", width: 1 } },
      hovertemplate: "<b>LONG ENTRY</b><br>%{x}<br>@ %{y:.2f}<extra></extra>",
      xaxis: "x", yaxis: "y",
    } as unknown as Data)
  }
  if (shorts.length) {
    data.push({
      type: "scatter", mode: "markers",
      x: shorts.map((tr) => tr.entry_time), y: shorts.map((tr) => tr.entry_price * 1.0015),
      name: "Short Entry",
      marker: { symbol: "triangle-down", size: 13, color: RED, line: { color: "white", width: 1 } },
      hovertemplate: "<b>SHORT ENTRY</b><br>%{x}<br>@ %{y:.2f}<extra></extra>",
      xaxis: "x", yaxis: "y",
    } as unknown as Data)
  }
  if (exits.length) {
    const exitColors = exits.map((tr) => (tr.pnl >= 0 ? GREEN : RED))
    data.push({
      type: "scatter", mode: "markers",
      x: exits.map((tr) => tr.exit_time!), y: exits.map((tr) => tr.exit_price!),
      name: "Exit",
      marker: { symbol: "x", size: 12, color: exitColors, line: { color: exitColors, width: 2 } },
      customdata: exits.map((tr) => [`$${tr.pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, tr.direction]),
      hovertemplate: "<b>EXIT (%{customdata[1]})</b><br>%{x}<br>@ %{y:.2f}<br>P&L: %{customdata[0]}<extra></extra>",
      xaxis: "x", yaxis: "y",
    } as unknown as Data)
  }

  // ── RSI(2) / StochRSI / RSI(13) / MFI -- a trace only for a row that exists ──
  // suffixOf() on a row that is not drawn resolves to the PRICE axis, which
  // would lay an oscillator line across the candles. So every trace is guarded
  // by its row actually being in indicatorRows.
  if (indicatorRows.includes("rsi2")) {
    const rsi2Suffix = suffixOf("rsi2")
    data.push({
      type: "scatter", mode: "lines", x: t, y: indicators.rsi2, name: "RSI(2)", showlegend: false,
      line: { color: "#ce93d8", width: 1.1 }, hovertemplate: "RSI(2): %{y:.1f}<extra></extra>",
      xaxis: `x${rsi2Suffix}`, yaxis: `y${rsi2Suffix}`,
    } as unknown as Data)
  }
  if (indicatorRows.includes("stochrsi")) {
    // StochRSI's two plots, named as the reference platform names them.
    const stochRsiSuffix = suffixOf("stochrsi")
    data.push(
      { type: "scatter", mode: "lines", x: t, y: indicators.stochrsi_k, name: "FullK", showlegend: false,
        line: { color: "#4fc3f7", width: 1.1 }, hovertemplate: "FullK: %{y:.1f}<extra></extra>",
        xaxis: `x${stochRsiSuffix}`, yaxis: `y${stochRsiSuffix}` } as unknown as Data,
      { type: "scatter", mode: "lines", x: t, y: indicators.stochrsi_d, name: "FullD", showlegend: false,
        line: { color: "#f48fb1", width: 1.0, dash: "dot" }, hovertemplate: "FullD: %{y:.1f}<extra></extra>",
        xaxis: `x${stochRsiSuffix}`, yaxis: `y${stochRsiSuffix}` } as unknown as Data,
    )
  }
  if (indicatorRows.includes("rsi13")) {
    const rsi13Suffix = suffixOf("rsi13")
    data.push({
      type: "scatter", mode: "lines", x: t, y: indicators.rsi13, name: "RSI(13)", showlegend: false,
      line: { color: "#ffcc80", width: 1.1 }, hovertemplate: "RSI(13): %{y:.1f}<extra></extra>",
      xaxis: `x${rsi13Suffix}`, yaxis: `y${rsi13Suffix}`,
    } as unknown as Data)
  }
  // Money Flow Index needs volume. Without it the series is all empty and, like
  // VWAP, no line is drawn -- the row keeps its 80/20 lines and nothing else.
  const mfiHasData = (indicators.mfi ?? []).some((v) => v != null)
  if (indicatorRows.includes("mfi") && mfiHasData) {
    const mfiSuffix = suffixOf("mfi")
    data.push({
      type: "scatter", mode: "lines", x: t, y: indicators.mfi, name: "MoneyFlowIndex",
      line: { color: "#facc15", width: 1.1 }, hovertemplate: "MoneyFlowIndex: %{y:.1f}<extra></extra>",
      xaxis: `x${mfiSuffix}`, yaxis: `y${mfiSuffix}`,
    } as unknown as Data)
  }

  // Overbought/oversold reference lines, for the rows being drawn. The values
  // live in lib/oscillatorStudies.ts, which the settings panels read too, so
  // what a panel says and what the chart draws cannot disagree.
  for (const { row, value, kind } of levelLines(indicatorRows)) {
    shapes.push({
      type: "line", xref: "paper", yref: `y${suffixOf(row)}` as Shape["yref"],
      x0: 0, x1: 1, y0: value, y1: value,
      line: { color: kind === "overbought" ? RED : GREEN, dash: "dash", width: 0.8 },
    })
  }

  const hasSwingHeaders = showZigzag && zz10.length > 0
  // maxHeaderLevel (set above by placeHeaderLevel() while building swing
  // headers) is how many EXTRA rows collision avoidance actually needed --
  // 0 when no two headers were ever close enough to collide. Everything
  // below that used to assume swing headers always occupy exactly one row
  // now needs to reserve room for however many rows were really used, or a
  // stacked header would just collide with the range-selector/title instead
  // of a neighboring swing.
  const extraHeaderRows = hasSwingHeaders ? maxHeaderLevel : 0
  // The range-selector's y is relative to the price axis's own (smaller)
  // domain, while the title's y=1.05 is relative to the whole plot area --
  // so this needs a bigger raw number than the title to land at roughly the
  // same physical height (hand-tuned, not exact). Nudged up from 1.09 to
  // 1.13 to sit closer to where Plotly's native modebar (camera/zoom/pan/
  // home icons, top-right) naturally renders. Swing headers sit lower still
  // (y=1.015 + stacked rows -- see placeHeaderLevel() above) so nothing in
  // this compact top strip overlaps, even when headers stack.
  // The range-selector's y is measured against the PRICE ROW's own domain,
  // while everything else up here (title, swing headers) is measured against
  // the whole paper. Those are different units, so the old code adding a
  // paper-sized `extraHeaderRows * HEADER_LEVEL_HEIGHT` straight onto a
  // price-row y was mixing them -- the buttons drifted by the wrong amount
  // whenever headers stacked. Converting through the price row's share of
  // the paper makes one paper unit mean one paper unit for both.
  // The paper/price-row conversion that used to position Plotly's floating
  // rangeselector went with it: ChartRangeBar is a DOM strip under the plot,
  // so it needs no coordinate conversion and cannot drift when swing headers
  // stack. The comment above is kept because the same conversion would be
  // needed again by anything else that has to sit in the top margin.

  // The default window (lib/chartWindow.ts) exists because aggregation alone
  // couldn't make candles look wide on a full-day view, because "wide" is a
  // function of how many bars are visible at once, not just how much time
  // each one covers. "All" (and the other range-selector buttons) still
  // show/restore the complete range.

  // Price panel's Y-range must be computed from the bars actually inside
  // the CURRENTLY VISIBLE x-window (the user's zoom/pan via visibleRange,
  // falling back to the default 2-hour window before any interaction), NOT
  // the whole day -- using the full day's high/low here was the real reason
  // candles looked short/flat by default: the axis was scaled to fit a much
  // bigger price range than what's actually visible, so the visible candles
  // only filled a fraction of the panel's height. Tight 1.5% padding on top
  // of the CORRECT (windowed) range is what actually makes them read as
  // tall. Recomputing this per visibleRange (rather than hardcoding the
  // 2-hour window every render) is what keeps candles from being plotted
  // outside the y-axis bounds -- and therefore invisible -- once the user
  // zooms/pans to a window with a different price band.
  const priceYRange: [number, number] | undefined = bars.length
    ? (() => {
        const lastMs = new Date(bars[bars.length - 1].t).getTime()
        const windowStartMs = visibleRange ? visibleRange.start : lastMs - defaultWindow
        const windowEndMs = visibleRange ? visibleRange.end : lastMs
        const visible = bars.filter((b) => {
          const ms = new Date(b.t).getTime()
          return ms >= windowStartMs && ms <= windowEndMs
        })
        const scope = visible.length ? visible : bars
        let lo = Math.min(...scope.map((b) => b.l))
        let hi = Math.max(...scope.map((b) => b.h))
        const barLo = lo, barHi = hi

        // Overlays drawn on this panel have to be inside its range or they
        // are silently invisible -- Plotly clips rather than complains.
        //
        // Session VWAP accumulates from the session OPEN while this range is
        // built from the visible window (the last two hours by default), so
        // on a trending day the VWAP legitimately sits well outside the
        // window's high/low. That is exactly what happened when VWAP shipped:
        // all three traces were present and legended, and every one of them
        // was drawn below the floor of the axis -- range [4540.3, 4591.7] for
        // a VWAP spanning 4499.1 to 4538.2.
        const idxInWindow: number[] = []
        bars.forEach((b, i) => {
          const ms = new Date(b.t).getTime()
          if (ms >= windowStartMs && ms <= windowEndMs) idxInWindow.push(i)
        })
        const finite = (xs: (number | null | undefined)[]) =>
          xs.filter((v): v is number => typeof v === "number" && Number.isFinite(v))
        const pick = (arr?: (number | null)[]) =>
          arr ? finite((idxInWindow.length ? idxInWindow : bars.map((_, i) => i)).map((i) => arr[i])) : []

        if (vwapOn && vwapHasData) {
          // All three series count, with no cap on how far they widen the
          // axis. A capped version was tried first (bands admitted only while
          // they stayed inside twice the bars' span) and it silently dropped
          // the one that mattered: on the default synthetic ES view the three
          // series need 119.1 points against a 51-point bar span -- 2.33x --
          // so −2σ sat entirely below the floor and only two of the three
          // lines ever appeared.
          //
          // The trade-off is real: on a wide-band session the candles
          // compress to make room. That is what the reference platform does
          // too, and a band you cannot see is not worth protecting candle
          // height for. Turning VWAP off restores the tight bars-only scale.
          // Scale the shipped ±2σ envelope to whatever the user selected, or
          // widening the bands would push them straight back outside the axis.
          const baseV = pick(indicators.vwap)
          const shippedU = pick(indicators.vwap_upper)
          const sigma = baseV.map((v, i) =>
            shippedU[i] != null ? (shippedU[i] - v) / 2 : 0)
          const all = [
            ...baseV,
            ...baseV.map((v, i) => v + devUp * sigma[i]),
            ...baseV.map((v, i) => v + devDn * sigma[i]),
          ]
          if (all.length) {
            lo = Math.min(lo, ...all)
            hi = Math.max(hi, ...all)
          }
        }

        // Whatever the overlays did, the candles themselves must still fit.
        lo = Math.min(lo, barLo)
        hi = Math.max(hi, barHi)
        const pad = (hi - lo) * 0.004
        return [lo - pad, hi + pad]
      })()
    : undefined

  // Pad the x-axis range a few bars beyond the first/last candle so the
  // edge tick labels (e.g. the last time on the right) aren't clipped by
  // sitting exactly on the plot boundary. Bar timestamps are naive
  // "wall clock" strings with no timezone marker -- new Date(...) parses
  // them as local time, so the padded boundary must be re-serialized with
  // local getters too (never toISOString(), which forces UTC and would
  // shift the range by the browser's UTC offset relative to the bars).
  const xRange = (() => {
    if (t.length < 2) return undefined
    const first = new Date(t[0]).getTime()
    const last = new Date(t[t.length - 1]).getTime()
    const barMs = (last - first) / (t.length - 1)
    const pad = barMs * 3
    // Mirrors priceYRange's fallback: default 2-hour window until the user
    // zooms/pans, then follow that same visibleRange so x and y never
    // disagree about which window is showing (a later re-render -- new
    // trade data, a resize -- would otherwise snap x back to the 2-hour
    // default while y stayed at the user's wider window, stretching a still
    // 2-hour-wide slice of candles across a much taller price axis).
    const windowStart = visibleRange ? Math.max(first, visibleRange.start) : Math.max(first, last - defaultWindow)
    const windowEnd = visibleRange ? Math.min(last, visibleRange.end) : last
    return [toNaiveString(windowStart), toNaiveString(windowEnd + pad)]
  })()

  const spikeAxis = {
    showspikes: true, spikemode: "across" as const, spikesnap: "cursor" as const,
    spikethickness: 1, spikedash: "dot" as const, spikecolor: "#6b6b8a",
  }

  // Axis definitions are built per active row (price + whichever oscillator
  // rows are on) instead of hardcoded blocks, so whichever row is last takes
  // over the bottom-axis role (tick labels, automargin).
  // The row label carries the CURRENT reading, as the reference shows it:
  // "RSI (2) 32.14" rather than a bare axis name. The value is the last
  // non-null point of the series the row draws -- the same number the line
  // ends on -- and the label falls back to the bare name when the series has
  // no reading yet, rather than printing a fabricated zero.
  const lastOf = (xs?: (number | null)[]) => {
    if (!xs) return null
    for (let i = xs.length - 1; i >= 0; i--) if (xs[i] != null) return xs[i] as number
    return null
  }
  const withValue = (name: string, v: number | null, digits = 2) =>
    v == null ? name : `${name}  ${v.toFixed(digits)}`
  const kNow = lastOf(indicators.stochrsi_k)
  const dNow = lastOf(indicators.stochrsi_d)
  const rowTitles: Record<string, string> = {
    price: "Price", rsi2: "RSI(2)", stochrsi: "StochRSI", rsi13: "RSI(13)", mfi: "MFI",
  }
  /** The reading each oscillator row currently shows, for its own label. */
  const rowReadout: Record<string, string> = {
    rsi2: withValue("RSI (2)", lastOf(indicators.rsi2)),
    stochrsi: kNow == null && dNow == null
      ? "StochRSI 14 14 3 3"
      : `StochRSI 14 14 3 3   ${kNow == null ? "--" : kNow.toFixed(2)}   ${dNow == null ? "--" : dNow.toFixed(2)}`,
    rsi13: withValue("RSI (13)", lastOf(indicators.rsi13)),
    mfi: withValue("MFI (20)", lastOf(indicators.mfi)),
  }
  // Keyed on `bars`, not on `t` -- `t` is rebuilt every render, so memoising
  // against it would recompute every time and defeat the point.
  const rangebreaks = useMemo(() => computeRangebreaks(bars.map((b) => b.t)), [bars])

  // POC / VAH / VAL as horizontal levels across the price panel, matching the
  // reference platform. Solid for the point of control, dashed for the value
  // area bounds -- one is a single price, the others are a band's edges.
  const vpLevels: { key: PlotKey; value: number; label: string; style: PlotStyle }[] = []
  const vpValues: Record<PlotKey, number | null> = {
    poc: null, profileHigh: null, profileLow: null, vah: null, val: null,
  }
  if (vpVisible) {
    // ProfileHigh / ProfileLow are the outer edges of the profile's own price
    // range -- the top of the highest bucket and the bottom of the lowest.
    const half = (vpLocal.binSize ?? 0) / 2
    vpValues.poc = vpLocal.poc
    vpValues.vah = vpLocal.vah
    vpValues.val = vpLocal.val
    vpValues.profileHigh = vpLocal.prices.length ? vpLocal.prices[vpLocal.prices.length - 1] + half : null
    vpValues.profileLow = vpLocal.prices.length ? vpLocal.prices[0] - half : null
    for (const key of ["poc", "vah", "val", "profileHigh", "profileLow"] as PlotKey[]) {
      const value = vpValues[key]
      if (vpPlots[key].show && value != null) {
        vpLevels.push({ key, value, label: PLOT_LABEL[key], style: vpPlots[key] })
      }
    }
  }
  // "Show plot names": Plotly has no per-trace on-chart label, so each level
  // gets a small annotation pinned at its right-hand end -- the same thing the
  // reference platform draws beside its plots.
  if (vpShowPlotNames) {
    for (const lv of vpLevels) {
      annotations.push({
        x: 1, xref: "paper", xanchor: "right",
        y: lv.value, yref: "y", yanchor: "middle",
        text: lv.label, showarrow: false,
        font: { size: 9, color: lv.style.color },
        bgcolor: HOVER, borderpad: 2,
      } as Partial<Annotations>)
    }
  }
  // Per-plot "Show bubble": the level's price tagged on the price axis.
  for (const lv of vpLevels) {
    if (lv.style.bubble) annotations.push(bubbleAnnotation(lv.value, lv.style, vpLeftAxis ? "left" : "right"))
  }
  // Per-plot "Show title": name and value in a line at the top of the price panel.
  const vpTitleLine = vpVisible ? titleEntries(vpPlots, vpValues) : ""
  if (vpTitleLine) {
    annotations.push({
      x: 0, xref: "paper", xanchor: "left",
      y: 1, yref: "y domain", yanchor: "top",
      text: vpTitleLine, showarrow: false,
      font: { size: 10, color: "#7dd3fc" },
      bgcolor: HOVER, borderpad: 2,
    } as unknown as Partial<Annotations>)
  }

  // Each level as a trace, so it also appears in the unified tooltip the way the
  // reference panel lists these values. Draw as / Style / Width / Colour apply.
  for (const lv of vpLevels) data.push(levelTrace(lv.label, lv.value, t, lv.style))

  const rowOrder = ["price", ...indicatorRows]
  const dynamicAxes: Record<string, unknown> = {}
  rowOrder.forEach((name, idx) => {
    const suffix = axisSuffix[idx]
    const isPrice = idx === 0
    const isBottom = idx === rowOrder.length - 1
    dynamicAxes[`xaxis${suffix}`] = {
      gridcolor: GRID,
      // Every row shares the price row's x, but rangebreaks are not inherited
      // through `matches` -- each axis needs its own copy or the indicator
      // panels stay stretched over the skipped periods and drift out of
      // alignment with the candles above them.
      rangebreaks,
      ...(isPrice
        ? {
            showgrid: true,
            rangeslider: { visible: false },
            // NO Plotly rangeselector. It floated above the price row with six
            // buttons; ChartRangeBar along the bottom now carries nine, in the
            // reference's order, and writes the same visibleRange the user's
            // zoom and pan write. Two range controls on one chart would drift
            // apart the moment one set a window the other did not know about.
            range: xRange,
          }
        : { matches: "x" }),
      domain: [0, 1] as [number, number],
      anchor: `y${suffix}`,
      showticklabels: isBottom,
      // tickformat forced to time-only -- Plotly's default date-axis
      // behavior auto-inserts a one-off date label (e.g. "Jul 8, 2026") at
      // the start of the axis when ticks span less than a day, which is
      // redundant with the date already in the chart title. An explicit
      // format with no date component suppresses that bookend entirely.
      // Time only suits intraday bars, where a view spans hours. From 2h bars
      // up the default view spans weeks and every tick lands on the same
      // session open, so the ticks read "09:30 09:30 09:30" -- those carry the
      // date instead. Daily and weekly views span months to years, so theirs
      // carry the year too.
      ...(isBottom
        ? { automargin: true, tickfont: { size: 11 },
            tickformat: barStepMs(t) >= 20 * 3_600_000 ? "%b %d, %Y"
              : barStepMs(t) >= DEFAULT_WINDOW_MS ? "%b %d" : "%H:%M" }
        : {}),
      ...spikeAxis,
    }
    dynamicAxes[`yaxis${suffix}`] = {
      gridcolor: GRID, showgrid: true,
      // "Left axis" from the reference dialog. Left is Plotly's default, so
      // unticking it moves the price scale to the right-hand side.
      side: (vpLeftAxis ? "left" : "right") as "left" | "right",
      title: { text: rowTitles[name], font: { size: 9, color: INK_DIM } },
      domain: domains[idx], anchor: `x${suffix}`,
      fixedrange: !isPrice,
      // Log applies to the PRICE row only: an oscillator is already bounded
      // 0-100 and a log scale on it would be meaningless.
      ...(isPrice && logScale ? { type: "log" as const } : {}),
      // A log axis takes its range as log10 of the price, so handing it the
      // linear range would put the window in the wrong place entirely.
      range: isPrice
        ? (logScale && priceYRange
            ? [Math.log10(Math.max(1e-9, priceYRange[0])), Math.log10(Math.max(1e-9, priceYRange[1]))]
            : priceYRange)
        : [0, 100],
    }

    // THE ROW'S CURRENT READING, as the reference draws it: horizontal, at the
    // top-left inside the row. The y-axis title is rotated and cannot hold a
    // number without colliding with its neighbours, which is why this is an
    // annotation rather than part of the title.
    //
    // Anchored to THIS ROW'S OWN AXIS DOMAIN (`y<suffix> domain`), not to a
    // paper offset indexed by position -- that put every label one panel above
    // the one it described, because the domain list is not in the same order
    // as the row list. Tied to the axis, the label cannot land on the wrong
    // row however the studies are switched on and off.
    const readout = rowReadout[name]
    if (readout) {
      annotations.push({
        text: readout,
        xref: "x domain" as Annotations["xref"],
        yref: `y${suffix} domain` as Annotations["yref"],
        x: 0.004, xanchor: "left",
        y: 0.97, yanchor: "top",
        showarrow: false, align: "left",
        font: { size: 9.5, color: INK_DIM, family: "Arial" },
      })
    }
  })


  // Overlay axis for the profile. Reversed so bars extend leftward from the
  // right edge; capped so the histogram occupies at most a third of the width.
  if (vpVisible) {
    const maxVol = Math.max(...vpLocal.volumes, 1)
    dynamicAxes["xaxis9"] = {
      overlaying: "x", side: "top", anchor: "y",
      range: [maxVol * 4.6, 0],     // reversed; 4.6x cap => bars use <= ~1/4.6 width,
                                    // which keeps them clear of the right-hand price scale
      showgrid: false, zeroline: false, showticklabels: false,
      fixedrange: true,
    }
  }


  // The Plotly top margin, in pixels. It holds the range selector and the
  // ZigZag swing headers, and the indicator readout overlay is positioned
  // from it so it starts below both rather than on top of them.
  const marginTop = hasSwingHeaders ? 62 + extraHeaderRows * 21 : 38

  // THE FLOOR GROWS WITH THE STUDIES. It was a flat 420px, which is fine for
  // the price panel and three oscillators and hopeless for four: switching MFI
  // on at an 800px window squeezed every row to about 25px, and the row labels
  // -- "RSI (2) 68.00", "StochRSI 14 14 3 3 16.51 26.82" -- overlapped each
  // other into noise.
  //
  // 58px is the least a 0-100 oscillator can be and still show its three grid
  // labels without them colliding. Below the floor the container stops
  // shrinking and the page scrolls instead, which is the honest trade: a row
  // you have to scroll to is readable, a row crushed to 25px is not.
  const OSC_ROW_MIN = 58
  const PRICE_MIN = 240
  const chartMinHeight = PRICE_MIN + indicatorRows.length * OSC_ROW_MIN + marginTop + 30

  const layout: Partial<Layout> = {
    // Plotly's title defaults to yref:"container" (positioned against the
    // WHOLE figure, margins included) while the range-selector buttons
    // position against the price axis's own "paper" (just that row's
    // domain) -- two different coordinate systems, which is why matching
    // y-numbers didn't land them on the same visual row last time (title
    // ended up higher, buttons lower/colliding with the swing labels).
    // Forcing the title onto yref:"paper" too makes both reference the same
    // anchor point (top of the price row), so the same y now means the same
    // row for both.
    // title's yref:"paper" scales against the whole plotting area (all 4
    // rows combined); the range-selector's y scales against just the price
    // row's own (smaller) domain -- so the same raw y number isn't the same
    // physical offset for both. y:1.02 here vs. rangeSelectorY (1.06) for
    // the buttons is a hand-tuned attempt to land them in the same visual
    // strip; nudge these two numbers together if a screenshot shows they're
    // still offset.
    // "Show input names": the reference platform appends the study's inputs to
    // its on-chart label, e.g. VolumeProfile(AUTOMATIC, 1.0, CHART, 1, ...).
    // NO PLOTLY TITLE. ChartHeader above the plot carries the instrument, the
    // interval and the exchange, and the strategy name and run date are in the
    // status bar -- a second title stacked over the same chart was the
    // reference's one plus one, and it cost the price panel two lines of
    // height. The Volume Profile input string went with it: it is editable in
    // that study's own settings panel, which is where it belongs.
    title: { text: "" },
    paper_bgcolor: BG, plot_bgcolor: BG,
    font: { color: INK },
    // Driven by the drawing rail. "pan" until a tool is picked, which is the
    // behaviour the chart had before the rail existed.
    dragmode: dragMode, hovermode: "x unified",
    // Style for shapes drawn from here on, so a user's trend line reads as
    // theirs rather than as one of the chart's own study lines.
    //
    // Cast: `newshape` and `activeshape` are real Plotly layout keys and have
    // been since the drawing tools shipped, but they are missing from the
    // plotly.js TypeScript definitions. The cast is for the typings' gap, not
    // for a property Plotly will ignore.
    ...({
      newshape: { line: { color: "#38bdf8", width: 1.5 }, opacity: 0.9 },
      activeshape: { fillcolor: "rgba(56,189,248,0.12)" },
    } as Partial<Layout>),
    // Plotly's own NATIVE legend, on -- matches api/report/charts.py's
    // _base_layout exactly (same bgcolor/borderwidth, default position, no
    // custom overlay component). Custom-built alternatives (a floating
    // ChartLegendCard overlay, a tab-row toggle button) were both tried and
    // didn't work as well as just using what the static HTML report
    // already does successfully.
    showlegend: legendOnChart,
    // ── THE LEGEND, AND WHY IT STOPPED SITTING ON THE PRICE LADDER ────────
    //
    // It was positioned in PAPER coordinates (x: 1.055), which are a fraction
    // of the PLOT's width -- so the gap it left for the price labels grew and
    // shrank with the window. Measured at 1494x832 the y-axis ticks ended at
    // x=1029 and the legend box started at x=1031: two pixels, at that one
    // size, by luck rather than by construction.
    //
    // xref "container" measures from the edge of the FIGURE instead, so the
    // legend always occupies the same strip whatever the width, and the right
    // margin below reserves exactly that strip plus the labels' own. The two
    // numbers are declared together at LEGEND_W / AXIS_W so they cannot drift
    // apart.
    //
    // The box is also slimmer: 10px type instead of the 12px default, a
    // constant marker size so a thick trace cannot widen the column, and a
    // transparent ground now that it no longer overlaps anything it needs to
    // be legible against.
    legend: {
      bgcolor: "rgba(0,0,0,0)", borderwidth: 0,
      xref: "container", x: 1, xanchor: "right",
      yref: "paper", y: 1, yanchor: "top",
      font: { size: 10, color: INK },
      itemsizing: "constant",
      itemwidth: 30,
      tracegroupgap: 3,
    } as unknown as Partial<Plotly.Legend>,
    // t trimmed from 95 -> 88 -- less unnecessary top padding above the
    // range-selector/title strip, closer to the top edge of the chart. b
    // trimmed 32 -> 24 too -- the bottom axis now shows time-only labels
    // (no more redundant date), which need less reserved height.
    // t trimmed 94 -> 74: the range-selector no longer occupies a band of its
    // own between the modebar and the title, so that row's worth of reserved
    // space is returned to the plotting area -- which is where the indicator
    // rows get back most of the height the larger PRICE_WEIGHT took from them.
    // t trimmed again 74 -> 62 (and 23 -> 21 per stacked header row): that
    // strip is reserved space above the plot, so every pixel taken off it is
    // a pixel the candles get. Kept a modest step on purpose -- the title and
    // the swing headers are positioned as PAPER fractions, so a taller paper
    // shrinks the gap between them in real pixels, and cutting too hard here
    // is what re-creates the title-collides-with-header bug this block has
    // already been through twice.
    // SIDES FOLLOW THE AXIS. The price scale sits on the right by default now,
    // and its labels need the 50px there instead of on the left -- at r: 20
    // they were clipped to "45" and drawn on top of the volume profile.
    // THE LEGEND NEEDS ITS OWN STRIP, and only while it is on.
    //
    // This margin used to reserve the axis labels alone, on the reasoning that
    // "Plotly already shrinks the plotting area to make room for a legend
    // anchored outside it". That is true of a PAPER-referenced legend. This
    // one is xref:"container" (see the legend block below, which moved to
    // container coords so its strip stopped scaling with the window), and a
    // container-referenced legend floats over the figure -- Plotly reserves
    // nothing for it. So with the legend on, it sat straight on top of the
    // price ladder: measured -20px, i.e. a 20px overlap, which is what
    // e2e/dashboard.spec.ts catches.
    //
    // Adding LEGEND_W only when legendOnChart is true keeps the old behaviour
    // exactly when the legend is off -- which is the default and the common
    // case -- so the chart does not lose 104px of width to a legend that is
    // not being drawn.
    margin: {
      l: vpLeftAxis ? AXIS_W + (legendOnChart && vpLeftAxis ? LEGEND_W : 0) : 14,
      r: (vpLeftAxis ? 14 : AXIS_W) + (legendOnChart && !vpLeftAxis ? LEGEND_W : 0),
      t: marginTop,
      b: 18,
    },
    // No fixed height here on purpose -- the wrapping container stretches to
    // fill the available vertical space (matching the taller right-panel
    // column), and autosize + the Plot's own height:100% style pick that up.
    autosize: true,
    ...(dynamicAxes as Partial<Layout>),
    // The chart's own shapes first, the user's drawings on top, so a trend
    // line is never hidden behind a value-area band. The counts are recorded
    // here, at the one place that knows the split, for handleRelayout's slice.
    shapes: ((): Layout["shapes"] => {
      // Alert levels count as the chart's own: the user did not draw them
      // with the rail, and the eraser must not treat them as a drawing.
      const own = [...shapes, ...alertShapes]
      builtInShapeCount.current = own.length
      return [...own, ...userShapes] as Layout["shapes"]
    })(),
    annotations: ((): Layout["annotations"] => {
      builtInNoteCount.current = annotations.length
      return [...annotations, ...userNotes] as Layout["annotations"]
    })(),
  }

  /**
   * Everything currently drawn on the price panel, with its colour, the way
   * it is drawn, and its latest reading where it has one.
   *
   * Built from the same state and the same style objects that produced the
   * traces above -- the ZigZag colours, the swing-circle colours and the
   * marker shapes are the literals the traces use. A legend holding its own
   * copy of the palette is a legend that will eventually describe a colour
   * the chart stopped using.
   *
   * Only what is actually ON appears. A key listing a study you switched off
   * is a key you have to second-guess.
   */
  const legendEntries: LegendEntry[] = []
  legendEntries.push(
    { label: "EMA 9", color: "#ffab40", kind: "line",
      value: fmtPrice(lastReading(indicators.ema9)) },
    { label: "EMA 21", color: "#80cbc4", kind: "line",
      value: fmtPrice(lastReading(indicators.ema21)) },
  )
  if (vwapOn && vwapHasData) {
    legendEntries.push(
      { label: "VWAP", color: vwapStyle.vwap.color, kind: "line",
        note: `session anchored, resets ${vwapTimeframe.toLowerCase()}`,
        value: fmtPrice(lastReading(indicators.vwap)) },
      { label: `VWAP Upper +${devUp.toFixed(1)}σ`, color: vwapStyle.upper.color,
        kind: "band", value: fmtPrice(bandUpperNow) },
      { label: `VWAP Lower ${devDn.toFixed(1)}σ`, color: vwapStyle.lower.color,
        kind: "band", value: fmtPrice(bandLowerNow) },
    )
  }
  if (bbOn) {
    legendEntries.push(
      { label: "BB 20 2 basis", color: "#6b7fa8", kind: "line",
        note: "20-bar mean, 2 sigma envelope",
        value: fmtPrice(lastReading(indicators.bb_middle)) },
      { label: "BB Upper", color: "#8b9dc3", kind: "dash",
        value: fmtPrice(lastReading(indicators.bb_upper)) },
      { label: "BB Lower", color: "#8b9dc3", kind: "dash",
        value: fmtPrice(lastReading(indicators.bb_lower)) },
    )
  }
  if (vpOn) {
    legendEntries.push({ label: "Volume Profile", color: "rgb(56,189,248)", kind: "band",
                         note: "value area darker than the rest" })
  }
  if (showZigzag) {
    legendEntries.push(
      { label: "ZigZag (3L)", color: "#f0c040", kind: "dot", note: "3-leg swing structure" },
      { label: "ZigZag (10L)", color: "#2196f3", kind: "dot", note: "10-leg swing structure" },
      { label: "Swing High", color: "#ff6b6b", kind: "marker", symbol: "circle",
        note: "numbered circle at the high" },
      { label: "Swing Low", color: "#69f0ae", kind: "marker", symbol: "circle",
        note: "numbered circle at the low" },
    )
  }
  if (trades.length) {
    legendEntries.push(
      { label: "Long Entry", color: GREEN, kind: "marker", symbol: "triangle-up" },
      { label: "Exit", color: RED, kind: "marker", symbol: "x",
        note: "green when the trade won, red when it lost" },
    )
  }

  // The chart's own controls, handed to ChartHeader so they land on the
  // instrument line instead of on a row of their own. Same buttons, same
  // state, same handlers -- only the parent that draws them changed.
  const chartActions = (
    <>
            {/* "Legend": what the lines and markers MEAN, and what they read right
          now. Next to Indicators, which is what turns them on and off -- two
          different questions, two different menus. */}
      <ChartLegendMenu entries={legendEntries}
                       onChart={legendOnChart}
                       onToggleOnChart={setLegendOnChart} />

      {/* "Indicators": every study in one menu. The checkboxes to the left
                stay exactly as they are -- this is a second way to reach the same
                state, for a narrow window where the row wraps, not a replacement. */}
            <span className="relative">
              <button type="button"
                      aria-haspopup="menu" aria-expanded={indicatorMenu}
                      onClick={() => { setIndicatorMenu((v) => !v); setSaveMenu(false) }}
                      className="flex items-center gap-1 rounded border border-[color:var(--hairline-mid)]
                                 bg-[color:var(--raise-3)] px-2 py-0.5 hover:bg-[color:var(--raise-4)]">
                Indicators <ChevronDown className="h-3 w-3" aria-hidden />
              </button>
              {indicatorMenu && (
                <div role="menu"
                     className="absolute right-0 top-7 z-30 w-52 rounded-lg border border-[color:var(--hairline-mid)]
                                bg-[var(--surface-1)] py-1 shadow-xl">
                  <MenuToggle label="VWAP" checked={vwapOn} onChange={setVwapOn} />
                  <MenuToggle label="Bollinger Bands (20, 2)" checked={bbOn} onChange={setBbOn} />
                  <MenuToggle label="Volume Profile" checked={vpOn} onChange={setVpOn} />
                  {OSC_ORDER.map((key) => (
                    <MenuToggle key={key}
                                label={OSC_STUDIES[key].label}
                                checked={osc[key]}
                                disabled={!OSC_STUDIES[key].available}
                                hint={OSC_STUDIES[key].available ? undefined : OSC_STUDIES[key].pending}
                                onChange={(v) => setOsc((o) => ({ ...o, [key]: v }))} />
                  ))}
                </div>
              )}
            </span>

            {/* "Save": the two things there are to save here. Both already
                existed -- the defaults writer and Plotly's own PNG export -- and
                neither had a home outside the Volume Profile dialog. */}
            <span className="relative">
              <button type="button"
                      aria-haspopup="menu" aria-expanded={saveMenu}
                      onClick={() => { setSaveMenu((v) => !v); setIndicatorMenu(false) }}
                      className="flex items-center gap-1 rounded border border-[color:var(--hairline-mid)]
                                 bg-[color:var(--raise-3)] px-2 py-0.5 hover:bg-[color:var(--raise-4)]">
                <Save className="h-3 w-3" aria-hidden /> Save <ChevronDown className="h-3 w-3" aria-hidden />
              </button>
              {saveMenu && (
                <div role="menu"
                     className="absolute right-0 top-7 z-30 w-56 rounded-lg border border-[color:var(--hairline-mid)]
                                bg-[var(--surface-1)] py-1 shadow-xl">
                  <button type="button" role="menuitem"
                          onClick={() => { setSaveMenu(false); saveVpDefaults() }}
                          className="block w-full px-3 py-1.5 text-left hover:bg-[color:var(--raise-3)]">
                    Save chart settings as default
                  </button>
                  <button type="button" role="menuitem"
                          onClick={() => { setSaveMenu(false); downloadPng() }}
                          className="block w-full px-3 py-1.5 text-left hover:bg-[color:var(--raise-3)]">
                    Download chart as PNG
                  </button>
                </div>
              )}
            </span>

            {/* Fullscreen. The Fullscreen API on this container, so the chart
                fills the screen with its own toolbar and oscillator rows rather
                than being screenshotted. */}
            <button type="button"
                    onClick={toggleFullscreen}
                    aria-pressed={isFullscreen}
                    title={isFullscreen ? "Exit full screen" : "Full screen"}
                    className="rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-1.5 py-0.5
                               hover:bg-[color:var(--raise-4)]">
              {isFullscreen ? <Minimize className="h-3.5 w-3.5" aria-hidden />
                            : <Maximize className="h-3.5 w-3.5" aria-hidden />}
              <span className="sr-only">{isFullscreen ? "Exit full screen" : "Full screen"}</span>
            </button>
    </>
  )

  return (
    // Real height comes from ResultsPage's flex-1 min-h-0 chain (hero row ->
    // Tabs -> App.tsx's viewport-bound scroll div). minHeight must stay a
    // true floor, not a target -- raising it to 620 broke RSI(2)/RSI(13)
    // entirely: whenever the real flex-computed height came in under 620px,
    // this div was forced taller than its parent Card's actual box, and
    // since Card clips overflow, everything past the bottom of that box
    // (i.e. the two indicator rows, which render last) got sliced off
    // instead of just being small. 420 is low enough to only kick in on
    // genuinely tiny viewports.
    <div ref={containerRef}
         style={{ width: "100%", height: "100%", minHeight: chartMinHeight,
                  display: "flex", flexDirection: "column" }}>
      {/* The instrument line, the OHLC quote, and the chart controls -- one
          row, rendered here rather than by the page so that the controls can
          sit on it. */}
      <ChartHeader symbol={symbol} description={description} exchange={exchange}
                   interval={interval} bars={bars} actions={chartActions} />

      {/* VWAP controls. The gear sits beside the toggle so the settings are
          discoverable from the thing they configure, rather than buried in a
          global preferences screen. */}
      <div className="shrink-0 flex flex-wrap items-center gap-x-1.5 gap-y-1 pb-1 text-xs relative">
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input type="checkbox" checked={vwapOn}
                 onChange={(e) => setVwapOn(e.target.checked)} />
          <span>VWAP</span>
        </label>
        {/* Deliberately NOT disabled when the indicator is off.
            A gear greyed to 40% next to a bright one reads as missing rather
            than as unavailable, and clicking it did nothing at all -- which is
            exactly how the Volume Profile gear below came to be reported as
            absent. Clicking now switches the indicator on and opens its panel,
            which is what someone reaching for the settings wanted anyway. */}
        <button
          type="button"
          aria-label="VWAP settings"
          title={vwapOn ? `VWAP settings — deviation ${devDn.toFixed(1)} / +${devUp.toFixed(1)}`
                        : "Turn VWAP on and open its settings"}
          onClick={() => { if (!vwapOn) setVwapOn(true); setVwapPanelOpen(true) }}
          className="rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-1.5 py-0.5
                     hover:bg-[color:var(--raise-4)]"
        >⚙</button>

        <span className="mx-0.5 hidden wide:inline text-[color:var(--hairline-firm)]">|</span>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input type="checkbox" checked={bbOn}
                 aria-label="Show Bollinger Bands"
                 onChange={(e) => setBbOn(e.target.checked)} />
          <span>BB(20,2)</span>
        </label>

        <span className="mx-0.5 hidden wide:inline text-[color:var(--hairline-firm)]">|</span>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input type="checkbox" checked={vpOn}
                 onChange={(e) => setVpOn(e.target.checked)} />
          <span>Volume Profile</span>
        </label>
        <button
          type="button"
          aria-label="Volume Profile settings"
          title={vpOn ? `Volume Profile settings — ${vpBins} rows, value area ${vpValueArea}%`
                      : "Turn Volume Profile on and open its settings"}
          onClick={() => { if (!vpOn) setVpOn(true); setVpPanelOpen(true) }}
          className="rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-1.5 py-0.5
                     hover:bg-[color:var(--raise-4)]"
        >⚙</button>

        {/* Oscillator panels, switched on and configured the same way as VWAP
            and Volume Profile. Switching one off removes its row, handing the
            space to price and the rest. */}
        {OSC_ORDER.map((key) => {
          const info = OSC_STUDIES[key]
          return (
            <span key={key} className="flex items-center gap-1.5">
              <span className="mx-0.5 hidden wide:inline text-[color:var(--hairline-firm)]" aria-hidden>|</span>
              <label className={`flex items-center gap-1.5 ${info.available ? "cursor-pointer" : "opacity-60"}`}
                     title={info.available ? undefined : info.pending}>
                <input type="checkbox" checked={osc[key]} disabled={!info.available}
                       aria-label={`Show ${info.label}`}
                       onChange={(e) => setOsc((o) => ({ ...o, [key]: e.target.checked }))} />
                <span>{info.label}</span>
              </label>
              <button
                type="button"
                aria-label={`${info.label} settings`}
                title={info.available ? `${info.label} settings` : info.pending}
                onClick={() => {
                  // Same as the VWAP gear: reaching for the settings of a study
                  // that is off switches it on.
                  if (info.available && !osc[key]) setOsc((o) => ({ ...o, [key]: true }))
                  setOscPanel(key)
                }}
                className="rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-1.5 py-0.5
                           hover:bg-[color:var(--raise-4)]"
              >⚙</button>
            </span>
          )
        })}

        {vpPanelOpen && vpOn && (
          <div className="absolute left-52 top-7 z-20 w-80 max-h-[70vh] overflow-y-auto rounded-lg border border-[color:var(--hairline-mid)]
                          bg-[var(--surface-1)] p-3 shadow-xl space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-sm">VolumeProfile Customizing</span>
              <button type="button" className="text-muted-foreground hover:text-foreground"
                      onClick={() => setVpPanelOpen(false)} aria-label="Close">✕</button>
            </div>
            <div className="flex gap-2 border-b border-[color:var(--hairline-soft)] pb-2">
              <button type="button" onClick={saveVpDefaults} aria-label="Save as default"
                      className="rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-2 py-1
                                 hover:bg-[color:var(--raise-4)]">Save as default</button>
              <button type="button" onClick={resetVpFactory} aria-label="Reset to factory default"
                      className="rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-2 py-1
                                 hover:bg-[color:var(--raise-4)]">Reset to factory default</button>
            </div>
            {vpSavedNote && (
              <p className="text-[#7dd3fc]">{vpSavedNote}</p>
            )}

            {/* The reference dialog's single input for the value area. Both
                edges follow it, and so do the VAHigh and VALow tabs below. */}
            <label className="flex items-center gap-2">
              <span className="w-32 text-muted-foreground">show value area</span>
              <select value={showValueArea(vpPlots) ? "Yes" : "No"} aria-label="show value area"
                      onChange={(e) => setVpPlots((s) => setShowValueArea(s, e.target.value === "Yes"))}
                      className="flex-1 rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-2 py-1
                                 text-foreground">
                {["Yes", "No"].map((v) => (
                  <option key={v} value={v} className="bg-[var(--surface-1)] text-[#e6edf3]">{v}</option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-2">
              <span className="w-32 text-muted-foreground">value area percent</span>
              <input type="number" min={1} max={100} step={5} value={vpValueArea}
                     onChange={(e) => setVpValueArea(Number(e.target.value))}
                     className="flex-1 rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-2 py-1
                                text-foreground" />
            </label>
            <label className="flex items-center gap-2">
              <span className="w-32 text-muted-foreground">opacity</span>
              <input type="number" min={5} max={100} step={5} value={vpOpacity}
                     onChange={(e) => setVpOpacity(Number(e.target.value))}
                     className="flex-1 rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-2 py-1
                                text-foreground" />
            </label>
            <label className="flex items-center gap-2">
              <span className="w-32 text-muted-foreground">price per row height</span>
              <select value={vpRowMode} aria-label="price per row height mode"
                      onChange={(e) => setVpRowMode(e.target.value as RowHeightMode)}
                      className="flex-1 rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-2 py-1
                                 text-foreground">
                {["AUTOMATIC", "MANUAL"].map((m) => (
                  <option key={m} value={m} className="bg-[var(--surface-1)] text-[#e6edf3]">{m}</option>
                ))}
              </select>
            </label>
            <label className={`flex items-center gap-2 ${vpRowMode === "AUTOMATIC" ? "opacity-40" : ""}`}>
              <span className="w-32 text-muted-foreground">custom row height</span>
              <input type="number" min={0.05} step={0.25} value={vpRowHeight}
                     disabled={vpRowMode === "AUTOMATIC"}
                     onChange={(e) => setVpRowHeight(Number(e.target.value))}
                     className="flex-1 rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-2 py-1
                                text-foreground" />
            </label>
            <label className={`flex items-center gap-2 ${vpRowMode === "MANUAL" ? "opacity-40" : ""}`}>
              <span className="w-32 text-muted-foreground">rows (bins)</span>
              <input type="number" min={6} max={240} step={6} value={vpBins}
                     disabled={vpRowMode === "MANUAL"}
                     onChange={(e) => setVpBins(Number(e.target.value))}
                     className="flex-1 rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-2 py-1
                                text-foreground" />
            </label>

            <div className="pt-1 border-t border-[color:var(--hairline-soft)] space-y-2">
              <label className="flex items-center gap-2">
                <span className="w-32 text-muted-foreground">time per profile</span>
                <select value={vpTimePer} aria-label="time per profile"
                        onChange={(e) => setVpTimePer(e.target.value as TimePerProfile)}
                        className="flex-1 rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-2 py-1
                                   text-foreground">
                  {["CHART", "DAY", "WEEK"].map((m) => (
                    <option key={m} value={m} className="bg-[var(--surface-1)] text-[#e6edf3]">{m}</option>
                  ))}
                </select>
              </label>
              <label className="flex items-center gap-2">
                <span className="w-32 text-muted-foreground">multiplier</span>
                <input type="number" min={1} max={30} step={1} value={vpMultiplier}
                       onChange={(e) => setVpMultiplier(Number(e.target.value))}
                       className="flex-1 rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-2 py-1
                                  text-foreground" />
              </label>
              <label className="flex items-center gap-2">
                <span className="w-32 text-muted-foreground">profiles</span>
                <input type="number" min={1} max={1000} step={1} value={vpMaxProfiles}
                       onChange={(e) => setVpMaxProfiles(Number(e.target.value))}
                       className="flex-1 rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-2 py-1
                                  text-foreground" />
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={vpOnExpansion} aria-label="on expansion"
                       onChange={(e) => setVpOnExpansion(e.target.checked)} />
                <span>on expansion <span className="text-muted-foreground">
                  (draw the whole-chart profile in the space right of price)</span></span>
              </label>
            </div>

            <div className="space-y-1 pt-2 border-t border-[color:var(--hairline-soft)]">
              <div className="text-muted-foreground mb-1">Options</div>
              {([
                ["Show study", vpShowStudy, setVpShowStudy],
                ["Show plot names", vpShowPlotNames, setVpShowPlotNames],
                ["Show input names", vpShowInputNames, setVpShowInputNames],
                ["Left axis", vpLeftAxis, setVpLeftAxis],
              ] as [string, boolean, (v: boolean) => void][]).map(([label, val, set]) => (
                <label key={label} className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={val} aria-label={label}
                         onChange={(e) => set(e.target.checked)} />
                  <span>{label}</span>
                </label>
              ))}
            </div>

            <div className="space-y-1 pt-2 border-t border-[color:var(--hairline-soft)]">
              <div className="text-muted-foreground mb-1">Plots</div>
              <VolumeProfilePlotTabs styles={vpPlots} onChange={setVpPlot} />
            </div>

            <p className="text-muted-foreground">
              The profile is rebuilt in the browser, so every control here
              redraws immediately.
            </p>
          </div>
        )}

        {vwapPanelOpen && vwapOn && (
          <div className="absolute left-0 top-7 z-20 w-72 rounded-lg border border-[color:var(--hairline-mid)]
                          bg-[var(--surface-1)] p-3 shadow-xl space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-sm">VWAP settings</span>
              <button type="button" className="text-muted-foreground hover:text-foreground"
                      onClick={() => setVwapPanelOpen(false)} aria-label="Close">✕</button>
            </div>

            {/* PRESET BANDS. The maths already took any multiplier -- sigma is
                recovered from the shipped 2-sigma payload as (upper - vwap)/2
                and the bands are rebuilt from it, so 1 through 5 were all
                reachable before this control existed. What was missing was any
                way to KNOW that: two bare number fields labelled "num dev dn"
                and "num dev up" do not tell you the range they accept, and
                nothing on the chart said the bands were at 2.

                These are symmetric, which is what a sigma band is -- one
                distance, both sides. The two fields below still take an
                asymmetric pair for anyone who wants one, and the preset simply
                writes both at once. */}
            <div className="space-y-1">
              <span className="text-muted-foreground">deviation bands (&plusmn;&sigma;)</span>
              <div className="flex flex-wrap gap-1.5">
                {[1, 2, 3, 4, 5].map((d) => {
                  const on = devUp === d && devDn === -d
                  return (
                    <button key={d} type="button"
                            aria-pressed={on}
                            aria-label={`deviation bands plus and minus ${d} sigma`}
                            onClick={() => { setDevUp(d); setDevDn(-d) }}
                            className={`rounded border px-2 py-0.5 ${on
                              ? "border-[color:var(--primary)] bg-[color:var(--primary)]/15 text-foreground"
                              : "border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] hover:bg-[color:var(--raise-4)]"}`}>
                      {on ? "✓ " : ""}&plusmn;{d}
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <label className="space-y-1">
                <span className="text-muted-foreground">num dev dn</span>
                <input type="number" step="0.5" value={devDn}
                       onChange={(e) => setDevDn(Number(e.target.value))}
                       className="w-full rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-2 py-1
                                  text-foreground" />
              </label>
              <label className="space-y-1">
                <span className="text-muted-foreground">num dev up</span>
                <input type="number" step="0.5" value={devUp}
                       onChange={(e) => setDevUp(Number(e.target.value))}
                       className="w-full rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-2 py-1
                                  text-foreground" />
              </label>
            </div>

            <label className="flex items-center gap-2">
              <span className="w-20 text-muted-foreground">time frame</span>
              <select value={vwapTimeframe} disabled
                      className="flex-1 rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-2 py-1
                                 text-foreground disabled:opacity-60"
                      aria-label="VWAP timeframe">
                <option className="bg-[var(--surface-1)] text-[#e6edf3]" value="DAY">DAY</option>
              </select>
            </label>

            <div className="space-y-1.5">
              {([
                ["VWAP", "vwap"],
                ["UpperBand", "upper"],
                ["LowerBand", "lower"],
              ] as [string, "vwap" | "upper" | "lower"][]).map(([label, key]) => (
                <div key={key} className="flex items-center gap-2">
                  <span className="w-20 text-muted-foreground">{label}</span>
                  <input
                    type="color"
                    value={vwapStyle[key].color}
                    onChange={(e) => setVwapStyle((v) => ({
                      ...v, [key]: { ...v[key], color: e.target.value },
                    }))}
                    className="h-6 w-8 cursor-pointer rounded border border-[color:var(--hairline-mid)] bg-transparent"
                    aria-label={`${label} colour`}
                  />
                  <select
                    value={vwapStyle[key].width}
                    onChange={(e) => setVwapStyle((v) => ({
                      ...v, [key]: { ...v[key], width: Number(e.target.value) },
                    }))}
                    className="rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-1.5 py-0.5
                               text-foreground"
                    aria-label={`${label} width`}
                  >
                    {[1, 1.5, 2, 2.5, 3, 4].map((w) => (
                      <option key={w} value={w} className="bg-[var(--surface-1)] text-[#e6edf3]">
                        {w}px
                      </option>
                    ))}
                  </select>
                  <select
                    value={vwapStyle[key].dash}
                    onChange={(e) => setVwapStyle((v) => ({
                      ...v, [key]: { ...v[key], dash: e.target.value },
                    }))}
                    className="rounded border border-[color:var(--hairline-mid)] bg-[color:var(--raise-3)] px-1.5 py-0.5
                               text-foreground"
                    aria-label={`${label} style`}
                  >
                    {["solid", "dash", "dot"].map((d) => (
                      <option key={d} value={d} className="bg-[var(--surface-1)] text-[#e6edf3]">
                        {d}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>

            <p className="text-muted-foreground">
              Bands are rebuilt from the session σ already computed for this
              range, so changes redraw immediately.
            </p>
          </div>
        )}
        {oscPanel && (
          <OscillatorStudyPanel study={oscPanel} onClose={() => setOscPanel(null)}
                                className="absolute right-0 top-7 z-20" />
        )}
      </div>

      <ChartToolbar
        symbol={symbol}
        lastPrice={bars.length ? bars[bars.length - 1].c : null}
        canUndo={userShapes.length > 0 || userNotes.length > 0}
        canRedo={redoStack.length > 0}
        onUndo={undoDrawing}
        onRedo={redoDrawing}
        onSnapshot={downloadPng}
        onAlertsChanged={() => setAlertTick((n) => n + 1)}
      />

      {/* The rail sits BESIDE the plot, not over it: an overlay would cover
          the candles at the left edge, which is exactly where a trend line
          usually starts. */}
      <div className="flex-1 min-h-0 flex">
        <ChartToolRail active={drawTool} onPick={pickTool} />
        <div className="flex-1 min-w-0">
      {/* No overlay any more. The EMA / VWAP readout used to be painted over
          the plot's top-left corner permanently -- about 200x90px of the one
          region on the page where space is worth something, spent covering
          the candles it described. The same numbers are in the Legend menu on
          the header row, beside the key that says what each line is. */}
        <Plot
          data={data}
          layout={layout}
          config={{
            scrollZoom: true, displayModeBar: true,
            // No Plotly badge. The modebar keeps every button it had --
            // zoom, pan, reset, download, the axis controls -- so nothing
            // about how the chart is driven changes; only the logo goes.
            displaylogo: false,
            modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
            // NO GLOBAL `edits`. Turning on edits.shapePosition here made
            // EVERY shape draggable, including the chart's own VWAP bands and
            // value-area rectangles -- which span the plot, so a drag anywhere
            // grabbed one of them instead of panning the chart. That is what
            // e2e's "dragging the chart still pans it" caught.
            //
            // Per-shape `editable: true` gives the same result where it is
            // wanted: the drawings the rail creates carry it, the chart's own
            // shapes do not, so a user's trend line can still be dragged and
            // panning is untouched everywhere else.
            editable: false,
          }}
          style={{ width: "100%", height: "100%" }}
          useResizeHandler
          onRelayout={handleRelayout}
        />
        </div>
      </div>

      <ChartRangeBar
        firstBarMs={bars.length ? new Date(bars[0].t).getTime() : null}
        lastBarMs={bars.length ? new Date(bars[bars.length - 1].t).getTime() : null}
        activeRange={activeRange}
        logScale={logScale}
        onRange={(id, start, end) => { setVisibleRange({ start, end }); setActiveRange(id || null) }}
        onToggleLog={() => setLogScale((v) => !v)}
        onAuto={() => { setVisibleRange(null); setActiveRange(null); setLogScale(false) }}
      />
    </div>
  )
}
