# Product Requirements Document

**Product:** AutoTrader
**Owner:** WealthWise Advisors
**Version:** 1.0.0
**Status:** Released — see [RELEASE_NOTES.md](RELEASE_NOTES.md)

> [!NOTE]
> This document describes what the product is for and what it must do.
> How it is built is [Design Document.md](Design%20Document.md); the testable
> requirement statements are [Technical Requirements Document.md](Technical%20Requirements%20Document.md).

---

## 1. Problem

Retail and small-desk futures traders test strategies in one tool, watch the
market in a second, and keep records in a third. The three disagree. A
backtest says a setup is profitable; the live chart shows a different bar
count; the spreadsheet has neither. When a strategy loses money, there is no
way to tell whether the idea was wrong or the measurement was.

AutoTrader exists to make one engine answer all three questions, so that a
number seen in a backtest is the same number seen on the live tape.

## 2. Who it is for

| User | What they need |
|---|---|
| **Strategy researcher** | Run a strategy over history, see the trades on a chart, and trust that the fills are not optimistic |
| **Discretionary trader** | Watch the tape bar by bar with the same overlays the backtest used, to judge a setup before risking capital |
| **Reviewer / analyst** | Open a self-contained report of a completed run without installing Python |

This is an internal tool for a single desk. It is not a multi-tenant SaaS
product, and there is no account system, billing, or per-user permission
model — see [Non-goals](#7-non-goals).

## 3. Goals

**G1 — One engine, three modes.** Backtest, replay, and live trading share
`BaseStrategy`, `PaperBroker` and the same bar aggregation. A strategy written
once runs in all three without modification.

**G2 — Honest fills.** No look-ahead. Orders fill at the *next* bar's open with
explicit slippage, never at the signal bar's close.

**G3 — Charts that match the broker's.** Bars, VWAP and session boundaries must
agree with the platform the trader already watches, or the tool is worse than
useless — it is actively misleading.

**G4 — Reproducible results.** The same input produces the same output. A run
can be re-executed and compared.

**G5 — Nothing silently wrong.** Where the system cannot do something — a data
source is unavailable, a session window is empty, a token has expired — it says
so explicitly rather than showing a plausible but wrong number.

## 4. What it does

### 4.1 Backtesting

Run a strategy over a symbol and date range, and get back trades, an equity
curve, and performance metrics (Sharpe, Sortino, drawdown, win rate, profit
factor). Results are explorable in the browser and exportable.

Configuration covers symbol, timeframe, date range, strategy and its
parameters, starting capital, slippage, and an optional session-hours filter.

### 4.2 Market Grid (bar-by-bar replay)

Step a strategy through history one bar at a time and watch it trade, driven
over a WebSocket. Used to answer "what would I have seen at the moment this
signal fired?"

When replay reaches the live edge of the data it begins **following live** —
polling for new bars and extending the tape on its own. The rules that make
this trustworthy rather than merely animated are in
[Technical Requirements Document.md §4.3](Technical Requirements Document.md#43-follow-live).

### 4.3 Live trading

Architecturally present, deliberately not enabled. `RithmicBroker` raises
`NotImplementedError`. The `ReplayEngine.step()` interface is shaped to match
a live broker bar callback so that wiring it up is an integration task, not a
redesign.

### 4.4 Market analysis

Swing/pivot detection, candlestick and chart patterns, regime classification,
and a full Elliott Wave engine with its own rule inventory and validation
layer. Analysis is display-and-research material; it does not silently alter
strategy signals.

### 4.5 Reporting and export

A completed run exports to a self-contained HTML report that opens in any
browser with no Python or server on the recipient's machine, plus CSV, Excel,
PDF and Word.

## 5. Data sources

Four, with availability reported by real checks rather than assumption
(`GET /api/data-sources`):

| Source | Use |
|---|---|
| Synthetic | No account needed; deterministic; the default for tests and demos |
| Historical CSV | The trader's own archive |
| Schwab | Live/recent data over OAuth2 |
| Rithmic | Professional futures data, requires an account |

A source that cannot be used is reported as unavailable and disabled in the
UI, rather than failing at run time with a stack trace.

## 6. Success criteria

| # | Criterion |
|---|---|
| S1 | A strategy runs unmodified in backtest and replay and produces the same trades over the same bars |
| S2 | Bars and VWAP match the trader's reference platform for the same symbol, timeframe and session |
| S3 | No fill is ever priced using information from the bar that produced the signal |
| S4 | A report opens correctly on a machine with no project dependencies installed |
| S5 | An unavailable data source is visibly unavailable before a run is attempted |
| S6 | A deploy that did not actually replace the running build fails loudly instead of reporting success |

## 7. Non-goals

Stated so they are not mistaken for gaps:

- **Not multi-tenant.** No user accounts, no authentication on the API, no
  per-user data separation. It is expected to run on a trusted network.
- **Not a portfolio manager.** One symbol per backtest. No cross-asset
  position sizing or margin enforcement.
- **Not options-capable yet.** Contract specs and the data model are futures
  shaped. Options are planned, not implemented.
- **Not investment advice.** Research and education only.
- **Not a mobile product.** The UI targets a desktop trading screen.

## 8. Constraints

| Constraint | Consequence |
|---|---|
| **Python 3.12** | `pandas_ta` breaks on 3.14 and produces a test failure that looks real but is not. The version is not a preference |
| **Schwab refresh token lasts 7 days** | Live Schwab data needs a periodic interactive re-auth; it cannot be automated away |
| **Rithmic requires a paid account** | That data source is unavailable in CI and on machines without credentials |
| **Single-symbol engine** | Multi-symbol work is a future engine change, not a configuration flag |
| **Proprietary licence** | See [`LICENSE`](../LICENSE); third-party components retain their own terms |

## 9. Security requirements

Credentials (`config/credentials.yaml`) and Schwab tokens
(`config/schwab_tokens.json`) are gitignored and must never be committed.
The process holds broker credentials, which is why third-party error
telemetry is deliberately not installed. Suspected security problems are not
filed as public issues — see [`CONTRIBUTING.md`](../CONTRIBUTING.md) and
[SECURITY_AUDIT.md](SECURITY_AUDIT.md).

## 10. Open items

| Item | State |
|---|---|
| Live Rithmic trading | Stub. `RithmicBroker.connect()` unimplemented |
| Options support | Not started |
| Multi-symbol backtests | Not started |
| Automated Schwab re-auth | Not possible within the current Schwab OAuth model |

---

<sub>[⬅ Back to docs](README.md)</sub>
