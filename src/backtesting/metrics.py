import numpy as np
from .results import BacktestResults


def compute_metrics(results: BacktestResults) -> BacktestResults:
    """Populate all metric fields on a BacktestResults object in-place."""
    trades = results.trades
    results.total_trades = len(trades)

    if not trades:
        # No trades is not a profit factor of zero -- zero is the score of a
        # strategy that lost everything it risked. Undefined, same as the
        # all-flat case below, and serialised as null.
        results.profit_factor = float("nan")
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
    # PROFIT FACTOR HAS THREE OUTCOMES, NOT ONE NUMBER.
    #
    # gross win / gross loss is only a ratio when something was lost. The old
    # expression collapsed the other two cases into float("inf"), so a run in
    # which every trade closed exactly flat -- nothing won, nothing lost --
    # reported the same "infinitely profitable" as a run of pure winners.
    #
    # inf  = won something, lost nothing. Genuinely unbounded.
    # nan  = nothing to divide. Undefined, and NOT a good score.
    # Serialisation maps both to JSON null; the trade counts beside it say
    # which of the two it was.
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    if gross_loss > 0:
        results.profit_factor = gross_win / gross_loss
    elif gross_win > 0:
        results.profit_factor = float("inf")
    else:
        results.profit_factor = float("nan")

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
