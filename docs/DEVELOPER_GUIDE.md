# Developer Guide

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

## Working on the Elliott Wave engine

**Read this before touching anything in `src/analysis/`.** The engine
went through 9 development tasks (core detection → recursive validation →
unified classification → triangles → complex corrections → diagonals →
regression suite → validation framework → industry benchmark) plus 3
follow-up "prove it or fix it" improvement passes, all under one rule:
**never modify detector logic, scoring, or DP selection without objective
evidence from a failing test or a measured benchmark regression.** A
"looks wrong" or "could be cleaner" is not evidence — see
`benchmark/TASK9_IMPROVEMENT_REPORT.md` section 4 for what real evidence
looks like (every disagreement independently re-verified via a second,
different measurement before any conclusion was drawn).

If you find something that looks like a bug:

1. Write a failing test in `tests/elliott/` first (or point to an
   existing benchmark case that demonstrates it).
2. Confirm the failure is in the engine, not the test fixture — fractal
   pivot confirmation at series endpoints has caused multiple false
   "engine bugs" that were actually fixture-construction mistakes (see
   `tests/elliott/conftest.py` and `benchmark/pipeline.py`'s bug-fix
   comments).
3. Make the smallest change that fixes the specific, demonstrated defect.
4. Re-run `elliott validate` (56 tests) and `elliott benchmark` (473
   cases) — both must still pass/hold before the change is done.

## Running tests

```bash
pytest tests/ -v                              # everything (61 tests)
pytest tests/elliott -v                        # Elliott Wave suite only (56)
pytest tests/elliott -v --cov=src/analysis --cov-report=term-missing
elliott validate                                # same suite via the CLI
```

## Code quality tools

```bash
ruff check .        # lint (config in pyproject.toml's [tool.ruff])
mypy src/analysis    # type check (informational on src/analysis -- see RELEASE_AUDIT.md)
vulture src api      # dead-code scan
bandit -r src api benchmark validation -ll   # security scan
pip-audit             # dependency CVE scan
black .                # formatter
```

`src/data/schwabdev/` (vendored third-party Schwab API client) is excluded
from ruff/mypy — it's kept as close to upstream as possible; see its
docstring for the original source.

## Regenerating the benchmark

```bash
elliott benchmark          # full rebuild, ~40s (104 synthetic + 369 real-market cases)
elliott benchmark --report-only   # just summarize the existing benchmark.db
```

Full methodology, dataset sourcing, and honesty notes:
[benchmark/README.md](../benchmark/README.md) and
[benchmark/TASK9_IMPROVEMENT_REPORT.md](../benchmark/TASK9_IMPROVEMENT_REPORT.md).

## Commit conventions

This repo doesn't enforce a commit-message format via tooling, but recent
history favors short, imperative subject lines describing *why* a change
was made, not a restatement of the diff. Never commit
`config/credentials.yaml` or `config/schwab_tokens.json` — both are
gitignored; double-check `git status` before a broad `git add`.

## Pull requests

See [CONTRIBUTING.md](../CONTRIBUTING.md).
