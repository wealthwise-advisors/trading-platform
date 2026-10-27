"""POST /api/poc-average -- the Chart page's swing flags, from Market Grid's bars.

The endpoint must compute from EXACTLY the bars a Market Grid session with
the same settings holds, or a swing could be flagged on the Chart page for a
match Market Grid never shows. So the main test builds a real Market Grid
session, takes its panes' bars, and checks the endpoint's answer against
poc_average_at run on those.
"""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import replay_store
from api.main import app
from src.analysis.poc_average import poc_average_at

client = TestClient(app)

TFS = ["1m", "5m", "15m"]
SETUP = {"symbol": "ES", "data_source": "synthetic",
         "start_date": "2026-08-17", "end_date": "2026-08-18",
         "session_start": None, "session_end": None}


def _moments(n: int = 4) -> list[str]:
    """A few moments inside the synthetic session (it starts 09:30 on day one)."""
    base = pd.Timestamp("2026-08-17 10:30")
    return [(base + pd.Timedelta(minutes=45 * i)).isoformat() for i in range(n)]


def test_matches_market_grid_panes_exactly():
    r = client.post("/api/replay", json={**SETUP, "timeframes": TFS, "strategy_id": "rsi_divergence"})
    assert r.status_code == 200, r.text
    session = replay_store.get(r.json()["replay_id"]).session
    panes = {tf: session.panes[tf].df for tf in TFS}
    want = poc_average_at(panes, [pd.Timestamp(m) for m in _moments()])

    got = client.post("/api/poc-average", json={**SETUP, "timeframes": TFS, "moments": _moments()})
    assert got.status_code == 200, got.text
    rows = got.json()["moments"]
    assert len(rows) == len(want)
    for g, w in zip(rows, want):
        assert g["pocs"] == pytest.approx(w["pocs"])
        assert g["average"] == pytest.approx(w["average"])
        assert g["matches"] == w["matches"]


def test_each_moment_reports_average_pocs_and_matches():
    got = client.post("/api/poc-average", json={**SETUP, "timeframes": TFS, "moments": _moments(2)})
    assert got.status_code == 200, got.text
    for row in got.json()["moments"]:
        assert set(row) >= {"t", "average", "pocs", "matches"}
        if row["average"] is not None:
            assert row["average"] == pytest.approx(sum(row["pocs"].values()) / len(row["pocs"]))
            for tf in row["matches"]:
                assert int(row["pocs"][tf]) == int(row["average"])


def test_defaults_to_the_eleven_timeframes_one_minute_to_one_hour():
    got = client.post("/api/poc-average", json={**SETUP, "moments": _moments(1)})
    assert got.status_code == 200, got.text
    assert got.json()["timeframes"] == [
        "1m", "3m", "5m", "10m", "15m", "20m", "25m", "30m", "35m", "45m", "1h"]


def test_rejects_an_unknown_timeframe():
    got = client.post("/api/poc-average", json={**SETUP, "timeframes": ["7m"], "moments": _moments(1)})
    assert got.status_code == 422
