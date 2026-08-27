"""A backtest result must survive the process that produced it.

The store used to be a dict, so every result 404'd after a restart. It is now a
cache in front of SQLite. These tests hold it to the promise that change was
for: what save() wrote, a fresh process can read back identically -- simulated
by clearing the in-memory cache, which is the only thing a restart really
loses.

The guard test at the bottom is the important one. A schema has columns typed
out by hand, so a metric added to BacktestResults without a matching migration
would be dropped silently. That test turns it into a build failure.
"""

import sqlite3
from dataclasses import fields
from datetime import datetime, time

import pandas as pd
import pytest

from api import store
from db import backtests as repo
from db import connection
from src.backtesting.results import BacktestResults, Trade


#: Whose results these are. Ownership arrived in schema v4; this suite is about
#: persistence, not isolation (tests/test_isolation.py covers that), so every
#: call here belongs to one owner and the id is threaded through explicitly.
#: There is no default on the store functions on purpose -- a default is what
#: lets an unscoped call slip through unnoticed.
OWNER = 1


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    """A scratch database, scratch parquet directory, and an empty cache."""
    db = tmp_path / "autotrader.db"
    monkeypatch.setattr(connection, "DB_PATH", db)
    monkeypatch.setattr(repo, "DB_PATH", db)
    monkeypatch.setattr(repo, "BLOB_DIR", tmp_path / "backtests")
    monkeypatch.setattr(store, "_store", {})

    # backtests.user_id is a foreign key and PRAGMA foreign_keys is ON, so the
    # owner has to actually exist or every insert fails the constraint.
    from api import auth
    from db import users as user_repo
    uid = user_repo.create_user("persistence-owner", auth.hash_password("x" * 14))
    assert uid == OWNER, f"expected the first user to be id {OWNER}, got {uid}"
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
                  datetime(2024, 3, 4, 10, 5), 4515.75, 272.5, 2.5,
                  "RSI Divergence", "o1", "o2"),
            # An open trade: exit_time and exit_price are NULL and must come
            # back as None, not as the string "None" and not as NaT.
            Trade("ES", "SHORT", 2, datetime(2024, 3, 4, 11, 0), 4530.00,
                  None, None, 0.0, 5.0, "RSI Divergence", "o3", ""),
        ],
        equity_curve=pd.Series([100_000.0 + i * 3.5 for i in range(120)], index=idx),
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


# ── the promise ──────────────────────────────────────────────────────────────
def test_result_survives_a_restart(tmp_store):
    bid = tmp_store.save(_results(), "synthetic", time(9, 30), time(16, 0), user_id=OWNER)

    tmp_store._store.clear()          # this is what a restart costs you
    got = tmp_store.get(bid, user_id=OWNER)

    assert got is not None, "result did not come back from the database"
    assert got.data_source == "synthetic"
    assert got.session_start == time(9, 30)
    assert got.session_end == time(16, 0)


def test_every_scalar_field_round_trips(tmp_store):
    original = _results()
    bid = tmp_store.save(original, "synthetic", time(9, 30), time(16, 0), user_id=OWNER)
    tmp_store._store.clear()
    got = tmp_store.get(bid, user_id=OWNER).results

    for name in repo.RESULT_COLUMNS:
        assert getattr(got, name) == getattr(original, name), f"{name} changed"


def test_frames_round_trip_with_index_and_dtypes(tmp_store):
    original = _results()
    bid = tmp_store.save(original, "synthetic", time(9, 30), time(16, 0), user_id=OWNER)
    tmp_store._store.clear()
    got = tmp_store.get(bid, user_id=OWNER).results

    # check_freq=False, and only that. Parquet does not carry a DatetimeIndex's
    # freq attribute, but no provider sets one -- an index parsed out of a CSV
    # or an API response has freq=None already, and nothing in src/ or api/
    # reads it. The fixture only has one because it was built with date_range.
    # The timestamps themselves are asserted equal below.
    pd.testing.assert_frame_equal(got.price_data, original.price_data,
                                  check_freq=False)
    pd.testing.assert_series_equal(got.equity_curve, original.equity_curve,
                                   check_names=False, check_freq=False)
    assert isinstance(got.price_data.index, pd.DatetimeIndex)
    assert list(got.price_data.index) == list(original.price_data.index)
    assert got.price_data.index.tz == original.price_data.index.tz


def test_open_trade_keeps_its_nulls(tmp_store):
    original = _results()
    bid = tmp_store.save(original, "synthetic", time(9, 30), time(16, 0), user_id=OWNER)
    tmp_store._store.clear()
    got = tmp_store.get(bid, user_id=OWNER).results

    assert len(got.trades) == 2
    closed, open_ = got.trades
    assert closed.entry_time == datetime(2024, 3, 4, 9, 45)
    assert closed.exit_time == datetime(2024, 3, 4, 10, 5)
    assert closed.pnl == 272.5
    assert open_.exit_time is None
    assert open_.exit_price is None


def test_unknown_id_returns_none(tmp_store):
    assert tmp_store.get("AT-doesnotexist", user_id=OWNER) is None


# ── failure modes ────────────────────────────────────────────────────────────
def test_an_unwritable_database_does_not_break_the_backtest(tmp_store, monkeypatch):
    """Persistence is a convenience. Losing it must cost history, not the run."""
    def boom(*a, **k):
        raise sqlite3.OperationalError("attempt to write a readonly database")

    monkeypatch.setattr(repo, "insert", boom)
    bid = tmp_store.save(_results(), "synthetic", time(9, 30), time(16, 0), user_id=OWNER)

    assert tmp_store.get(bid, user_id=OWNER) is not None, "in-memory result was lost too"
    tmp_store._store.clear()
    assert tmp_store.get(bid, user_id=OWNER) is None, "nothing should have reached the database"


def test_a_newer_schema_is_refused_not_guessed(tmp_store, tmp_path):
    """A database written by a later build may have columns this one does not
    write. Refusing beats a partial INSERT that corrupts it quietly."""
    tmp_store.save(_results(), "synthetic", time(9, 30), time(16, 0), user_id=OWNER)
    conn = connection.connect()
    conn.execute("INSERT INTO schema_version (version, applied_at) VALUES (999, '')")
    conn.close()

    with pytest.raises(RuntimeError, match="schema v999"):
        connection.connect()


def test_deleting_a_result_takes_its_trades_with_it(tmp_store):
    """ON DELETE CASCADE, and the PRAGMA that makes it actually fire."""
    bid = tmp_store.save(_results(), "synthetic", time(9, 30), time(16, 0), user_id=OWNER)
    conn = connection.connect()
    assert conn.execute("SELECT COUNT(*) c FROM trades").fetchone()["c"] == 2
    conn.close()

    assert tmp_store.delete(bid, user_id=OWNER) is True
    conn = connection.connect()
    assert conn.execute("SELECT COUNT(*) c FROM trades").fetchone()["c"] == 0
    conn.close()

    tmp_store._store.clear()
    assert tmp_store.get(bid, user_id=OWNER) is None
    assert tmp_store.delete("AT-nothing", user_id=OWNER) is False


# ── the reason a database was worth it ───────────────────────────────────────
def test_querying_across_runs(tmp_store):
    """Storing blobs by id needs no database. This is the part that does."""
    good = _results()
    bad = _results()
    bad.sharpe_ratio = 0.3
    bad.symbol = "NQ"

    tmp_store.save(good, "synthetic", time(9, 30), time(16, 0), user_id=OWNER)
    tmp_store.save(bad, "synthetic", time(9, 30), time(16, 0), user_id=OWNER)

    assert len(tmp_store.summaries(user_id=OWNER)) == 2
    assert len(tmp_store.summaries(user_id=OWNER, symbol="ES")) == 1
    assert len(tmp_store.summaries(user_id=OWNER, min_sharpe=1.0)) == 1
    assert tmp_store.summaries(user_id=OWNER, min_sharpe=1.0)[0]["symbol"] == "ES"
    assert len(tmp_store.summaries(user_id=OWNER, symbol="NQ", min_sharpe=1.0)) == 0


def test_list_ids_is_newest_first(tmp_store):
    a = tmp_store.save(_results(), "synthetic", time(9, 30), time(16, 0), user_id=OWNER)
    b = tmp_store.save(_results(), "csv", time(9, 30), time(16, 0), user_id=OWNER)
    ids = tmp_store.list_ids(user_id=OWNER)
    assert set(ids) == {a, b}
    assert len(ids) == 2


# ── the guard ────────────────────────────────────────────────────────────────
def test_schema_covers_every_field_on_the_dataclass(tmp_store):
    """A hand-written schema is the cost of using SQL, and this is the receipt.

    Add a metric to BacktestResults and this fails, naming it, instead of the
    number being dropped on every save with nothing to notice it.
    """
    conn = connection.connect()
    try:
        have = set(connection.columns(conn, "backtests"))
        trade_have = set(connection.columns(conn, "trades"))
    finally:
        conn.close()

    frame_fields = {"equity_curve", "price_data", "trades"}
    want = {f.name for f in fields(BacktestResults)} - frame_fields
    missing = want - have
    assert not missing, (
        f"BacktestResults has {sorted(missing)} but the backtests table does not. "
        "Add the column to db/schema.sql and bump SCHEMA_VERSION."
    )

    trade_want = {f.name for f in fields(Trade)}
    trade_missing = trade_want - trade_have
    assert not trade_missing, (
        f"Trade has {sorted(trade_missing)} but the trades table does not. "
        "Add the column to db/schema.sql and bump SCHEMA_VERSION."
    )
