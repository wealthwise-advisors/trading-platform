"""In-memory backtest result cache, keyed by backtest_id.

Fine for a single-process dev server (matches Streamlit's own st.session_state
model — one process, one user). A real multi-user deployment would swap this
for Redis/a DB; not needed for this rewrite's scope.
"""

import uuid
from dataclasses import dataclass
from datetime import time as time_type

from src.backtesting.results import BacktestResults


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
    _store[backtest_id] = StoredBacktest(results, data_source, session_start, session_end)
    return backtest_id


def get(backtest_id: str) -> StoredBacktest | None:
    return _store.get(backtest_id)
