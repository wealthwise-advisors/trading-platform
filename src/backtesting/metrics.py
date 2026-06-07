import numpy as np
import pandas as pd
from .results import BacktestResults


def compute_metrics(results: BacktestResults) -> BacktestResults:
    """Populate all metric fields on a BacktestResults object in-place."""
    trades = results.trades
    results.total_trades = len(trades)

    if not trades:
        return results

    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    results.total_pnl = sum(pnls)
    results.final_capital = results.initial_capital + results.total_pnl
    results.total_return_pct = (results.total_pnl / results.initial_capital) * 100
    results.winning_trades = len(wins)
    results.losing_trades = len(losses)
    results.win_rate = (len(wins) / len(trades)) * 100 if trades else 0.0
    results.avg_win = np.mean(wins) if wins else 0.0
    results.avg_loss = np.mean(losses) if losses else 0.0
    results.profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else float("inf")

    durations = [t.duration_minutes for t in trades if t.duration_minutes is not None]
    results.avg_trade_duration_min = np.mean(durations) if durations else 0.0

    # Sharpe & Sortino from equity curve returns
    if len(results.equity_curve) > 2:
        eq = results.equity_curve
        daily_returns = eq.pct_change().dropna()

        if daily_returns.std() > 0:
            results.sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        downside = daily_returns[daily_returns < 0]
        if len(downside) > 0 and downside.std() > 0:
            results.sortino_ratio = (daily_returns.mean() / downside.std()) * np.sqrt(252)

        # Max drawdown
        rolling_max = eq.cummax()
        drawdown = (eq - rolling_max) / rolling_max * 100
        results.max_drawdown_pct = abs(drawdown.min())

    return results
