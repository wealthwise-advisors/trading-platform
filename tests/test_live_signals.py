"""Live strategy signals (upgrade plan, Feature 2).

The strategy runs on bars that arrive after the backtest, closed bars only, with the
engine's own rules for when a signal changes the position.
"""
from datetime import datetime

import pandas as pd
import pytest

from api.strategy_registry import build_strategy
from src.backtesting.engine import BacktestEngine
from src.backtesting.live_signals import LiveSignalRunner
from src.data.sample_data import generate_sample_data

PARAMS = {"period": 5, "oversold": 30, "overbought": 70}


@pytest.fixture(scope="module")
def bars(tmp_path_factory) -> pd.DataFrame:
    tmp = tmp_path_factory.mktemp("bars")
    df = generate_sample_data("ES", datetime(2026, 11, 16), bars=400, timeframe_minutes=5, save_dir=str(tmp))
    return df[["open", "high", "low", "close", "volume"]]


def runner(edge=None):
    return LiveSignalRunner(build_strategy("rsi_mean_reversion", PARAMS), "ES", "5m", contracts=1, edge=edge)


def test_the_same_signals_as_the_backtest(bars):
    class Frame:                                  # a provider that serves exactly these bars
        def load(self, *a, **k):
            return bars
    engine = BacktestEngine(data_provider=Frame(), strategy=build_strategy("rsi_mean_reversion", PARAMS),
                            symbol="ES", timeframe="5m", initial_capital=100_000,
                            commission_per_contract=0, contracts_per_trade=1,
                            tick_size=0.25, tick_value=12.5)
    res = engine.run(bars.index[0].to_pydatetime(), bars.index[-1].to_pydatetime())
    r = runner()
    r.feed(pd.concat([bars, bars.iloc[[-1]].set_axis([bars.index[-1] + pd.Timedelta(minutes=5)])]))
    sigs = {s["time"]: s["side"] for s in r.signals}
    assert res.trades, "the fixture must trade, or this test proves nothing"
    nxt = {t: bars.index[i + 1] for i, t in enumerate(bars.index[:-1])}
    for tr in res.trades:
        before = next(t for t, n in nxt.items() if n == pd.Timestamp(tr.entry_time))
        assert sigs.get(before.to_pydatetime()) == ("BUY" if tr.direction == "LONG" else "SELL")


def test_bar_by_bar_equals_all_at_once(bars):
    once, step = runner(), runner()
    once.feed(bars)
    for i in range(2, len(bars) + 1):
        step.feed(bars.iloc[:i])
    assert step.signals == once.signals


def test_the_forming_bar_never_signals(bars):
    r = runner()
    r.feed(bars)
    assert all(s["time"] < bars.index[-1].to_pydatetime() for s in r.signals)


def test_a_replaced_forming_bar_is_not_fed_twice(bars):
    r = runner()
    r.feed(bars.iloc[:50])
    changed = bars.iloc[:50].copy()
    changed.iloc[-1, changed.columns.get_loc("close")] += 50        # the forming bar moved
    r.feed(changed)
    again = runner()
    again.feed(bars.iloc[:50])
    assert r.signals == again.signals


def test_only_signals_from_the_edge_on_are_live(bars):
    edge = bars.index[len(bars) // 2].to_pydatetime()
    r = runner(edge=edge)
    r.feed(bars)
    full = runner()
    full.feed(bars)
    assert r.signals == [s for s in full.signals if s["time"] >= edge]
    assert r.signals, "the second half must signal, or this test proves nothing"


def test_a_signal_carries_price_and_reason(bars):
    r = runner()
    r.feed(bars)
    s = r.signals[0]
    assert set(s) == {"time", "side", "price", "reason"} and s["side"] in {"BUY", "SELL", "CLOSE"}


def test_two_tabs_polling_at_once_never_double_feed(bars):
    from concurrent.futures import ThreadPoolExecutor
    r, ref = runner(), runner()
    ref.feed(bars)
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda _: r.feed(bars), range(8)))
    assert r.signals == ref.signals
