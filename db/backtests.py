"""Reading and writing backtest results.

The only module that knows the table layout. api/store.py talks to this and
nothing else, so the SQL stays in one place and the routers never see a cursor.

OWNERSHIP
---------
Every function here takes a user_id and every statement filters on it. It is a
REQUIRED argument with no default on purpose: a default would make the unscoped
call the easy one to write, and the whole failure mode this guards against is
someone forgetting to pass it. Omitting it is a TypeError at import-time-ish
speed rather than a leak discovered later.

A miss and a not-yours are deliberately indistinguishable here -- both come
back as None/False/empty. Distinguishing them would tell an attacker which
backtest ids exist, which is the same enumeration weakness the login endpoint
avoids by refusing unknown users and wrong passwords identically.
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
           session_start: time_type, session_end: time_type, user_id: int,
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
        user_id=user_id,
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

        # INSERT OR REPLACE overwrites whatever holds this id. Ids are minted
        # server-side from uuid4 so a collision is not reachable today, but
        # "not reachable today" is how a rewrite turns into someone else's
        # result being silently replaced. Refuse rather than rely on that.
        existing = conn.execute(
            "SELECT user_id FROM backtests WHERE id = ?", (backtest_id,)
        ).fetchone()
        if existing is not None and existing["user_id"] != user_id:
            raise PermissionError(
                f"backtest {backtest_id} belongs to another user"
            )

        conn.execute(sql, row)
        conn.execute("DELETE FROM trades WHERE backtest_id = ?", (backtest_id,))
        conn.executemany(
            f"INSERT INTO trades (backtest_id, seq, user_id, {', '.join(TRADE_COLUMNS)}) "
            f"VALUES (?, ?, ?, {', '.join('?' for _ in TRADE_COLUMNS)})",
            [
                (backtest_id, i, user_id,
                 *[_iso(getattr(t, c)) for c in TRADE_COLUMNS])
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
def fetch(backtest_id: str, user_id: int, db: Path | None = None):
    """One result, or None. Returns (results, data_source, session_start, session_end).

    None covers both "no such backtest" and "not yours" -- see the module
    docstring for why those must look the same from outside.
    """
    conn = connect(db)
    try:
        row = conn.execute(
            "SELECT * FROM backtests WHERE id = ? AND user_id = ?",
            (backtest_id, user_id),
        ).fetchone()
        if row is None:
            return None
        # Filtered on user_id as well as backtest_id. The parent row has
        # already been checked, so this is redundant -- and it is the redundancy
        # that makes a stray trades row belonging to someone else unreturnable
        # even if the two tables ever disagree.
        trade_rows = conn.execute(
            "SELECT * FROM trades WHERE backtest_id = ? AND user_id = ? ORDER BY seq",
            (backtest_id, user_id),
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


def list_ids(user_id: int, db: Path | None = None) -> list[str]:
    """This user's backtest ids, newest first."""
    conn = connect(db)
    try:
        return [r["id"] for r in conn.execute(
            "SELECT id FROM backtests WHERE user_id = ? "
            "ORDER BY created_at DESC, id DESC", (user_id,))]
    finally:
        conn.close()


def summaries(user_id: int, symbol: str | None = None,
              min_sharpe: float | None = None,
              since: str | None = None, limit: int = 100,
              db: Path | None = None) -> list[dict]:
    """Rows across this user's runs -- the question a database is here to answer.

    `since` is an ISO date string compared against created_at.

    user_id leads the signature rather than sitting among the optional filters
    because it is not a filter: the others narrow a result set, this one
    defines whose result set it is.
    """
    sql = ["SELECT id, created_at, symbol, strategy_name, timeframe, total_pnl,",
           "       total_return_pct, sharpe_ratio, max_drawdown_pct, win_rate,",
           "       total_trades FROM backtests WHERE user_id = ?"]
    args: list = [user_id]
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


def delete(backtest_id: str, user_id: int, db: Path | None = None) -> bool:
    """Remove this user's result and its sidecars. True if the row existed.

    False for someone else's backtest, and the Parquet sidecars are left alone
    in that case -- an unscoped rmtree would destroy another user's charts even
    though the row survived, which is a worse outcome than the leak this is
    guarding.
    """
    conn = connect(db)
    try:
        cur = conn.execute(
            "DELETE FROM backtests WHERE id = ? AND user_id = ?",
            (backtest_id, user_id),
        )
        existed = cur.rowcount > 0
    finally:
        conn.close()

    if not existed:
        return False

    d = _blob_dir(backtest_id)
    if d.is_dir():
        shutil.rmtree(d, ignore_errors=True)
    return True
