"""Reading and writing backtest results.

The only module that knows the table layout. api/store.py talks to this and
nothing else, so the SQL stays in one place and the routers never see a cursor.
"""

import logging
import shutil
from dataclasses import fields
from datetime import datetime
from datetime import time as time_type
from pathlib import Path

import pandas as pd

from db.connection import DB_PATH, connect
from src.backtesting.results import BacktestResults, Trade

log = logging.getLogger(__name__)

#: Parquet sidecars live beside the database file, one directory per result.
BLOB_DIR = DB_PATH.parent / "backtests"

EQUITY = "equity.parquet"
PRICES = "prices.parquet"

# Metric/identity columns, taken from the dataclass rather than typed out. The
# guard test compares this list against the table's columns, so adding a field
# to BacktestResults without a migration fails the build instead of dropping a
# number on the floor.
_FRAME_FIELDS = {"equity_curve", "price_data", "trades"}
RESULT_COLUMNS = [f.name for f in fields(BacktestResults) if f.name not in _FRAME_FIELDS]
TRADE_COLUMNS = [f.name for f in fields(Trade)]

_DATE_FIELDS = {"start_date", "end_date"}
_TRADE_DATE_FIELDS = {"entry_time", "exit_time"}


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _blob_dir(backtest_id: str) -> Path:
    return BLOB_DIR / backtest_id


# ── write ────────────────────────────────────────────────────────────────────
def insert(backtest_id: str, results: BacktestResults, data_source: str,
           session_start: time_type, session_end: time_type,
           db: Path | None = None) -> None:
    """Write one result. Raises on failure -- the caller decides what that means."""
    d = _blob_dir(backtest_id)
    d.mkdir(parents=True, exist_ok=True)

    equity_rows = price_rows = 0
    if results.equity_curve is not None and len(results.equity_curve):
        # A Series has no parquet writer; one named column round-trips both the
        # values and the DatetimeIndex without inventing a second format.
        results.equity_curve.to_frame(name="equity").to_parquet(d / EQUITY)
        equity_rows = len(results.equity_curve)
    if results.price_data is not None and not results.price_data.empty:
        results.price_data.to_parquet(d / PRICES)
        price_rows = len(results.price_data)

    row = {n: _iso(getattr(results, n)) for n in RESULT_COLUMNS}
    row.update(
        id=backtest_id,
        created_at=datetime.now().isoformat(timespec="seconds"),
        data_source=data_source,
        session_start=_iso(session_start),
        session_end=_iso(session_end),
        equity_rows=equity_rows,
        price_rows=price_rows,
    )

    cols = list(row)
    sql = (f"INSERT OR REPLACE INTO backtests ({', '.join(cols)}) "
           f"VALUES ({', '.join(':' + c for c in cols)})")

    conn = connect(db)
    try:
        # One transaction: the row and its trades land together or not at all,
        # so a crash mid-write cannot leave a result with half its trades.
        conn.execute("BEGIN")
        conn.execute(sql, row)
        conn.execute("DELETE FROM trades WHERE backtest_id = ?", (backtest_id,))
        conn.executemany(
            f"INSERT INTO trades (backtest_id, seq, {', '.join(TRADE_COLUMNS)}) "
            f"VALUES (?, ?, {', '.join('?' for _ in TRADE_COLUMNS)})",
            [
                (backtest_id, i, *[_iso(getattr(t, c)) for c in TRADE_COLUMNS])
                for i, t in enumerate(results.trades)
            ],
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


# ── read ─────────────────────────────────────────────────────────────────────
def fetch(backtest_id: str, db: Path | None = None):
    """One result, or None. Returns (results, data_source, session_start, session_end)."""
    conn = connect(db)
    try:
        row = conn.execute(
            "SELECT * FROM backtests WHERE id = ?", (backtest_id,)
        ).fetchone()
        if row is None:
            return None
        trade_rows = conn.execute(
            "SELECT * FROM trades WHERE backtest_id = ? ORDER BY seq", (backtest_id,)
        ).fetchall()
    finally:
        conn.close()

    scalars = {n: row[n] for n in RESULT_COLUMNS}
    for name in _DATE_FIELDS:
        if scalars.get(name):
            scalars[name] = datetime.fromisoformat(scalars[name])

    trades = []
    for t in trade_rows:
        d = {c: t[c] for c in TRADE_COLUMNS}
        for name in _TRADE_DATE_FIELDS:
            d[name] = datetime.fromisoformat(d[name]) if d[name] else None
        trades.append(Trade(**d))

    bd = _blob_dir(backtest_id)
    equity = pd.Series(dtype="float64")
    if (bd / EQUITY).is_file():
        equity = pd.read_parquet(bd / EQUITY)["equity"]
    prices = pd.DataFrame()
    if (bd / PRICES).is_file():
        prices = pd.read_parquet(bd / PRICES)

    # The row counts are recorded so a truncated sidecar is noticed rather than
    # served as a shorter chart with no explanation.
    if len(equity) != row["equity_rows"]:
        log.warning("backtest %s: equity.parquet has %d rows, expected %d",
                    backtest_id, len(equity), row["equity_rows"])
    if len(prices) != row["price_rows"]:
        log.warning("backtest %s: prices.parquet has %d rows, expected %d",
                    backtest_id, len(prices), row["price_rows"])

    results = BacktestResults(**scalars, trades=trades,
                              equity_curve=equity, price_data=prices)
    return (results, row["data_source"],
            time_type.fromisoformat(row["session_start"]),
            time_type.fromisoformat(row["session_end"]))


def list_ids(db: Path | None = None) -> list[str]:
    """Every backtest id, newest first."""
    conn = connect(db)
    try:
        return [r["id"] for r in conn.execute(
            "SELECT id FROM backtests ORDER BY created_at DESC, id DESC")]
    finally:
        conn.close()


def summaries(symbol: str | None = None, min_sharpe: float | None = None,
              since: str | None = None, limit: int = 100,
              db: Path | None = None) -> list[dict]:
    """Rows across runs -- the question a database is here to answer.

    `since` is an ISO date string compared against created_at.
    """
    sql = ["SELECT id, created_at, symbol, strategy_name, timeframe, total_pnl,",
           "       total_return_pct, sharpe_ratio, max_drawdown_pct, win_rate,",
           "       total_trades FROM backtests WHERE 1 = 1"]
    args: list = []
    if symbol:
        sql.append("AND symbol = ?")
        args.append(symbol)
    if min_sharpe is not None:
        sql.append("AND sharpe_ratio >= ?")
        args.append(min_sharpe)
    if since:
        sql.append("AND created_at >= ?")
        args.append(since)
    sql.append("ORDER BY created_at DESC LIMIT ?")
    args.append(limit)

    conn = connect(db)
    try:
        return [dict(r) for r in conn.execute(" ".join(sql), args)]
    finally:
        conn.close()


def delete(backtest_id: str, db: Path | None = None) -> bool:
    """Remove a result and its sidecars. True if the row existed."""
    conn = connect(db)
    try:
        cur = conn.execute("DELETE FROM backtests WHERE id = ?", (backtest_id,))
        existed = cur.rowcount > 0
    finally:
        conn.close()

    d = _blob_dir(backtest_id)
    if d.is_dir():
        shutil.rmtree(d, ignore_errors=True)
        existed = True
    return existed
