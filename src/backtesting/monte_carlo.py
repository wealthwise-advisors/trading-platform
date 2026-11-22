"""Monte Carlo on a run's trades (upgrade plan, Feature 6).

One backtest is one ordering of its trades. Two questions it cannot answer by itself:

  * SHUFFLE -- the same trades in other orders. The final P&L is fixed; what moves is the
    drawdown: how deep could the hole have been with the same trades arriving differently?
  * BOOTSTRAP -- trades drawn with replacement, as many as the run had. The final P&L
    spreads too: how much of the result was this particular set of trades?

Both report percentiles of final P&L and of maximum drawdown, the chance of ending below
the starting capital (and, given a threshold, of losing more than it), and a 5/50/95%
equity fan per trade for the chart. Seeded, so the same inputs give the same answer.
"""
from __future__ import annotations

import numpy as np

PCTS = (5, 25, 50, 75, 95)


def _drawdowns(equity: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Max drawdown in dollars and percent of the running peak, per row."""
    peak = np.maximum.accumulate(equity, axis=1)
    dd = peak - equity
    worst = dd.argmax(axis=1)
    rows = np.arange(equity.shape[0])
    return dd.max(axis=1), dd[rows, worst] / peak[rows, worst] * 100


def _summary(pnl_rows: np.ndarray, capital: float, loss_threshold: float | None) -> dict:
    equity = capital + np.concatenate([np.zeros((len(pnl_rows), 1)), pnl_rows.cumsum(axis=1)], axis=1)
    finals = equity[:, -1] - capital
    dd, dd_pct = _drawdowns(equity)
    pct = lambda a: {f"p{p}": float(np.percentile(a, p)) for p in PCTS}        # noqa: E731
    out = {
        "final_pnl": pct(finals),
        "max_drawdown": pct(dd),
        "max_drawdown_pct": pct(dd_pct),
        "prob_loss": float((finals < 0).mean()),
        "equity_fan": {k: [float(v) for v in np.percentile(equity, p, axis=0)]
                       for k, p in (("p5", 5), ("p50", 50), ("p95", 95))},
    }
    if loss_threshold:
        out["prob_loss_over"] = float((finals < -abs(loss_threshold)).mean())
    return out


def monte_carlo(pnls: list[float], initial_capital: float, runs: int = 1000, seed: int = 0,
                loss_threshold: float | None = None) -> dict:
    p = np.asarray(pnls, dtype=float)
    if p.size < 2:
        raise ValueError("Monte Carlo needs at least 2 trades.")
    rng = np.random.default_rng(seed)
    shuffled = rng.permuted(np.tile(p, (runs, 1)), axis=1)
    boot = rng.choice(p, size=(runs, p.size), replace=True)
    actual_eq = initial_capital + np.concatenate([[0.0], p.cumsum()])
    dd, dd_pct = _drawdowns(actual_eq[None, :])
    return {
        "runs": runs, "trades": int(p.size), "seed": seed, "initial_capital": initial_capital,
        "actual": {"final_pnl": float(p.sum()), "max_drawdown": float(dd[0]), "max_drawdown_pct": float(dd_pct[0])},
        "shuffle": _summary(shuffled, initial_capital, loss_threshold),
        "bootstrap": _summary(boot, initial_capital, loss_threshold),
    }
