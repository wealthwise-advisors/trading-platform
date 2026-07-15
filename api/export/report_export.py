"""Builds the DataFrames used by the multi-format backtest report export
(CSV/Excel/PDF/Word) -- a metrics summary table and a trade log table, fed
into api.export.formats' generic converters."""

from __future__ import annotations

import pandas as pd

from src.backtesting.results import BacktestResults


def build_metrics_df(results: BacktestResults) -> pd.DataFrame:
    r = results
    rows = [
        ("Symbol", r.symbol),
        ("Strategy", r.strategy_name),
        ("Timeframe", r.timeframe),
        ("Start Date", str(r.start_date.date())),
        ("End Date", str(r.end_date.date())),
        ("Initial Capital", f"${r.initial_capital:,.0f}"),
        ("Final Capital", f"${r.final_capital:,.0f}"),
        ("Total P&L", f"${r.total_pnl:+,.0f}"),
        ("Total Return %", f"{r.total_return_pct:+.2f}%"),
        ("Sharpe Ratio", f"{r.sharpe_ratio:.2f}"),
        ("Sortino Ratio", f"{r.sortino_ratio:.2f}"),
        ("Max Drawdown %", f"{r.max_drawdown_pct:.2f}%"),
        ("Win Rate %", f"{r.win_rate:.1f}%"),
        ("Profit Factor", f"{r.profit_factor:.2f}"),
        ("Total Trades", r.total_trades),
        ("Winning Trades", r.winning_trades),
        ("Losing Trades", r.losing_trades),
        ("Avg Win", f"${r.avg_win:,.0f}"),
        ("Avg Loss", f"${r.avg_loss:,.0f}"),
        ("Avg Trade Duration (min)", f"{r.avg_trade_duration_min:.0f}"),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Value"]).set_index("Metric")


def build_trades_df(results: BacktestResults) -> pd.DataFrame:
    rows = []
    for i, t in enumerate(results.trades, 1):
        rows.append({
            "#": i,
            "Direction": t.direction,
            "Entry Time": t.entry_time,
            "Entry Price": t.entry_price,
            "Exit Time": t.exit_time,
            "Exit Price": t.exit_price,
            "Duration (min)": t.duration_minutes,
            "P&L": t.pnl,
        })
    return pd.DataFrame(rows).set_index("#") if rows else pd.DataFrame(
        columns=["Direction", "Entry Time", "Entry Price", "Exit Time",
                 "Exit Price", "Duration (min)", "P&L"])
