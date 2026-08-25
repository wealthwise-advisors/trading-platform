"""Backtest result store, keyed by backtest_id.

An in-memory cache in front of the SQLite database in `db/`. Results are
written there on save and read back on a miss, so a restart no longer throws
away every result the user has run.

WHY THERE IS STILL A CACHE
--------------------------
Loading a result means one row, its trades, and reading two Parquet files back
into pandas. A single dashboard page view hits six endpoints against the same
backtest_id, so without the cache that work happens six times for one screen.
The database is the record; the dict is what keeps a page load cheap.

WHAT LIVES WHERE
----------------
Scalars and trades are rows in SQLite -- they are the parts you can ask
questions about, and `db.backtests.summaries()` exists for exactly that. The
equity curve and the OHLCV frame stay as Parquet beside the database; the note
at the top of db/schema.sql explains why they are not shredded into rows.

FAILING SOFT, ON PURPOSE
------------------------
Persistence must never break a backtest. Every database call here is wrapped:
an unwritable directory, a locked file, a missing parquet engine -- all of it
logs and carries on as the in-memory cache. A failed write costs history; a
raised exception would cost the run that just finished.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import time as time_type

from db import backtests as repo
from src.backtesting.results import BacktestResults

log = logging.getLogger(__name__)


@dataclass
class StoredBacktest:
    results: BacktestResults
    data_source: str
    session_start: time_type
    session_end: time_type


_store: dict[str, StoredBacktest] = {}


def save(results: BacktestResults, data_source: str, session_start: time_type,
        session_end: time_type) -> str:
    backtest_id = f"AT-{uuid.uuid4().hex[:10]}"
    _store[backtest_id] = StoredBacktest(results, data_source, session_start,
                                         session_end)
    try:
        repo.insert(backtest_id, results, data_source, session_start, session_end)
    except Exception:
        # The run succeeded and is in memory; only its history is lost.
        log.exception("could not persist backtest %s -- serving from memory only",
                      backtest_id)
    return backtest_id


def get(backtest_id: str) -> StoredBacktest | None:
    stored = _store.get(backtest_id)
    if stored is not None:
        return stored
    try:
        found = repo.fetch(backtest_id)
    except Exception:
        log.exception("could not load backtest %s from the database", backtest_id)
        return None
    if found is None:
        return None
    stored = StoredBacktest(*found)
    _store[backtest_id] = stored          # warm the cache for the next endpoint
    return stored


def list_ids() -> list[str]:
    """Every backtest id, newest first. Ids only in memory are included."""
    try:
        ids = repo.list_ids()
    except Exception:
        log.exception("could not list backtests")
        ids = []
    for bid in _store:
        if bid not in ids:
            ids.append(bid)
    return ids


def summaries(**kw) -> list[dict]:
    """Query across runs -- symbol, min_sharpe, since, limit. See db.backtests."""
    try:
        return repo.summaries(**kw)
    except Exception:
        log.exception("could not query backtest summaries")
        return []


def delete(backtest_id: str) -> bool:
    """Drop a result from the cache and the database. True if anything was there."""
    had = _store.pop(backtest_id, None) is not None
    try:
        had = repo.delete(backtest_id) or had
    except Exception:
        log.exception("could not delete backtest %s", backtest_id)
    return had
