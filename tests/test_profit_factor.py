"""Profit factor across its three outcomes, end to end.

gross win / gross loss is a ratio ONLY when something was lost. The other two
cases are not numbers:

    winners, no losers   -> unbounded  (the best a run can do)
    nothing won or lost  -> undefined  (there is nothing to divide)

Both used to reach the client as 0.0 -- the same value a run that lost
everything reports. These tests pin the distinction at every layer it crosses:
the metric, the JSON, the optimiser's ranking, and the two report writers.
"""

import math

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.serializers import profit_factor_label, results_to_summary
from src.backtesting.metrics import compute_metrics
from src.backtesting.results import BacktestResults

client = TestClient(app)


class _Trade:
    """A stand-in for a Trade, with the fields the paths under test read.

    It began as just `pnl` and `duration_minutes`, which is all
    compute_metrics looks at. The serializer now also derives the average
    move in POINTS from each trade's entry and exit, so a stub without prices
    stopped standing in for a real Trade -- which always has them -- and the
    JSON tests failed on the fake rather than on the code.

    Prices are placed so the move agrees with the pnl's sign: a 1-point move
    per $50, the E-mini's point value.
    """

    def __init__(self, pnl, *, direction="LONG", entry_price=4500.0):
        self.pnl = pnl
        self.duration_minutes = 10
        self.direction = direction
        self.entry_price = entry_price
        move = pnl / 50.0
        self.exit_price = entry_price + (move if direction == "LONG" else -move)


def _results(pnls) -> BacktestResults:
    import datetime as dt
    r = BacktestResults(
        symbol="ES", strategy_name="rsi", timeframe="5m",
        start_date=dt.datetime(2026, 1, 5), end_date=dt.datetime(2026, 1, 5),
        initial_capital=100_000.0,
    )
    r.trades = [_Trade(p) for p in pnls]
    return compute_metrics(r)


class TestTheMetric:
    def test_a_ratio_when_something_was_lost(self):
        r = _results([300.0, -100.0])
        assert r.profit_factor == pytest.approx(3.0)

    def test_unbounded_when_there_are_winners_and_no_losers(self):
        r = _results([300.0, 100.0])
        assert math.isinf(r.profit_factor)

    def test_undefined_when_nothing_was_won_or_lost(self):
        """Every trade closed exactly flat. The old expression called this
        infinitely profitable, which is the opposite of what happened."""
        r = _results([0.0, 0.0])
        assert math.isnan(r.profit_factor)

    def test_undefined_when_there_were_no_trades_at_all(self):
        """Not 0.0 -- zero is the score of a strategy that lost everything."""
        r = _results([])
        assert math.isnan(r.profit_factor)

    def test_a_losing_run_is_still_a_real_number(self):
        r = _results([100.0, -400.0])
        assert r.profit_factor == pytest.approx(0.25)


class TestTheJson:
    @staticmethod
    def _summary(pnls):
        import datetime as dt
        r = _results(pnls)
        r.symbol, r.strategy_name, r.timeframe = "ES", "rsi", "5m"
        r.start_date = r.end_date = dt.datetime(2026, 1, 5)
        return results_to_summary("bt-1", r, "synthetic", None, None)

    def test_unbounded_serialises_as_null_not_zero(self):
        s = self._summary([300.0, 100.0])
        assert s["profit_factor"] is None
        # The counts are what let a reader tell unbounded from undefined.
        assert s["winning_trades"] == 2 and s["losing_trades"] == 0

    def test_undefined_serialises_as_null_too(self):
        s = self._summary([])
        assert s["profit_factor"] is None
        assert s["total_trades"] == 0

    def test_a_finite_factor_is_still_a_number(self):
        assert self._summary([300.0, -100.0])["profit_factor"] == pytest.approx(3.0)

    def test_zero_is_reserved_for_a_run_that_actually_lost(self):
        """0.0 must keep meaning "won nothing against real losses", which is
        precisely what it stopped meaning when inf was mapped onto it."""
        s = self._summary([-100.0, -50.0])
        assert s["profit_factor"] == 0.0


class TestTheReportWriters:
    def test_the_html_report_shows_a_symbol_not_the_word_inf(self):
        assert profit_factor_label(float("inf")) == "∞"
        assert profit_factor_label(float("nan")) == "—"
        assert profit_factor_label(2.5) == "2.50"

    def test_the_file_exports_avoid_a_glyph_their_font_lacks(self):
        """reportlab's standard fonts are WinAnsi-encoded and have no U+221E,
        so a PDF would render it as a black box."""
        assert profit_factor_label(float("inf"), unicode=False) == "Infinite"
        assert profit_factor_label(float("nan"), unicode=False) == "Undefined"
        assert profit_factor_label(2.5, unicode=False) == "2.50"

    def test_the_metrics_table_never_prints_a_raw_float_repr(self):
        from api.export.report_export import build_metrics_df
        import datetime as dt
        r = _results([300.0, 100.0])
        r.symbol, r.strategy_name, r.timeframe = "ES", "rsi", "5m"
        r.start_date = r.end_date = dt.datetime(2026, 1, 5)
        df = build_metrics_df(r)
        # "Metric" is the index of this frame, not a column.
        assert df.loc["Profit Factor", "Value"] == "Infinite"


class TestTheApiContract:
    def test_the_schema_allows_null(self):
        """A client generated from the OpenAPI document has to know this field
        is nullable, or it will fail to parse a flawless run."""
        schema = app.openapi()["components"]["schemas"]["OptimizeCombo"]["properties"]["profit_factor"]
        allows_null = (
            schema.get("type") == "null"
            or any(o.get("type") == "null" for o in schema.get("anyOf", []))
            or schema.get("nullable") is True
        )
        assert allows_null, schema
