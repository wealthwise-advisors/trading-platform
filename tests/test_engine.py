"""Smoke tests for the backtesting engine."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from src.data.sample_data import generate_sample_data
from src.data.csv_provider import CSVDataProvider
from src.strategies import MACrossoverStrategy, RSIMeanReversionStrategy, BreakoutStrategy
from src.backtesting.engine import BacktestEngine


def _run(strategy, symbol="ES", bars=500):
    generate_sample_data(
        symbol=symbol, start=datetime(2024, 1, 2, 9, 30),
        bars=bars, timeframe_minutes=5, base_price=4500.0,
        tick_size=0.25, save_dir="data/historical", seed=99,
    )
    engine = BacktestEngine(
        data_provider=CSVDataProvider("data/historical"),
        strategy=strategy,
        symbol=symbol, timeframe="5m",
        initial_capital=100_000.0,
        tick_size=0.25, tick_value=12.50, point_value=50.0,
    )
    return engine.run(datetime(2024, 1, 2), datetime(2024, 12, 31))


def test_ma_crossover_runs():
    r = _run(MACrossoverStrategy(fast=9, slow=21))
    assert r.total_trades >= 0
    assert len(r.equity_curve) > 0
    assert r.final_capital > 0


def test_rsi_runs():
    r = _run(RSIMeanReversionStrategy(period=14))
    assert r.total_trades >= 0
    assert r.sharpe_ratio != float("inf")


def test_breakout_runs():
    r = _run(BreakoutStrategy(lookback=20))
    assert r.total_trades >= 0


def test_equity_curve_length():
    r = _run(MACrossoverStrategy())
    assert len(r.equity_curve) > 10


def test_trade_pnl_types():
    r = _run(MACrossoverStrategy())
    for trade in r.trades:
        assert isinstance(trade.pnl, float)
        assert trade.entry_price > 0
