"""Thin SQLite helper for the Independent Industry Benchmark (Task 9).
Same pattern as validation/db.py -- entirely outside src/ and api/.
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path(__file__).parent / "benchmark.db"
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db(path: Path = DB_PATH) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_SCHEMA_PATH.read_text())
        conn.commit()
    finally:
        conn.close()


@contextmanager
def connect(path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def fetch_all(conn: sqlite3.Connection, query: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, params).fetchall()]
