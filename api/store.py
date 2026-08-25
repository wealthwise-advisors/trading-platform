"""Backtest result store, keyed by backtest_id.

Results are held in memory and also written to disk, so a restart no longer
throws away every result the user has run. Reads come from memory when the
result is still there and fall back to disk when it is not.

WHY FILES AND NOT A DATABASE
----------------------------
The access pattern is: write one result, read it back by its exact id, never
search it. That is a key-value lookup, and every database would be bought for
features this never uses -- joins, concurrent writers, replication -- while
charging for a server to run, a schema to migrate and backups to remember.

A result is also mostly two pandas objects: the equity curve and the full
OHLCV frame for the range. Those do not become rows without someone deciding
how, which is the part of "just add SQLite" that is not small. Parquet stores
them as what they already are, with dtypes and the DatetimeIndex intact.

So: one directory per backtest, a JSON manifest for the scalars and the
trades, and Parquet for the two frames. If this ever needs to answer questions
ACROSS runs -- every ES backtest with Sharpe above 1.5 since March -- that is
when a real database earns its place. Storing blobs by id does not.

FAILING SOFT, ON PURPOSE
------------------------
Persistence must never be able to break a backtest. Every disk operation here
is wrapped: if the directory is unwritable, the disk is full, or a file is
corrupt, the store logs it and carries on as the in-memory cache it has always
been. A failed write loses history; a raised exception would lose the run.
"""

import json
import logging
import os
import shutil
import uuid
from dataclasses import dataclass, fields
from datetime import datetime
from datetime import time as time_type
from pathlib import Path

import pandas as pd

from src.backtesting.results import BacktestResults, Trade

log = logging.getLogger(__name__)

#: Override with AUTOTRADER_STORE_DIR to point at a mounted volume in Docker.
STORE_DIR = Path(os.environ.get("AUTOTRADER_STORE_DIR", "data/backtests"))

MANIFEST = "meta.json"
EQUITY = "equity.parquet"
PRICES = "prices.parquet"

#: Bumped when the on-disk shape changes in a way older files cannot satisfy.
FORMAT_VERSION = 1

# Everything on BacktestResults that is neither a DataFrame/Series nor the
# trade list. Derived from the dataclass rather than typed out, so a metric
# added later is persisted without anyone remembering to update this file.
_FRAME_FIELDS = {"equity_curve", "price_data", "trades"}
_SCALAR_FIELDS = [f.name for f in fields(BacktestResults) if f.name not in _FRAME_FIELDS]
_DATE_FIELDS = {"start_date", "end_date"}
_TRADE_DATE_FIELDS = {"entry_time", "exit_time"}


@dataclass
class StoredBacktest:
    results: BacktestResults
    data_source: str
    session_start: time_type
    session_end: time_type


_store: dict[str, StoredBacktest] = {}


# ── serialisation ────────────────────────────────────────────────────────────
def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def _manifest(stored: StoredBacktest) -> dict:
    r = stored.results
    return {
        "format_version": FORMAT_VERSION,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "data_source": stored.data_source,
        "session_start": _iso(stored.session_start),
        "session_end": _iso(stored.session_end),
        "results": {n: _iso(getattr(r, n)) for n in _SCALAR_FIELDS},
        "trades": [
            {f.name: _iso(getattr(t, f.name)) for f in fields(Trade)}
            for t in r.trades
        ],
    }


def _revive(m: dict, equity: pd.Series, prices: pd.DataFrame) -> StoredBacktest:
    scalars = dict(m["results"])
    for name in _DATE_FIELDS:
        if scalars.get(name):
            scalars[name] = datetime.fromisoformat(scalars[name])

    trades = []
    for d in m.get("trades", []):
        d = dict(d)
        for name in _TRADE_DATE_FIELDS:
            if d.get(name):
                d[name] = datetime.fromisoformat(d[name])
        trades.append(Trade(**d))

    results = BacktestResults(
        **scalars, trades=trades, equity_curve=equity, price_data=prices
    )
    return StoredBacktest(
        results=results,
        data_source=m.get("data_source", "synthetic"),
        session_start=time_type.fromisoformat(m["session_start"]),
        session_end=time_type.fromisoformat(m["session_end"]),
    )


# ── disk ─────────────────────────────────────────────────────────────────────
def _write(backtest_id: str, stored: StoredBacktest) -> None:
    d = STORE_DIR / backtest_id
    d.mkdir(parents=True, exist_ok=True)
    r = stored.results

    # A Series has no parquet writer of its own; one named column round-trips
    # the values and the DatetimeIndex without inventing a second format.
    if r.equity_curve is not None and len(r.equity_curve):
        r.equity_curve.to_frame(name="equity").to_parquet(d / EQUITY)
    if r.price_data is not None and not r.price_data.empty:
        r.price_data.to_parquet(d / PRICES)

    # The manifest is written last and to a temp name first: a half-written
    # manifest is the one thing that would make a directory look complete and
    # load wrong. If the process dies mid-write, the directory has no manifest
    # and _read skips it.
    tmp = d / (MANIFEST + ".tmp")
    tmp.write_text(json.dumps(_manifest(stored), indent=1), encoding="utf-8")
    tmp.replace(d / MANIFEST)


def _read(backtest_id: str) -> StoredBacktest | None:
    d = STORE_DIR / backtest_id
    mf = d / MANIFEST
    if not mf.is_file():
        return None
    m = json.loads(mf.read_text(encoding="utf-8"))
    if m.get("format_version") != FORMAT_VERSION:
        log.warning("backtest %s written by format v%s, this build reads v%s -- skipping",
                    backtest_id, m.get("format_version"), FORMAT_VERSION)
        return None

    equity = pd.Series(dtype="float64")
    if (d / EQUITY).is_file():
        equity = pd.read_parquet(d / EQUITY)["equity"]
    prices = pd.DataFrame()
    if (d / PRICES).is_file():
        prices = pd.read_parquet(d / PRICES)
    return _revive(m, equity, prices)


# ── api ──────────────────────────────────────────────────────────────────────
def save(results: BacktestResults, data_source: str, session_start: time_type,
        session_end: time_type) -> str:
    backtest_id = f"AT-{uuid.uuid4().hex[:10]}"
    stored = StoredBacktest(results, data_source, session_start, session_end)
    _store[backtest_id] = stored
    try:
        _write(backtest_id, stored)
    except Exception:
        # The run itself succeeded and is in memory; only its history is lost.
        log.exception("could not persist backtest %s -- serving from memory only",
                      backtest_id)
    return backtest_id


def get(backtest_id: str) -> StoredBacktest | None:
    stored = _store.get(backtest_id)
    if stored is not None:
        return stored
    try:
        stored = _read(backtest_id)
    except Exception:
        log.exception("could not load backtest %s from disk", backtest_id)
        return None
    if stored is not None:
        _store[backtest_id] = stored     # warm the cache for the next endpoint
    return stored


def list_ids() -> list[str]:
    """Every backtest id on disk, newest first. Ids only in memory are included."""
    seen: dict[str, float] = {}
    try:
        for d in STORE_DIR.iterdir():
            mf = d / MANIFEST
            if mf.is_file():
                seen[d.name] = mf.stat().st_mtime
    except FileNotFoundError:
        pass
    except Exception:
        log.exception("could not list %s", STORE_DIR)
    for bid in _store:
        seen.setdefault(bid, 0.0)
    return sorted(seen, key=lambda b: seen[b], reverse=True)


def delete(backtest_id: str) -> bool:
    """Drop a result from memory and disk. True if anything was there."""
    had = _store.pop(backtest_id, None) is not None
    d = STORE_DIR / backtest_id
    try:
        if d.is_dir():
            shutil.rmtree(d)
            had = True
    except Exception:
        log.exception("could not delete backtest %s from disk", backtest_id)
    return had
