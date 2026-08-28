// Dedicated Elliott Wave chart. Standalone by design: it does NOT import,
// extend, or parameterise CandlestickChart.tsx (SRS FE-2.2).
//
// HIERARCHICAL LABELLING
// ----------------------
// Structures are drawn as a nested tree following the classic convention:
//
//   depth 0   motive 1 2 3 4 5          corrective A B C
//   depth 1   motive (i)..(v)           corrective (a) (b) (c)
//   depth 2   motive ((1))..((5))       corrective ((a)) ((b)) ((c))
//
// The tree is derived from data the engine already produces -- a structure at
// scale k-1 whose span falls inside a leg of a structure at scale k is that
// leg's subdivision. No detection logic is touched here; this is a rendering
// join over `scale` + span, plus the parent_id/child_ids the API already
// returns.
//
// HONESTY (FE-3) IS THE CONSTRAINT THAT SHAPES THIS FILE
// ------------------------------------------------------
// Sub-wave labels appear ONLY where the engine actually detected a structure
// at a finer scale. A leg with no detected subdivision gets no invented
// (i)/(ii)/(iii) -- it is drawn plain and reported as unlabelled. A structure
// whose acceptance depends on a blocked rule (UNDECIDABLE) is drawn dashed,
// dimmed and named "(undecidable)". Nothing here fabricates a label that no
// analysis backs.

import { useMemo, useState } from "react"
import Plot from "react-plotly.js"
import type { Data, Layout, Annotations } from "plotly.js"
import type { ElliottWaveResponse, EWWave, OHLCVRecord } from "@/lib/types"
import { computeRangebreaks } from "@/lib/rangebreaks"
import { LoadingBlock } from "@/components/ui/loader"

const BG = "#14151c"
const GRID = "#1a2340"

// A native <select> inherits the app's light-on-dark text, but the popup list
// it opens is painted by the OS with its own (light) background -- so the
// options were white text on white and unreadable while open. The closed
// control looked fine, which is why it read as "the dropdown text is white".
// Both the control and the options therefore need explicit colours.
const SELECT_CLS =
  "bg-white/5 border border-white/10 rounded px-2 py-1 text-foreground"
const OPTION_CLS = "bg-[#14151c] text-[#e6edf3]"
const UP = "#2dd4bf"
const DOWN = "#f0576b"

// Three-colour scheme: motive, corrective, and the parent-degree marker.
// Deliberately distinct from the Swing/3-Leg palette (FE-2.6).
const C_MOTIVE = "#ff8c42"
const C_CORRECTIVE = "#f0576b"
const C_PARENT = "#c084fc"
const C_UNLABELLED = "#64748b"

const MOTIVE_TYPES = new Set(["impulse", "leading_diagonal", "ending_diagonal"])

const PRETTY: Record<string, string> = {
  impulse: "Impulse",
  leading_diagonal: "Leading Diagonal",
  ending_diagonal: "Ending Diagonal",
  zigzag: "Zigzag",
  flat: "Flat",
  flat_running: "Running Flat",
}

const ALPHABET: Record<number, { motive: string[]; corrective: string[] }> = {
  0: { motive: ["1", "2", "3", "4", "5"], corrective: ["A", "B", "C"] },
  1: {
    motive: ["(i)", "(ii)", "(iii)", "(iv)", "(v)"],
    corrective: ["(a)", "(b)", "(c)"],
  },
  2: {
    motive: ["((1))", "((2))", "((3))", "((4))", "((5))"],
    corrective: ["((a))", "((b))", "((c))"],
  },
}

const isMotive = (t: string | null) => !!t && MOTIVE_TYPES.has(t)

interface Node {
  s: EWWave
  legs: EWWave[]
  /** finer-scale structures found inside each leg, by leg index */
  subs: Map<number, Node[]>
  depth: number
}

interface Props {
  symbol: string
  strategyName: string
  bars: OHLCVRecord[]
  data: ElliottWaveResponse | undefined
  isLoading: boolean
  error?: unknown
  scaleFilter: number | "all"
  onScaleFilter: (s: number | "all") => void
}

export function ElliottWaveChart({
  symbol, strategyName, bars, data, isLoading, error,
  scaleFilter, onScaleFilter,
}: Props) {
  const [showUndecidable, setShowUndecidable] = useState(true)
  const [maxDepth, setMaxDepth] = useState(2)

  const built = useMemo(() => {
    if (!data || !bars.length) return null

    const byId = new Map(data.waves.map((w) => [w.id, w]))
    const structures = data.waves.filter((w) => w.structure_type !== null)
    const scales = [...new Set(structures.map((s) => s.scale))].sort((a, b) => a - b)
    const legsOf = (s: EWWave) =>
      s.child_ids.map((c) => byId.get(c)).filter(Boolean) as EWWave[]

    // ── build the hierarchy ────────────────────────────────────────────────
    // A structure at scale k-1 nested inside a leg of a structure at scale k
    // is that leg's subdivision. Span containment on the timestamps the API
    // already returns; no detection logic involved.
    // Overlapping parents are legitimate -- v1 surfaces every alternate and
    // prunes nothing (FR-2.4) -- so one finer structure can sit inside legs of
    // two different coarser structures. It must still be DRAWN once, or it
    // appears twice with two different parent labels. Each child is assigned to
    // exactly one owner: the tightest containing leg, ties broken by parent id
    // so the choice is deterministic. This is a rendering decision only; it
    // discards no analysis, and both parents remain drawn in full.
    const claims = new Map<string, { parent: string; leg: number; span: number }>()
    for (const s of structures) {
      const finer = structures.filter((x) => x.scale === s.scale - 1)
      legsOf(s).forEach((leg, i) => {
        const span = Date.parse(leg.end_t) - Date.parse(leg.start_t)
        for (const x of finer) {
          if (x.id === s.id) continue
          if (x.start_t < leg.start_t || x.end_t > leg.end_t) continue
          const cur = claims.get(x.id)
          if (!cur || span < cur.span || (span === cur.span && s.id < cur.parent)) {
            claims.set(x.id, { parent: s.id, leg: i, span })
          }
        }
      })
    }

    const nested = new Set(claims.keys())
    const subsFor = (s: EWWave): Map<number, Node[]> => {
      const out = new Map<number, Node[]>()
      for (const [childId, owner] of claims) {
        if (owner.parent !== s.id) continue
        const child = byId.get(childId)
        if (!child) continue
        const list = out.get(owner.leg) ?? []
        list.push({ s: child, legs: legsOf(child), subs: new Map(), depth: 0 })
        out.set(owner.leg, list)
      }
      return out
    }

    const withSubs = structures.map((s) => ({ s, legs: legsOf(s), subs: subsFor(s), depth: 0 }))
    const nodeById = new Map(withSubs.map((n) => [n.s.id, n]))
    // resolve one further level so depth-2 labels are possible where data allows
    for (const n of withSubs) {
      for (const [, kids] of n.subs) {
        kids.forEach((k, i) => {
          const real = nodeById.get(k.s.id)
          if (real) kids[i] = real
        })
      }
    }

    const roots = withSubs
      .filter((n) => !nested.has(n.s.id))
      .filter((n) => scaleFilter === "all" || n.s.scale === scaleFilter)
      .filter((n) => showUndecidable || n.s.state !== "undecidable")

    // ── emit traces + leader-line annotations ──────────────────────────────
    const traces: Data[] = [{
      type: "candlestick",
      x: bars.map((b) => b.t),
      open: bars.map((b) => b.o), high: bars.map((b) => b.h),
      low: bars.map((b) => b.l), close: bars.map((b) => b.c),
      increasing: { line: { color: UP } }, decreasing: { line: { color: DOWN } },
      name: "Price", showlegend: false, hoverinfo: "x+y",
    } as unknown as Data]

    const annotations: Partial<Annotations>[] = []
    const legendSeen = new Set<string>()
    let labelled = 0
    let unlabelledLegs = 0

    const emit = (node: Node, depth: number, parentLabel: string | null) => {
      const { s, legs } = node
      if (!legs.length) return
      const motive = isMotive(s.structure_type)
      const alpha = ALPHABET[Math.min(depth, 2)][motive ? "motive" : "corrective"]
      const undecided = s.state === "undecidable"
      const color = motive ? C_MOTIVE : C_CORRECTIVE
      const pretty = PRETTY[s.structure_type ?? ""] ?? s.structure_type ?? "?"
      const tier = depth === 0 ? "" : depth === 1 ? " · sub" : " · sub²"
      const legendName = `${pretty}${tier}${undecided ? " (undecidable)" : ""}`

      // the path itself
      traces.push({
        type: "scatter", mode: "lines+markers",
        x: [s.start_t, ...legs.map((l) => l.end_t)],
        y: [s.start_price, ...legs.map((l) => l.end_price)],
        line: {
          color,
          width: undecided ? 1.1 : depth === 0 ? 2.4 : 1.6,
          dash: undecided ? "dot" : "solid",
        },
        marker: {
          symbol: undecided ? "circle-open" : "diamond",
          size: depth === 0 ? 9 : 6,
          color: undecided ? color : BG,
          line: { color, width: 1.5 },
        },
        opacity: undecided ? 0.5 : 1,
        name: legendName, legendgroup: legendName,
        showlegend: !legendSeen.has(legendName),
        hovertemplate:
          `<b>${pretty}</b> — scale ${s.scale}<br>state: <b>${s.state}</b>` +
          (s.blocked_by.length ? `<br>Blocked by: ${s.blocked_by.join(", ")}` : "") +
          "<br>%{x}<br>%{y:.2f}<extra></extra>",
      } as unknown as Data)
      legendSeen.add(legendName)

      // one leader-line annotation per labelled leg -- an arrow to the pivot,
      // not a marker sitting on top of it
      legs.forEach((leg, i) => {
        const text = alpha[i] ?? ""
        if (!text) return
        const up = leg.end_price >= leg.start_price
        annotations.push({
          x: leg.end_t, y: leg.end_price, xref: "x", yref: "y",
          text: `<b>${text}</b>`,
          showarrow: true, arrowhead: 0, arrowsize: 1, arrowwidth: 1,
          arrowcolor: color, opacity: undecided ? 0.55 : 1,
          ax: 0, ay: up ? -(26 - depth * 6) : (26 - depth * 6),
          font: { color, size: depth === 0 ? 12 : 10, family: "Arial" },
          bgcolor: "rgba(20,21,28,0.72)", borderpad: 1,
        })
        labelled++

        // recurse into this leg's own subdivision, if the engine found one
        const kids = node.subs.get(i)
        if (kids && depth + 1 <= maxDepth) {
          kids.forEach((k) => emit(k, depth + 1, text))
        } else if (!kids && depth === 0) {
          unlabelledLegs++
        }
      })

      // the structure's own position within its parent, in a third colour --
      // this is the real parent relationship, not an assumed degree
      if (parentLabel) {
        annotations.push({
          x: s.end_t, y: s.end_price, xref: "x", yref: "y",
          text: `<b>${parentLabel}</b>`,
          showarrow: true, arrowhead: 0, arrowwidth: 1, arrowcolor: C_PARENT,
          ax: 22, ay: 0,
          font: { color: C_PARENT, size: 11, family: "Arial" },
          bgcolor: "rgba(20,21,28,0.72)", borderpad: 1,
        })
      }
    }

    roots.forEach((n) => emit(n, 0, null))

    return { traces, annotations, roots, scales, labelled, unlabelledLegs, nested }
  }, [data, bars, scaleFilter, showUndecidable, maxDepth])

  if (isLoading) {
    return <div className="flex items-center justify-center h-full">
      <LoadingBlock label="Running Elliott Wave analysis…" hint="Scanning impulse and corrective structures" />
    </div>
  }
  if (error) {
    return <div className="p-6 text-destructive">Elliott Wave analysis failed: {String(error)}</div>
  }
  if (!data || !built) return null

  const gated = data.counts.structures_by_state?.gated ?? 0
  const undecidable = data.counts.structures_by_state?.undecidable ?? 0

  // Open on a readable window rather than the fully-crammed "All" view. With
  // nested labelling a two-month range packs hundreds of annotations into a
  // few hundred pixels and nothing is legible. Same convention the static
  // report already uses (_DEFAULT_VIEW_BARS). The "All" range button and
  // scroll-zoom still reach everything; this only sets the FIRST render.
  const DEFAULT_VIEW_BARS = 260
  const visible = bars.length > DEFAULT_VIEW_BARS ? bars.slice(-DEFAULT_VIEW_BARS) : bars
  const initialRange =
    bars.length > DEFAULT_VIEW_BARS ? [visible[0].t, visible[visible.length - 1].t] : undefined
  // Fit y to the visible window too -- with x windowed but y auto-ranging over
  // the whole series the price action collapses into a sliver of the panel.
  let initialY: [number, number] | undefined
  if (initialRange) {
    const lo = Math.min(...visible.map((b) => b.l))
    const hi = Math.max(...visible.map((b) => b.h))
    const pad = (hi - lo) * 0.12 || 1
    initialY = [lo - pad, hi + pad]
  }

  const layout: Partial<Layout> = {
    title: {
      text: `${symbol} — ${strategyName} · Elliott Wave (engine ${data.engine_version})`,
      font: { size: 14, color: "#d4d6e4" },
    },
    paper_bgcolor: BG, plot_bgcolor: BG,
    font: { color: "#d4d6e4", size: 11 },
    dragmode: "pan", hovermode: "closest",
    margin: { l: 58, r: 12, t: 44, b: 40 },
    annotations: built.annotations,
    xaxis: {
      gridcolor: GRID, rangeslider: { visible: false }, type: "date",
      // Skip non-trading voids so waves read against continuous price
      // rather than islands separated by overnight blanks.
      rangebreaks: computeRangebreaks(bars.map((b) => b.t)),
      ...(initialRange ? { range: initialRange } : {}),
      showspikes: true, spikemode: "across", spikesnap: "cursor",
      spikethickness: 1, spikedash: "dot", spikecolor: "#6b6b8a",
      rangeselector: {
        buttons: [
          { count: 1, label: "1D", step: "day", stepmode: "backward" },
          { count: 5, label: "5D", step: "day", stepmode: "backward" },
          { count: 1, label: "1M", step: "month", stepmode: "backward" },
          { step: "all", label: "All" },
        ],
        bgcolor: BG, activecolor: "#3a3a48",
        font: { color: "#d4d6e4", size: 11 }, x: 0, y: 1.02, xanchor: "left",
      },
    },
    yaxis: initialY
      ? { gridcolor: GRID, title: { text: "Price" }, range: initialY }
      : { gridcolor: GRID, title: { text: "Price" }, autorange: true },
    legend: { bgcolor: "rgba(0,0,0,0)", borderwidth: 0, orientation: "h", y: -0.14 },
    autosize: true,
  }

  return (
    <div className="flex flex-col xl:flex-row gap-3 h-full min-h-0">
      <div className="flex-1 min-w-0 min-h-0 flex flex-col">
        <div className="shrink-0 flex flex-wrap items-center gap-3 pb-2 text-xs">
          <label className="flex items-center gap-1.5">
            <span className="text-muted-foreground">Scale</span>
            <select className={SELECT_CLS}
                    value={String(scaleFilter)}
                    onChange={(e) => onScaleFilter(e.target.value === "all" ? "all" : Number(e.target.value))}>
              <option className={OPTION_CLS} value="all">All</option>
              {built.scales.map((s) => (
                <option className={OPTION_CLS} key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-1.5">
            <span className="text-muted-foreground">Nesting</span>
            <select className={SELECT_CLS}
                    value={maxDepth} onChange={(e) => setMaxDepth(Number(e.target.value))}>
              <option className={OPTION_CLS} value={0}>Top level only</option>
              <option className={OPTION_CLS} value={1}>+ sub-waves</option>
              <option className={OPTION_CLS} value={2}>+ sub-sub-waves</option>
            </select>
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input type="checkbox" checked={showUndecidable}
                   onChange={(e) => setShowUndecidable(e.target.checked)} />
            <span>Show undecidable</span>
          </label>
          <span className="text-muted-foreground">
            <b className="text-foreground">{built.roots.length}</b> top-level ·{" "}
            <b className="text-foreground">{built.nested.size}</b> nested ·{" "}
            {built.labelled} labels
          </span>
          <span className="ml-auto flex items-center gap-3">
            <span className="inline-flex items-center gap-1" style={{ color: C_MOTIVE }}>
              ▬ motive 1-5 / (i)-(v)
            </span>
            <span className="inline-flex items-center gap-1" style={{ color: C_CORRECTIVE }}>
              ▬ corrective A-C / (a)-(c)
            </span>
            <span className="inline-flex items-center gap-1" style={{ color: C_PARENT }}>
              ▬ position in parent
            </span>
          </span>
        </div>

        <div className="flex-1 min-h-0 relative">
          <Plot data={built.traces} layout={layout}
                config={{ scrollZoom: true, displaylogo: false, displayModeBar: true,
                          modeBarButtonsToRemove: ["lasso2d", "select2d"] }}
                style={{ width: "100%", height: "100%" }} useResizeHandler />
          {/* An empty result is a legitimate outcome here, not a failure -- the
              engine declines to label what it cannot detect. Previously the
              only sign was a "0 top-level" counter in a row of controls, which
              reads as a broken chart rather than an answer. The two reasons
              for an empty chart need different responses, so they are told
              apart rather than sharing one message. */}
          {built.roots.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="pointer-events-auto max-w-md rounded-lg border border-white/10
                              bg-[#14151c]/92 px-5 py-4 text-center shadow-lg">
                {data.counts.structures === 0 ? (
                  <>
                    <p className="text-sm font-semibold text-foreground">
                      No Elliott Wave structures detected in this range
                    </p>
                    <p className="mt-1.5 text-xs text-muted-foreground leading-relaxed">
                      The engine found {data.counts.pivots} pivots but none of them formed a
                      structure that passes its rules. Nothing is labelled rather than
                      labelling something it did not detect.
                    </p>
                    <p className="mt-2 text-xs text-muted-foreground">
                      Try a longer date range or a coarser timeframe — more pivots give the
                      engine more to work with.
                    </p>
                  </>
                ) : (
                  <>
                    <p className="text-sm font-semibold text-foreground">
                      {data.counts.structures} structure
                      {data.counts.structures === 1 ? "" : "s"} detected, but hidden by the
                      current filters
                    </p>
                    <p className="mt-1.5 text-xs text-muted-foreground leading-relaxed">
                      Set <b className="text-foreground">Scale</b> to “All”
                      {!showUndecidable && <> and tick <b className="text-foreground">Show
                      undecidable</b></>} to see them.
                    </p>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      <aside className="xl:w-80 shrink-0 overflow-y-auto text-xs space-y-3 border-t xl:border-t-0 xl:border-l border-white/6 pt-3 xl:pt-0 xl:pl-3">
        {/* At-a-glance figures only. The methodology behind them -- why legs go
            unlabelled, what "undecidable" means, the scope notes and the full
            blocked-rule inventory -- is real and still reachable, but it was
            several paragraphs of standing theory next to a chart, so it now
            sits behind a closed disclosure instead of being read every time. */}
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5">
          {([
            ["Structures", String(data.counts.structures)],
            ["Pivots", String(data.counts.pivots)],
            ["Nested", String(built.nested.size)],
            ["Labels drawn", String(built.labelled)],
          ] as [string, string][]).map(([k, v]) => (
            <div key={k} className="flex justify-between border-b border-white/5 pb-1">
              <dt className="text-muted-foreground">{k}</dt>
              <dd className="font-semibold text-foreground">{v}</dd>
            </div>
          ))}
          <div className="flex justify-between border-b border-white/5 pb-1">
            <dt className="text-muted-foreground">Undecidable</dt>
            <dd className="font-semibold" style={{ color: C_UNLABELLED }}>
              {undecidable}/{gated + undecidable}
            </dd>
          </div>
          <div className="flex justify-between border-b border-white/5 pb-1">
            <dt className="text-muted-foreground">Unlabelled legs</dt>
            <dd className="font-semibold" style={{ color: C_UNLABELLED }}>
              {built.unlabelledLegs}
            </dd>
          </div>
        </dl>

        <p className="text-muted-foreground leading-relaxed">
          Partial by design — <b className="text-foreground">{data.counts.blocked_rule_ids}</b>{" "}
          reference rules can’t be evaluated, so some structures stay undecidable.
        </p>

        <details className="rounded border border-white/8 px-2 py-1.5">
          <summary className="cursor-pointer select-none font-semibold text-sm">
            How to read this
          </summary>
          <div className="mt-2 space-y-3">
            <p className="text-muted-foreground leading-relaxed">
              Sub-wave labels are drawn <b className="text-foreground">only</b> where the engine
              detected a finer-scale structure inside a parent wave.{" "}
              <b style={{ color: C_UNLABELLED }}>{built.unlabelledLegs}</b> top-level legs have no
              detected subdivision and are left unlabelled rather than given invented
              (i)/(ii)/(iii) markings.
            </p>
            <p className="text-muted-foreground leading-relaxed">
              Dashed structures are <b>undecidable</b>: they passed every gate the engine can
              evaluate, but acceptance depends on a rule the source material does not define
              precisely enough — so their sub-waves are not asserted either.
            </p>
            {data.notes.length > 0 && (
              <div>
                <h4 className="font-semibold mb-1">Scope notes</h4>
                <ul className="list-disc pl-4 space-y-1 text-muted-foreground">
                  {data.notes.map((n, i) => <li key={i}>{n}</li>)}
                </ul>
              </div>
            )}
          </div>
        </details>

        <details className="rounded border border-white/8 px-2 py-1.5">
          <summary className="cursor-pointer select-none font-semibold text-sm">
            Unevaluated rules ({data.blocked_rules.length} groups)
          </summary>
          <ul className="mt-2 space-y-1.5">
            {data.blocked_rules.map((b, i) => (
              <li key={i} className="border border-white/6 rounded p-1.5">
                <div className="font-mono text-[11px] text-amber-300">{b.oq}</div>
                <div className="text-muted-foreground">{b.rules.join(", ")}</div>
                <div className="text-muted-foreground/80 mt-0.5">{b.reason}</div>
              </li>
            ))}
          </ul>
        </details>
      </aside>
    </div>
  )
}
