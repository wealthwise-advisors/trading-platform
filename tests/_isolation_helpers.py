"""A minimal BacktestResults, for tests that exercise the store below HTTP.

Underscore-prefixed so pytest does not collect it as a test module.

The repository-level isolation tests need a real result object to insert, but
nothing about ownership depends on the numbers in it -- so this builds the
smallest object the dataclass will accept rather than running an engine, which
would make those tests slow and would couple them to strategy behaviour that
has nothing to do with who owns a row.
"""

from datetime import datetime

import pandas as pd

from src.backtesting.results import BacktestResults


def tiny_results(symbol: str = "ES") -> BacktestResults:
    """One result with one bar and no trades."""
    idx = pd.date_range("2024-01-02 09:30", periods=1, freq="1h")
    return BacktestResults(
        symbol=symbol,
        strategy_name="test",
        timeframe="1h",
        start_date=datetime(2024, 1, 2),
        end_date=datetime(2024, 1, 3),
        initial_capital=100_000.0,
        trades=[],
        equity_curve=pd.Series([100_000.0], index=idx),
        price_data=pd.DataFrame(
            {"open": [1.0], "high": [2.0], "low": [0.5], "close": [1.5],
             "volume": [10]},
            index=idx,
        ),
        final_capital=100_000.0,
    )
