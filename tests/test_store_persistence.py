"""A backtest result must survive the process that produced it.

The store used to be a dict, so every result 404'd after a restart. These tests
hold it to the one promise that change was for: what save() wrote, a FRESH
interpreter state can read back identically -- which is simulated by clearing
the in-memory cache, the only thing a restart actually loses.
"""

from datetime import datetime, time

import pandas as pd
import pytest

from api import store
from src.backtesting.results import BacktestResults, Trade


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    """Point the store at a scratch directory and give it an empty cache."""
    monkeypatch.setattr(store, "STORE_DIR", tmp_path / "backtests")
    monkeypatch.setattr(store, "_store", {})
    return store


def _results() -> BacktestResults:
    idx = pd.date_range("2024-03-04 09:30", periods=120, freq="1min")
    prices = pd.DataFrame(
        {
            "open": [4500.0 + i * 0.25 for i in range(120)],
            "high": [4501.0 + i * 0.25 for i in range(120)],
            "low": [4499.0 + i * 0.25 for i in range(120)],
            "close": [4500.5 + i * 0.25 for i in range(120)],
            "volume": [100 + i for i in range(120)],
        },
        index=idx,
    )
    return BacktestResults(
        symbol="ES",
        strategy_name="RSI Divergence",
        timeframe="1m",
        start_date=datetime(2024, 3, 4, 9, 30),
        end_date=datetime(2024, 3, 4, 11, 30),
        initial_capital=100_000.0,
        trades=[
            Trade("ES", "LONG", 1, datetime(2024, 3, 4, 9, 45), 4510.25,
                  datetime(2024, 3, 4, 10, 5), 4515.75, 272.5, 2.5, "RSI Divergence",
                  "o1", "o2"),
            # An open trade: exit_time and exit_price are None and must stay None
            # rather than coming back as the string "None" or as NaT.
            Trade("ES", "SHORT", 2, datetime(2024, 3, 4, 11, 0), 4530.00,
                  None, None, 0.0, 5.0, "RSI Divergence", "o3", ""),
        ],
        equity_curve=pd.Series(
            [100_000.0 + i * 3.5 for i in range(120)], index=idx
        ),
        price_data=prices,
        total_pnl=272.5,
        total_return_pct=0.2725,
        sharpe_ratio=1.42,
        sortino_ratio=2.01,
        max_drawdown_pct=-1.8,
        win_rate=50.0,
        profit_factor=1.9,
        avg_win=272.5,
        avg_loss=0.0,
        total_trades=2,
        winning_trades=1,
        losing_trades=0,
        avg_trade_duration_min=20.0,
        final_capital=100_272.5,
    )


def test_result_survives_a_restart(tmp_store):
    bid = tmp_store.save(_results(), "synthetic", time(9, 30), time(16, 0))

    tmp_store._store.clear()          # this is what a restart costs you
    got = tmp_store.get(bid)

    assert got is not None, "result did not come back from disk"
    assert got.data_source == "synthetic"
    assert got.session_start == time(9, 30)
    assert got.session_end == time(16, 0)


def test_every_scalar_field_round_trips(tmp_store):
    """Enumerated from the dataclass, so a metric added later is covered here
    without anyone remembering to extend this test."""
    original = _results()
    bid = tmp_store.save(original, "synthetic", time(9, 30), time(16, 0))
    tmp_store._store.clear()
    got = tmp_store.get(bid).results

    for name in store._SCALAR_FIELDS:
        assert getattr(got, name) == getattr(original, name), f"{name} changed"


def test_frames_round_trip_with_index_and_dtypes(tmp_store):
    original = _results()
    bid = tmp_store.save(original, "synthetic", time(9, 30), time(16, 0))
    tmp_store._store.clear()
    got = tmp_store.get(bid).results

    # check_freq=False, and only that. Parquet does not carry a DatetimeIndex's
    # freq attribute, but no provider sets one: an index parsed out of a CSV or
    # an API response has freq=None already, and nothing in src/ or api/ reads
    # it. The fixture only has one because it was built with date_range. The
    # timestamps themselves are asserted equal below, so this relaxes the
    # metadata and not the data.
    pd.testing.assert_frame_equal(got.price_data, original.price_data,
                                  check_freq=False)
    pd.testing.assert_series_equal(got.equity_curve, original.equity_curve,
                                   check_names=False, check_freq=False)
    assert isinstance(got.price_data.index, pd.DatetimeIndex)
    assert list(got.price_data.index) == list(original.price_data.index)
    assert got.price_data.index.tz == original.price_data.index.tz


def test_open_trade_keeps_its_nulls(tmp_store):
    original = _results()
    bid = tmp_store.save(original, "synthetic", time(9, 30), time(16, 0))
    tmp_store._store.clear()
    got = tmp_store.get(bid).results

    assert len(got.trades) == 2
    closed, open_ = got.trades
    assert closed.entry_time == datetime(2024, 3, 4, 9, 45)
    assert closed.exit_time == datetime(2024, 3, 4, 10, 5)
    assert closed.pnl == 272.5
    assert open_.exit_time is None
    assert open_.exit_price is None


def test_unknown_id_returns_none(tmp_store):
    assert tmp_store.get("AT-doesnotexist") is None


def test_an_unwritable_store_does_not_break_the_backtest(tmp_store, monkeypatch):
    """Persistence is a convenience. Losing it must cost history, not the run."""
    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(store, "_write", boom)
    bid = tmp_store.save(_results(), "synthetic", time(9, 30), time(16, 0))

    assert tmp_store.get(bid) is not None, "in-memory result was lost too"
    tmp_store._store.clear()
    assert tmp_store.get(bid) is None, "nothing should have reached disk"


def test_a_half_written_manifest_is_skipped(tmp_store):
    """A crash mid-write must not leave a directory that loads as a real result."""
    bid = tmp_store.save(_results(), "synthetic", time(9, 30), time(16, 0))
    (store.STORE_DIR / bid / store.MANIFEST).unlink()

    tmp_store._store.clear()
    assert tmp_store.get(bid) is None


def test_a_future_format_version_is_refused(tmp_store):
    bid = tmp_store.save(_results(), "synthetic", time(9, 30), time(16, 0))
    mf = store.STORE_DIR / bid / store.MANIFEST
    mf.write_text(mf.read_text(encoding="utf-8").replace(
        f'"format_version": {store.FORMAT_VERSION}', '"format_version": 999'),
        encoding="utf-8")

    tmp_store._store.clear()
    assert tmp_store.get(bid) is None


def test_list_and_delete(tmp_store):
    a = tmp_store.save(_results(), "synthetic", time(9, 30), time(16, 0))
    b = tmp_store.save(_results(), "csv", time(9, 30), time(16, 0))
    assert set(tmp_store.list_ids()) == {a, b}

    assert tmp_store.delete(a) is True
    tmp_store._store.clear()
    assert tmp_store.get(a) is None
    assert tmp_store.get(b) is not None
    assert tmp_store.delete("AT-nothing") is False
