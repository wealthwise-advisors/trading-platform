"""Avg win / avg loss as a price move, which is what the KPI pair shows."""
import datetime as dt
import pytest
from api.serializers import _avg_points
from src.backtesting.results import Trade


def _t(direction, entry, exit_, pnl):
    return Trade(symbol="ES", direction=direction, quantity=1,
                 entry_time=dt.datetime(2026, 1, 5, 9, 30), entry_price=entry,
                 exit_time=dt.datetime(2026, 1, 5, 9, 45), exit_price=exit_,
                 pnl=pnl, commission=2.5, strategy="rsi")


def test_a_long_winner_measures_the_move_up():
    assert _avg_points([_t("LONG", 4500.0, 4512.4, 617.5)], winners=True) == pytest.approx(12.4)


def test_a_short_winner_measures_the_move_down():
    """A short that falls 12.4 points won 12.4 points, not minus 12.4."""
    assert _avg_points([_t("SHORT", 4512.4, 4500.0, 617.5)], winners=True) == pytest.approx(12.4)


def test_a_loser_is_reported_as_a_negative_move():
    assert _avg_points([_t("LONG", 4500.0, 4481.4, -932.5)], winners=False) == pytest.approx(-18.6)


def test_winners_and_losers_are_averaged_separately():
    trades = [_t("LONG", 4500.0, 4510.0, 500.0), _t("LONG", 4500.0, 4514.8, 740.0),
              _t("LONG", 4500.0, 4490.0, -500.0)]
    assert _avg_points(trades, winners=True) == pytest.approx(12.4)
    assert _avg_points(trades, winners=False) == pytest.approx(-10.0)


def test_an_open_trade_is_skipped_rather_than_counted_as_zero():
    assert _avg_points([_t("LONG", 4500.0, None, 0.0)], winners=True) is None


def test_a_flat_trade_belongs_to_neither_side():
    flat = _t("LONG", 4500.0, 4500.0, 0.0)
    assert _avg_points([flat], winners=True) is None
    assert _avg_points([flat], winners=False) is None


def test_no_trades_on_that_side_is_none_not_zero():
    """Zero points and nothing to measure are different facts."""
    assert _avg_points([_t("LONG", 4500.0, 4510.0, 500.0)], winners=False) is None


def test_it_does_not_divide_by_a_contract_multiplier():
    """The move is the move. A 12.4-point win on ES is 12.4 points whether it
    was one contract or ten, and whatever commission was charged."""
    big = _t("LONG", 4500.0, 4512.4, 6175.0)
    big.quantity = 10
    assert _avg_points([big], winners=True) == pytest.approx(12.4)
