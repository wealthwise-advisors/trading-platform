# 🧩 `web/src/lib`

**Pure logic, unit-tested away from React.**

The decisions live here rather than inside components, so they can be tested without
a browser, a socket or a timer. Each module has a `.test.ts` beside it — **279 tests**
across this directory.

### Why the split matters

`followLive.ts` decides *whether to poll*, *whether to resume playback* and *what the
status line should say*. Those are the rules that make live-following trustworthy,
and none of them need React to be true. Testing them here catches wording and logic
bugs that a component test would hide behind rendering.

### Files in this directory

| File | Purpose | Lines |
|---|---|---:|
| [`deviationColors.test.ts`](deviationColors.test.ts) | Tests for `deviationColors.ts`. | 468 |
| [`types.ts`](types.ts) | Mirrors api/schemas/backtest.py + api/strategy_registry.py | 467 |
| [`followLive.test.ts`](followLive.test.ts) | Tests for `followLive.ts`. | 375 |
| [`followLive.ts`](followLive.ts) | "Follow live": once the replay has caught up to the newest bar, keep asking the server for bars that have… | 260 |
| [`resample.test.ts`](resample.test.ts) | Tests for `resample.ts`. | 234 |
| [`dayRange.test.ts`](dayRange.test.ts) | Tests for `dayRange.ts`. | 221 |
| [`volumeProfile.ts`](volumeProfile.ts) | Volume Profile, computed in the browser. | 216 |
| [`deviationColors.ts`](deviationColors.ts) | Colour the VWAP deviation columns by the whole number they land on. | 191 |
| [`chartAxis.test.ts`](chartAxis.test.ts) | Tests for `chartAxis.ts`. | 145 |
| [`clock.ts`](clock.ts) | Pure clock arithmetic for the digital time field. | 140 |
| [`volumeProfileShapes.test.ts`](volumeProfileShapes.test.ts) | Tests for `volumeProfileShapes.ts`. | 122 |
| [`deviationColorSettings.test.ts`](deviationColorSettings.test.ts) | Tests for `deviationColorSettings.ts`. | 118 |
| [`resample.ts`](resample.ts) | Display-only aggregation of bars into wider buckets, purely so each candle | 112 |
| [`dayRange.ts`](dayRange.ts) | "Number of days" over the existing inclusive start/end date range. | 111 |
| [`api.ts`](api.ts) | Typed fetch client for the FastAPI backend. | 102 |
| [`nowEastern.test.ts`](nowEastern.test.ts) | Tests for `nowEastern.ts`. | 101 |
| [`bandAgreement.test.ts`](bandAgreement.test.ts) | Tests for `bandAgreement.ts`. | 96 |
| [`isoTime.test.ts`](isoTime.test.ts) | Tests for `isoTime.ts`. | 94 |
| [`rangebreaks.test.ts`](rangebreaks.test.ts) | Tests for `rangebreaks.ts`. | 88 |
| [`deviationColorSettings.ts`](deviationColorSettings.ts) | Persistence for the user's deviation-colour palettes. | 87 |
| [`volumeProfileShapes.ts`](volumeProfileShapes.ts) | Session-anchored Volume Profile geometry (time per profile = DAY / WEEK). | 80 |
| [`clock.test.ts`](clock.test.ts) | Tests for `clock.ts`. | 77 |
| [`bandAgreement.ts`](bandAgreement.ts) | Which VWAP band values agree across timeframes, to the whole number. | 67 |
| [`rangebreaks.ts`](rangebreaks.ts) | Periods a time axis should skip so bars read as one continuous series. | 57 |
| [`priceFormat.test.ts`](priceFormat.test.ts) | Tests for `priceFormat.ts`. | 56 |
| [`insights.ts`](insights.ts) | TS port of ui/components/insights.py's generate_insights()/generate_ai_insight(). | 50 |
| [`savedConfigs.ts`](savedConfigs.ts) | Named backtest configs, persisted in the browser (localStorage) -- no | 39 |
| [`isoTime.ts`](isoTime.ts) | Timestamp round-tripping for Plotly date axes. | 36 |
| [`priceFormat.ts`](priceFormat.ts) | Price display, in the same shape the reference platform prints. | 35 |
| [`utils.ts`](utils.ts) | Small shared helpers, including the `cn` class-name merger used across components. | 6 |

---

<sub>[⬅ Back to the project README](../../../README.md)</sub>
