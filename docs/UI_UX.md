# UI / UX

**Surface:** `web/` — React 19 + TypeScript + Vite + Tailwind + shadcn/ui
**Audience:** anyone changing the interface

> [!NOTE]
> This describes how the interface behaves and why. Component APIs live in
> the code; requirements live in [SRS.md §9](SRS.md#9-user-interface).

---

## 1. Who is looking at this

One trader, on a desktop screen, often with the broker's own platform open
beside it. That single fact drives most of what follows:

- **Comparison is constant.** If a bar or a VWAP value disagrees with the
  other screen, the user believes the other screen. Visual fidelity to the
  reference platform is not polish, it is correctness.
- **The screen is watched, not visited.** A live tape is looked at for long
  stretches, so anything that moves permanently becomes an irritant.
- **Mistakes are expensive.** An ambiguous state — is this stale? did that
  save? — costs more than an extra label would.

There is no mobile target. Layouts assume a wide viewport.

---

## 2. Structure

```
App shell
├── header            brand, clock, page switch
├── Backtest          configure a run, then read its results
└── Market Grid       set up a replay, then watch the tape
```

`web/src/features/` holds `backtest/`, `replay/` and `export/`. Shared pieces
live in `web/src/components/`: `ui/` (shadcn primitives), `charts/`, `cards/`,
`tables/`, `motion/`.

> [!NOTE]
> The page is labelled **Market Grid** in the interface; the code, the
> router and the engine all still say `replay`. That is deliberate — the
> rename was a display change only, and renaming the API would have broken
> stored URLs and the WebSocket contract.

---

## 3. The two pages

### 3.1 Backtest

A configuration form and a results view. The form is generated from the
strategy registry (`GET /api/strategies`), so adding a strategy adds its
inputs with no UI work.

Results show metrics, the equity curve, a trade table, and the chart. Export
is available once a run completes.

### 3.2 Market Grid

Setup is a small number of numbered steps rather than one long form, because
a replay has more decisions than a backtest and an undifferentiated wall of
inputs hides which ones matter.

Instrument, source and strategy are chosen through searchable pickers rather
than plain `<select>` elements — the symbol universe is long enough that
scanning it is slower than typing.

A summary panel reflects the current configuration continuously, so the state
about to be committed is visible before it is committed.

---

## 4. The chart

`web/src/components/charts/CandlestickChart.tsx` (react-plotly.js). Four
stacked rows:

| Row | Height | Content |
|---|---|---|
| 1 | 55% | Candles, EMA(9), EMA(21), ZigZag overlay, trade markers |
| 2 | 15% | RSI(2), with threshold lines |
| 3 | 15% | Stochastic %K/%D |
| 4 | 15% | RSI(13) |

The exported HTML report uses the same layout from `api/report/charts.py`.
The two are kept in step deliberately: a report that looks different from the
screen it came from cannot be checked against it.

ZigZag is display only. Red marks swing highs, green marks swing lows, and
neither changes a strategy signal.

---

## 5. Motion

Animation here is weighted by **how often a surface is seen**:

| Surface | Motion | Why |
|---|---|---|
| Setup screens | Expressive — reveals, staggered entrances, shared-element transitions | Seen briefly, a few times a session. Motion helps orient |
| Live tape and tables | Effectively none | Watched continuously. Motion becomes noise, then irritation |
| Page transitions | Opacity only | See the constraint below |

Implemented with Framer Motion; shared primitives are in
`web/src/components/motion/`.

> [!CAUTION]
> The page transition animates **opacity only**, and the transition class
> sits on the existing scroll container rather than a new wrapper. Both
> constraints are load-bearing:
>
> - A `transform` on a scroll container breaks `position: sticky` inside it.
> - `ResultsPage`'s root is `h-full` and needs a parent with a resolved
>   height. An extra wrapper `div` has `auto` height, so `h-full` collapses
>   to content, the chart loses its `flex-1` chain, and a large empty gap
>   opens beneath it.
>
> This was found by breaking it. Re-test the chart's height if you touch
> that element.

---

## 6. State

| Concern | Mechanism |
|---|---|
| Backtest configuration | Zustand store |
| Server data | TanStack Query |
| Replay stream | WebSocket, held by the replay feature |
| Local component state | `useState` |

Server data is not copied into the global store. One owner per piece of state
avoids the two disagreeing.

---

## 7. Making state legible

The interface has to distinguish four things that look alike if nobody works
at it: *running*, *finished*, *failed*, and *stale*.

- **Following live** is labelled while it is happening, so a still tape reads
  as "no new closed bar", not "frozen".
- **A poll failure is shown.** The tape never presents old data as current.
- **A named gap** beats a line drawn across missing bars.
- **An unavailable data source is disabled before selection**, with the
  reason, rather than failing after a run is submitted.
- **Schwab token expiry is displayed** in the sidebar widget, because only an
  interactive sign-in can renew the 7-day refresh token and the user needs
  warning before it lapses.

---

## 8. Visual system

Tokens are CSS custom properties in `web/src/index.css`, consumed through
Tailwind and shadcn/ui — `--background`, `--foreground`, `--card`, `--border`,
`--accent`, `--destructive` and their pairs. Components read tokens; they do
not hard-code colour.

Financial convention is followed without exception: **green is up, red is
down**, in the chart, the trade table and the metrics. Reusing those two
colours for anything else on a trading screen is a bug, not a style choice.

Numbers are tabular-aligned so columns compare vertically. Prices carry the
instrument's real tick precision rather than a generic two decimals.

---

## 9. Accessibility

- Every control reachable by keyboard; focus rings are never removed.
- Colour is never the only carrier of meaning — a red cell also has a sign or
  a label.
- Radix primitives (via shadcn/ui) supply roles and focus management for
  dialogs, menus and pickers.
- Icon-only buttons carry accessible labels.

---

## 10. Conventions for new UI

1. **Read the tokens.** No literal hex in a component.
2. **Generate inputs from schemas** where a registry exists.
3. **Justify motion in one sentence** — hierarchy, feedback, sequence, or
   state change. If the sentence is "it looks nice", leave it out, and if the
   surface is watched continuously, leave it out anyway.
4. **Name the failure state** before building the success state.
5. **Match the report.** A chart change that makes the screen and the exported
   report differ is incomplete until both move.
6. **Test the chart's height** after touching any layout ancestor — see §5.

---

<sub>[⬅ Back to docs](README.md)</sub>
