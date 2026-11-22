"""Monthly Returns: the first month of a run is measured from the starting capital.

It used to be measured against the month before it, which a run has not got, so every
first month came out empty -- a 16-20 Nov run that made +21.9% showed November as
"no data" (2026-11-22)."""
import pandas as pd

from api.serializers import monthly_returns
from src.backtesting.results import BacktestResults


def _results(points, capital=100_000.0):
    eq = pd.Series([v for _, v in points], index=pd.to_datetime([t for t, _ in points]))
    return BacktestResults(symbol="ES", strategy_name="t", timeframe="5m", start_date=eq.index[0].to_pydatetime(),
                           end_date=eq.index[-1].to_pydatetime(), initial_capital=capital, equity_curve=eq)


def _cell(out, year, month):
    return out["values"][out["years"].index(str(year))][month - 1]


def test_a_run_inside_one_month_shows_that_month():
    out = monthly_returns(_results([("2026-11-16 09:30", 100_000), ("2026-11-20 16:00", 121_900)]))
    assert _cell(out, 2026, 11) == 21.9


def test_the_first_month_counts_from_the_starting_capital_and_the_next_from_its_close():
    out = monthly_returns(_results([("2026-10-20", 100_000), ("2026-10-31", 110_000), ("2026-11-30", 99_000)]))
    assert _cell(out, 2026, 10) == 10.0
    assert _cell(out, 2026, 11) == -10.0
    assert _cell(out, 2026, 9) is None          # before the run: still no data


def test_a_losing_first_month_is_negative():
    out = monthly_returns(_results([("2026-11-02", 100_000), ("2026-11-27", 95_000)]))
    assert _cell(out, 2026, 11) == -5.0
