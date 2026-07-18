"""Thin SQLite helper for the Expert Chart Validation Framework (Task 8).
No ORM -- the schema is small and stable enough that plain SQL stays more
readable than an abstraction layer would. Entirely outside src/ and api/.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

DB_PATH = Path(__file__).parent / "validation.db"
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


def insert_chart(conn: sqlite3.Connection, *, market: str, timeframe: str, start_date: str,
                 end_date: str, bar_count: int, data_source: str,
                 price_csv_path: Optional[str]) -> str:
    chart_id = new_id("chart")
    conn.execute(
        "INSERT INTO charts (chart_id, market, timeframe, start_date, end_date, bar_count, "
        "data_source, price_csv_path, fetched_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (chart_id, market, timeframe, start_date, end_date, bar_count, data_source,
        price_csv_path, now_iso()),
    )
    return chart_id


def insert_analysis(conn: sqlite3.Connection, *, chart_id: str, degree: str, n_swings: int,
                    bias: str, cycle_position: str, primary_count: list, alternates: list,
                    impulse_quality: Optional[float], corrective_quality: Optional[float],
                    triangle_quality: Optional[float], diagonal_quality: Optional[float],
                    confidence: Optional[float], recursive_verification: list,
                    rule_violations: list, warnings: list, notes: list) -> str:
    analysis_id = new_id("analysis")
    conn.execute(
        "INSERT INTO analyses (analysis_id, chart_id, degree, n_swings, bias, cycle_position, "
        "primary_count_json, alternate_counts_json, impulse_quality, corrective_quality, "
        "triangle_quality, diagonal_quality, confidence, recursive_verification_json, "
        "rule_violations_json, warnings_json, notes_json, analyzed_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (analysis_id, chart_id, degree, n_swings, bias, cycle_position,
        json.dumps(primary_count), json.dumps(alternates), impulse_quality, corrective_quality,
        triangle_quality, diagonal_quality, confidence, json.dumps(recursive_verification),
        json.dumps(rule_violations), json.dumps(warnings), json.dumps(notes), now_iso()),
    )
    return analysis_id


def insert_review(conn: sqlite3.Connection, *, analysis_id: str, reviewer: str, verdict: str,
                  false_positive: bool = False, false_negative: bool = False,
                  mis_numbering: bool = False, wrong_degree: bool = False,
                  missed_triangle: bool = False, missed_diagonal: bool = False,
                  wrong_correction: bool = False, notes: str = "") -> str:
    review_id = new_id("review")
    conn.execute(
        "INSERT INTO reviews (review_id, analysis_id, reviewer, verdict, false_positive, "
        "false_negative, mis_numbering, wrong_degree, missed_triangle, missed_diagonal, "
        "wrong_correction, notes, reviewed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (review_id, analysis_id, reviewer, verdict, int(false_positive), int(false_negative),
        int(mis_numbering), int(wrong_degree), int(missed_triangle), int(missed_diagonal),
        int(wrong_correction), notes, now_iso()),
    )
    return review_id


def fetch_all(conn: sqlite3.Connection, query: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, params).fetchall()]
