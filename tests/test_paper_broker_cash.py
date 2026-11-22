"""A closed trade's profit or loss reaches the account's cash.

The broker only ever took commissions off the cash, so every equity curve climbed while
a trade was open and fell back to the starting capital when it closed: a 16-20 Nov run
that made +21.9% ended its equity curve near $100,000, and Monthly Returns, Max Drawdown,
Sharpe and Balance History were all built on that line (2026-11-22)."""
from datetime import datetime

import pytest

from src.broker.base_broker import Order, OrderSide, OrderType
from src.broker.paper_broker import PaperBroker
from src.backtesting.engine import BacktestEngine
from src.strategies.ma_crossover import MACrossoverStrategy

T = datetime(2026, 11, 20, 10, 0)


def _fill(b, side, price, qty=1):
    b.submit_order(Order(symbol="ES", side=side, quantity=qty, order_type=OrderType.MARKET))
    b.process_bar("ES", price, price, price, price, T)


def _broker():   # ES: 0.25 tick = $12.50, so a point is $50; no slippage, $2.50 a contract
    return PaperBroker(initial_capital=100_000, commission_per_contract=2.5, slippage_ticks=0, tick_size=0.25, tick_value=12.5)


def test_a_winning_long_adds_its_profit():
    b = _broker()
    _fill(b, OrderSide.BUY, 6900)
    _fill(b, OrderSide.SELL, 6910)
    assert b.get_cash() == pytest.approx(100_000 + 10 * 50 - 2 * 2.5)


def test_a_losing_short_takes_its_loss():
    b = _broker()
    _fill(b, OrderSide.SELL, 6900, 2)
    _fill(b, OrderSide.BUY, 6904, 2)
    assert b.get_cash() == pytest.approx(100_000 - 4 * 50 * 2 - 4 * 2.5)


def test_an_open_position_has_no_realised_profit_yet():
    b = _broker()
    _fill(b, OrderSide.BUY, 6900)
    assert b.get_cash() == pytest.approx(100_000 - 2.5)


def test_part_of_a_position_closed_realises_only_that_part():
    b = _broker()
    _fill(b, OrderSide.BUY, 6900, 2)
    _fill(b, OrderSide.SELL, 6920, 1)
    assert b.get_cash() == pytest.approx(100_000 + 20 * 50 - 3 * 2.5)
    assert b.get_position("ES") == 1


def test_the_equity_curve_ends_at_the_final_capital():
    """End to end: the backtest's last equity point is the account it reports."""
    import api.routers.backtests as bt
    from datetime import date
    provider = bt._build_provider("synthetic", "ES", "5m", date(2026, 11, 16), date(2026, 11, 20),
                                  {"tick_size": 0.25, "tick_value": 12.5, "point_value": 50.0, "commission": 2.5})
    eng = BacktestEngine(data_provider=provider, strategy=MACrossoverStrategy(fast=3, slow=8), symbol="ES", timeframe="5m",
                         tick_size=0.25, tick_value=12.5, point_value=50.0)
    r = eng.run(datetime(2026, 11, 16), datetime(2026, 11, 20, 23, 59))
    assert r.total_trades > 0
    assert r.equity_curve.iloc[-1] == pytest.approx(r.final_capital, abs=0.01)
