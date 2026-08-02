# Elliott Wave Notation

How wave labels are computed vs. how they're displayed — and why those are
two different, deliberately decoupled layers.

## Real Elliott Wave notation is shown — numbers for motive waves, letters for corrective waves

Every Elliott Wave chart in this app — the live React tab
(`web/src/components/charts/ElliottWaveChart.tsx`) and the static HTML
report export (`api/report/report.py`) — displays the engine's own labels
essentially as-is, matching standard Elliott Wave notation
(elliottwave-forecast.com's own diagrams use the identical convention):

```
1  2  3  4  5              (a completed impulse or diagonal)
A  B  C                    (a zigzag/flat correction closing it)
A  B  C  D  E               (a triangle)
W  X  Y                     (a double three)
W  X  Y  X  Z               (a triple three)
```

Numbers `1`–`11` are reserved for motive (impulse/diagonal) waves only —
`6`–`11` are genuine continuation waves (see below), never a renumbering
trick. Corrective structures are **always** lettered, never numbered.

## Why there's a separate "engine" and "display" layer at all

`src/analysis/wave_numbering.py` (plus `complex_corrections.py` and
`diagonal_waves.py`) computes a **continuous** count across the whole
chart, and its raw output already uses this exact notation:

- A completed 5-wave impulse is followed by its closing correction,
  labeled `a`, `b`, `c` (lowercase internally).
- Combinations use `w`, `x`, `y` (double three) or `w`, `x`, `y`, `x`, `z`
  (triple three).
- Triangles use `a`, `b`, `c`, `d`, `e`.
- If price keeps making new extremes in the same direction *after* Wave 5
  completes (the trend hasn't actually reversed into a correction), the
  engine keeps labeling those points `"6"`, `"7"`, `"8"`... up to a cap of
  11 — a genuine, deliberate engineering convention so a still-extending
  trend isn't forced into an unsupportable correction label.

The **presentation layer** applies exactly one text transform to each
point's real label before it renders — uppercasing corrective letters
(`a` → `A`, ... `z` → `Z`); numeric labels pass through unchanged:

- `web/src/components/charts/ElliottWaveChart.tsx`'s `displayWave()` (live chart)
- `api/report/wave_layout.py`'s `display_wave()` (static report)

Both files also share an identical **segmentation** rule, used to group
the flat, continuous label sequence into independently-boxed/colored
structures on the chart. A new segment begins whenever:

1. The engine's own label is `"a"` or `"w"` — a fresh corrective structure
   starting (an impulse/diagonal's own `"1"` only ever appears as the
   first element of a coarser "run" — see `groupRuns`/`_group_wave_runs` —
   so it never needs to be a mid-run boundary here).
2. The label's **kind** changes from the previous point's — numeric
   digits vs. letters. An impulse's `"5"` followed by its closing
   correction's `"a"` is the impulse *ending* and a new corrective
   structure *beginning*, even though the engine keeps both in one
   continuous internal run.

The engine's raw output is never changed to accommodate display — the
transform above is the only place labels are ever touched for rendering.

(History: from 2026-07-18 through 2026-07-21, this app instead rewrote
every point's label to a plain renumbered digit regardless of its real
kind — reversed 2026-07-27 after explicit feedback that it doesn't match
real Elliott Wave notation: a corrective structure is always lettered, and
a digit-filled box titled "Correction" doesn't read as legitimate Elliott
notation at all.)

## How successive structures are told apart

Four things do this job together, identically on the live chart and the
static report:

1. **Color.** Each segment gets its own color, cycling through a fixed
   palette (`SEGMENT_COLORS`/`_EW_RUN_COLORS`), the same way
   `CandlestickChart.tsx` cycles colors per swing group. Consecutive
   segments are always different colors even when the palette wraps around.
2. **A header.** A bold, colored chip above each segment reads `"Wave N
   (1-{len})"` for a numeric (impulse/diagonal) segment, or the real
   technical name plus its own letter span for a corrective one — e.g.
   `"ABC Correction (A–C)"`, `"Triangle (A–E)"`, `"WXY Correction (W–Y)"`,
   `"Triple Three (W–Z)"`. A per-technical-type `"#N"` ordinal suffix only
   appears when that same type recurs within one structure-set, so two
   same-kind boxes stay distinguishable.
3. **A full price-range box** (live chart: full paper height; static
   report: the segment's own price extent) with a dashed border in the
   segment's own color, tiling the timeline so one box's right edge is the
   next box's left edge.
4. **Hover text** surfaces the same technical name (`"ABC Correction —
   point %{text}"` etc.) for corrective segments; numeric segments keep
   `"Wave %{text}"`.

## Every detected label is always visible

Separately from notation, both rendering layers guarantee **no label is
ever silently hidden** — a real bug found and fixed in this app's history
(see `waveLabelLayout.ts`'s and `wave_layout.py`'s module docstrings for
the full root-cause writeups). Two rules, enforced identically on both the
live chart and the static export:

1. Every wave the engine detected gets a marker and a line segment,
   always, at every zoom level, in every segment, from the first candle
   to the last.
2. When two labels would visually overlap, the lower-priority one fans
   outward (`stackIndex` / `stack_index`) instead of being deleted.

## Label sizing is uniform

Every wave label (numeric or lettered) renders at the same font size,
weight, and opacity within a structure-set (modulated only by the real
`sub` confidence signal — dimmer for `sub === 2` — and by
Global/Nested styling when both are present) — there is no separate tiered
hierarchy layered on top of that.
