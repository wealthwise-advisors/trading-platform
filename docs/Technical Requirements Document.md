# Software Requirements Specification

**Product:** AutoTrader
**Version:** 1.0.0
**Scope:** Platform-wide

> [!NOTE]
> This covers the platform: engines, brokers, data, API, UI.
> The Elliott Wave subsystem has its own, deeper specification in
> [ELLIOTT_WAVE.md](ELLIOTT_WAVE.md#requirements) — this document does not
> restate it.

Requirements are written to be checkable. Where a requirement is already
enforced by a test, the test file is named.

---

## 1. Definitions

| Term | Meaning |
|---|---|
| **Bar** | One OHLCV candle at the configured timeframe |
| **Closed bar** | A bar whose time window has fully elapsed |
| **Forming bar** | The current, still-changing bar |
| **Signal** | A `BUY`, `SELL` or `CLOSE` emitted by a strategy |
| **Fill** | An executed order, priced by the broker |
| **Live edge** | The most recent closed bar available from the provider |
| **Session** | The configured intraday trading window |

---

## 2. Strategy engine

**FR-1.1** A strategy shall subclass `BaseStrategy` and implement
`on_bar(bars_df, current_bar, position) -> Signal | None`.

**FR-1.2** A strategy shall implement `reset()`, clearing all internal state
so that consecutive runs cannot contaminate each other.

**FR-1.3** `on_bar` shall receive only bars at or before `current_bar`.
Providing later bars is look-ahead and is a defect.

**FR-1.4** The engine shall handle position flipping. A strategy emits intent;
it does not manage transitions between long and short.

**FR-1.5** A registered strategy shall declare `id`, `label` and a parameter
schema in `api/strategy_registry.py`. The web config form and the Market Grid
page shall both build their inputs from that registry, with no per-strategy UI
code.

*Registered at v1.0.0:* MA Crossover, RSI Mean Reversion, Breakout (Donchian),
RSI Divergence, Regime Adaptive.

---

## 3. Execution and fills

**FR-2.1** A market order shall fill at the **next** bar's open, never the
signal bar's close.

**FR-2.2** A fill price shall include slippage of
`slippage_ticks × tick_size`, applied against the trade direction.

**FR-2.3** A limit order shall fill only if the bar's range reaches the limit
price — `low ≤ limit` to buy, `high ≥ limit` to sell.

**FR-2.4** A stop order shall trigger when price crosses the stop level.

**FR-2.5** Contract economics — tick size, tick value, point value, margins —
shall come from configuration, not from constants embedded in strategy code.

**FR-2.6** `RithmicBroker` shall raise rather than silently simulate. A broker
that cannot trade must never appear to have traded.

> [!IMPORTANT]
> FR-2.1 is the single most consequential requirement in this document.
> Filling at the signal bar's close makes almost any strategy look
> profitable, and the resulting numbers are indistinguishable from real
> ones without reading the fill code.

---

## 4. Replay and follow-live

**FR-3.1** `ReplayEngine.load(df)` shall preload bars; `step()` shall process
exactly one bar and return a frame snapshot.

**FR-3.2** Replay shall be drivable over a WebSocket at `/api/replay/{id}`.

**FR-3.3** `get_results()` shall build a `BacktestResults` equivalent to the
batch engine's for the same bars — the two engines shall not disagree.

### 4.3 Follow-live

On reaching the live edge, replay begins following live. These rules are what
separate it from an animation:

**FR-3.4 — Only closed bars.** A bar polled mid-window is still moving.
Showing it puts a number on screen that later changes, so the tape waits for
the close.

**FR-3.5 — Never silent.** If polling fails, the UI says so. It does not
display a stale tape as though it were current.

**FR-3.6 — A pause is respected.** Following live never resumes on its own
after the user pauses.

**FR-3.7 — The gap is named.** If bars are missing between the last shown bar
and the newest, the gap is reported rather than closed by drawing a line
across it.

*Covered by* `tests/test_replay_follow_live.py`, `test_follow_live_matrix.py`,
`test_replay_extend.py`.

---

## 5. Data

**FR-4.1** Every provider shall implement the `DataProvider` interface and
return a uniform OHLCV frame regardless of upstream shape.

**FR-4.2** `GET /api/data-sources` shall report availability from a real
check — import success, credential presence, token validity — not from a
static list.

**FR-4.3** A provider that cannot serve a request shall fail with a message
naming the cause. Returning an empty frame that reads as "no trades" is a
defect.

**FR-4.4** Coarser timeframes shall be resampled from finer source bars, and
the aggregation shall be shared with the live path so that a 5-minute bar is
built identically in both.

**FR-4.5** Schwab access tokens shall refresh automatically. The 7-day refresh
token shall surface its expiry in the UI, since only an interactive sign-in
can renew it.

**FR-4.6** Requests to a provider with range limits shall be chunked to stay
within them.

*Covered by* `tests/test_provider_timeframes.py`,
`test_api_provider_errors.py`, `test_symbol_universe.py`,
`test_schwab_redirect_parsing.py`.

---

## 6. Analysis

**FR-5.1** `src/analysis/` shall not import from `api/`. The dependency runs
one way only.

**FR-5.2** Pivot detection shall require `left`/`right` confirming bars on
both sides. A backtest shall act on `confirm_index`, never `index` — using
`index` is look-ahead.

**FR-5.3** Swing filtering shall evaluate each candidate against *local*
volatility, so a genuine pivot in a quiet stretch is not erased by an
unrelated volatile stretch elsewhere in the series.

**FR-5.4** Indicator output shall match the reference platform for the same
inputs, validated across multiple timeframes and dates.

**FR-5.5** The live chart and the exported report shall produce identical
swing and label data for identical input.

*Covered by* `tests/test_indicator_correctness.py`,
`test_swing_zigzag_regression.py`, `test_vwap_bands.py`,
`test_reference_platform_parity.py`.

> [!CAUTION]
> `test_swing_zigzag_regression.py` is a confirmed baseline, not a
> convenience. A failure there means behaviour that was verified against
> real data has changed. Treat it as "did I mean to do this", never as
> "update the expected values".

---

## 7. Sessions

**FR-6.1** A session filter shall accept a start and end time and drop bars
outside it after loading, before the strategy runs.

**FR-6.2** Providers shall load the full day; trimming is the engine's job, so
that changing session hours does not require re-downloading data.

**FR-6.3** If a session window leaves no bars, the response shall say so and
report how many bars existed before filtering.

> [!TIP]
> A VWAP that disagrees with another platform is usually the session
> anchor, not an indicator bug. Check the session window before treating
> it as a defect.

---

## 8. API

**FR-7.1** All routes shall mount under `/api`.

**FR-7.2** `GET /api/health` shall return liveness and back the container
healthcheck.

**FR-7.3** `GET /api/version` shall return the running version and commit.

**FR-7.4** Invalid input shall return `400` with a message describing what is
wrong, without exposing internal paths or configuration.

**FR-7.5** OpenAPI documentation shall be generated from the route signatures,
not maintained separately.

---

## 9. User interface

**FR-8.1** The UI shall present Backtest and Market Grid as distinct pages.

**FR-8.2** Strategy parameter inputs shall be generated from the registry
schema.

**FR-8.3** The chart shall render price with EMA, ZigZag/swing overlays and
trade markers, with indicator sub-panels beneath.

**FR-8.4** Schwab authentication state and refresh-token expiry shall be
visible, with re-authentication reachable from the UI.

**FR-8.5** A run in progress shall be distinguishable from a failed one.

Interaction and visual detail: [UI_UX.md](UI_UX.md).

---

## 10. Non-functional requirements

### 10.1 Correctness
**NFR-1.1** Identical input shall produce identical output; synthetic data
shall be seeded.
**NFR-1.2** Analysis shall be validated across multiple timeframes and dates
before being considered correct — a single passing chart is not evidence.

### 10.2 Security
**NFR-2.1** Credentials and tokens shall never enter version control.
**NFR-2.2** No third-party error-reporting service shall receive process data,
because the process holds broker credentials.
**NFR-2.3** Dependencies shall be CVE-scanned in CI (`pip-audit`, `bandit`).

### 10.3 Portability
**NFR-3.1** Python 3.12 is required. `pandas_ta` fails on 3.14 in a way that
resembles a genuine test failure.
**NFR-3.2** Paths shall use `pathlib`; the code shall not assume Windows.
**NFR-3.3** An exported report shall not require the recipient to install
anything.

### 10.4 Quality gates
**NFR-4.1** CI shall run lint, type check, unit tests, security audit,
frontend tests and a package build. All must pass before merge.
**NFR-4.2** `ruff check .` shall pass. It is enforced locally by a pre-commit
hook running the identical command against the identical config.
**NFR-4.3** A deploy shall assert that the commit answering on port 80 is the
one just built, and fail if it is not.

---

## 11. Traceability

| Area | Requirements | Tests |
|---|---|---|
| Engine and fills | FR-1.x, FR-2.x | `test_engine.py` |
| Replay / follow-live | FR-3.x | `test_replay_*.py`, `test_follow_live_matrix.py`, `test_multi_replay.py` |
| Data providers | FR-4.x | `test_provider_timeframes.py`, `test_api_provider_errors.py`, `test_symbol_universe.py` |
| Analysis | FR-5.x | `test_indicator_correctness.py`, `test_swing_zigzag_regression.py`, `test_vwap_bands.py` |
| Sessions | FR-6.x | `test_replay_session_message.py` |
| Schwab auth | FR-4.5 | `test_schwab_redirect_parsing.py` |

Run the suite with `pytest tests/ -v`; it is the authoritative count, not any
number written in a document.

---

<sub>[⬅ Back to docs](README.md)</sub>
