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

## Running tests

```bash
pytest tests/ -v
```

## Code quality tools

```bash
ruff check .        # lint (config in pyproject.toml's [tool.ruff])
mypy src/analysis    # type check (informational on src/analysis -- see RELEASE_AUDIT.md)
vulture src api      # dead-code scan
bandit -r src api -ll   # security scan
pip-audit             # dependency CVE scan
black .                # formatter
```

`src/data/schwabdev/` (vendored third-party Schwab API client) is excluded
from ruff/mypy — it's kept as close to upstream as possible; see its
docstring for the original source.

## Commit conventions

This repo doesn't enforce a commit-message format via tooling, but recent
history favors short, imperative subject lines describing *why* a change
was made, not a restatement of the diff. Never commit
`config/credentials.yaml` or `config/schwab_tokens.json` — both are
gitignored; double-check `git status` before a broad `git add`.

## Pull requests

See [CONTRIBUTING.md](../CONTRIBUTING.md).
