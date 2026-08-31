# Developer Guide

Working on the codebase: setup, the workflows you will actually repeat, and
the traps that have already cost someone a morning.

## Dev setup

```bash
pip install -e ".[dev]"
cd web && npm install
```

Run both services:

```bash
uvicorn api.main:app --reload --port 8000
cd web && npm run dev   # separate terminal, port 5173, proxies /api/* to 8000
```

Enable the lint hook once per clone:

```bash
git config core.hooksPath .githooks
```

> [!CAUTION]
> **Use Python 3.12.** On Windows that means `py -3.12`, not `python` or
> `py -3`. On 3.14 `pandas_ta` breaks and produces a test failure that
> looks like a real regression in your change. This is a hard requirement,
> not a preference.

> [!TIP]
> Open `http://localhost:5173`, not `127.0.0.1:5173`. Vite binds to
> `localhost`, and the proxy behaves differently through the other host.

## Repository map

| Path | Contains |
|---|---|
| `src/` | The engine. No HTTP, no React, no framework |
| `api/` | FastAPI service, routers, schemas, report generation |
| `web/` | React frontend |
| `tests/` | Test suite |
| `scripts/` | CLI runners and data downloaders |
| `docs/` | This directory |
| `config/` | Settings and (gitignored) credentials |

The one structural rule: **`src/` never imports from `api/` or `web/`.** See
[Design Document.md](Design Document.md#the-dependency-rule) for why.

## Writing a new strategy

1. Subclass `BaseStrategy` in `src/strategies/`:

```python
from src.strategies.base_strategy import BaseStrategy, Signal, SignalType

class MyStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="MyStrategy")

    def reset(self):
        pass  # clear any indicator state between runs

    def on_bar(self, bars_df, current_bar, position):
        if len(bars_df) < 20:
            return None
        # ... your logic ...
        return Signal(
            signal_type=SignalType.BUY,
            strategy_name=self.name,
            timestamp=current_bar.timestamp,
            price=current_bar.close,
            reason="Your reason here",
        )
```

2. Register it in `src/strategies/__init__.py`.
3. Add it to `api/strategy_registry.py`'s `STRATEGIES` list (id, label,
   param schema) — the React config form and Live Replay page both read
   from that registry automatically, no per-file UI wiring needed.

The engine handles position flipping automatically from BUY/SELL/CLOSE
signals; see `src/broker/paper_broker.py` for the fill model (next-bar-open,
slippage in ticks).

> [!IMPORTANT]
> Implement `reset()` properly. Without it, indicator state survives into
> the next run and the second backtest of a session silently differs from
> the first — a bug that reproduces only when you run twice.

Two rules to hold on to while writing strategy logic:

- **Never look ahead.** `on_bar` sees bars up to `current_bar` and no
  further. If you use swings, act on `confirm_index`, never `index`.
- **Do not price your own fills.** Emit intent and let `PaperBroker` fill at
  the next open. A strategy that computes its own entry price at the signal
  bar's close will look excellent and be worthless.

## Adding a symbol

Add its spec in three places, or it will half-work:

1. `config/settings.yaml` under `contracts:` — tick size, tick value, point
   value, margins.
2. `api/deps.py`'s `CONTRACT_SPECS`.
3. `scripts/run_backtest.py`'s `CONTRACT_SPECS`.

For futures, also confirm the exchange mapping in
`src/data/rithmic_provider.py` (CME, NYMEX, COMEX, CBOT).

## Running tests

```bash
pytest tests/ -v
```

Useful narrowings:

```bash
pytest tests/test_engine.py -v            # one file
pytest tests/ -k follow_live -v           # one behaviour
pytest tests/ -x                          # stop at first failure
cd web && npx vitest run                  # frontend
```

> [!CAUTION]
> Some suites are **confirmed baselines**, not ordinary assertions —
> `test_swing_zigzag_regression.py`, `test_indicator_correctness.py`,
> `test_reference_platform_parity.py`. Their expected values were verified
> against real backtests and a reference trading platform.
>
> A failure there means *"did I mean to change this?"*. It does not mean
> "update the expected values to match the new output". Re-baselining
> silently throws away the verification that made those numbers worth
> having.

## Validating analysis changes

Charts are the easiest place in this codebase to be confidently wrong. Before
calling an indicator or overlay fixed:

1. Check **multiple timeframes** — bugs that only appear above 1m are common.
2. Check **multiple dates**, including a quiet day and a volatile one.
3. Compare against the reference platform to a **whole-number tolerance**.
4. Confirm the **live chart and the exported report agree**. They share
   layout deliberately; if they disagree, one of them is wrong.

> [!TIP]
> A VWAP or band that disagrees with another platform is far more often
> the **session anchor** than an indicator bug. Check the session window
> before you start editing the maths.

## Seeing the architecture

[CodeFlow](https://github.com/braedonsaunders/codeflow) turns this repository
into an interactive dependency map -- which file imports which, and what breaks
if you change one. Useful for the question `Design Document.md` answers in prose
but cannot answer for a specific file: *what actually depends on this?*

```bash
npx -y github:braedonsaunders/codeflow .
```

Opens on <http://127.0.0.1:4173>, watches the folder, and re-reads on save.

> [!WARNING]
> **Use the `github:` form, not `npx codeflow`.** There is an unrelated package
> published on npm under the bare name `codeflow`, pointing at codeflow.co.
> `npx codeflow` installs that one instead, which is not what you want and not
> what this section is about.

**Nothing is vendored, and nothing should be.** It is a tool you point at a
codebase, not a dependency of one -- the repository is ~48 MB and its UI is a
single 12,000-line `index.html`. Adding it to `package.json` would put all of
that in every clone and every Docker build to serve a question asked
occasionally.

Verified before recommending it: MIT licensed, and the local mode reads files
and serves on 127.0.0.1 only. It calls `api.github.com` in one place, reached
solely by the paste-a-public-URL mode in the browser -- not by the CLI that
reads this repository. Your code stays on the machine.

---

## Code quality tools

```bash
ruff check .        # lint (config in pyproject.toml's [tool.ruff])
mypy src/analysis    # type check (informational on src/analysis -- see RELEASE.md#audit)
vulture src api      # dead-code scan
bandit -r src api -ll   # security scan
pip-audit             # dependency CVE scan
black .                # formatter
```

`src/data/schwabdev/` (vendored third-party Schwab API client) is excluded
from ruff/mypy — it's kept as close to upstream as possible; see its
docstring for the original source. It carries its own MIT licence file;
leave the attribution headers intact.

`ruff check .` also runs as a pre-commit hook against the same config CI
uses, so the two cannot disagree. `git commit --no-verify` skips it when you
genuinely need to.

## Frontend notes

```bash
cd web
npm run dev          # dev server, port 5173
npm run build        # production build
npx tsc --noEmit     # type check
npx vitest run       # tests
```

> [!WARNING]
> `npx tsc --noEmit` can report success on broken JSX, because the root
> `tsconfig.json` delegates to project references. Run `npm run build`
> before trusting a green type check.

Read [UI_UX.md](UI_UX.md) before changing layout. Two constraints there are
easy to break and hard to diagnose — the page transition must stay
opacity-only, and the results page needs an ancestor with a resolved height
or the chart collapses.

## Working with Schwab data

Access tokens (30 minutes) refresh themselves. The **refresh token lasts 7
days** and only an interactive sign-in can renew it, through the
`SchwabAuthWidget` in the sidebar.

> [!IMPORTANT]
> When the token is expiring or expired, ask the account owner for a new
> one. Do not attempt to re-authenticate on someone's behalf.

Never commit `config/credentials.yaml` or `config/schwab_tokens.json`. Both
are gitignored; check `git status` before a broad `git add`.

## Debugging by symptom

| Symptom | Look at first |
|---|---|
| Tests fail on a clean checkout | Python version — are you on 3.12? |
| Backtest returns no trades | Session filter emptied the bar set |
| Chart disagrees with the broker | Session anchor, then timeframe aggregation |
| Second run differs from the first | A strategy's `reset()` is incomplete |
| Data source missing in the UI | `GET /api/data-sources` — it reports the real reason |
| Frontend builds but renders blank | Type check passed on broken JSX; run `npm run build` |
| Deploy "succeeded" but nothing changed | The commit assertion should have caught it — check that step |

## Commit conventions

This repo doesn't enforce a commit-message format via tooling, but recent
history favors short, imperative subject lines describing *why* a change
was made, not a restatement of the diff. Never commit
`config/credentials.yaml` or `config/schwab_tokens.json` — both are
gitignored; double-check `git status` before a broad `git add`.

## Pull requests

See [CONTRIBUTING.md](../CONTRIBUTING.md).

---

<sub>[⬅ Back to docs](README.md)</sub>
