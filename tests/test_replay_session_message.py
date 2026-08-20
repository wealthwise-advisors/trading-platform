"""
The message shown when the session window empties the frame.

This path is hit by a real person most mornings: they open Live Replay before
09:30 ET, the default session window filters every overnight bar away, and the
API refuses. Whether that reads as "the app is broken" or "change this one
setting" is entirely down to the wording, so the wording is tested.
"""
from datetime import datetime, timedelta, timezone

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

ET = timezone(timedelta(hours=-4))


def _bars(n: int, start: datetime, minutes: int = 5) -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq=f"{minutes}min")
    return pd.DataFrame(
        {"open": 4500.0, "high": 4501.0, "low": 4499.0, "close": 4500.5,
         "volume": 100},
        index=idx,
    )


def test_before_the_open_it_names_the_24_hour_setting(monkeypatch):
    """
    The overnight bars exist; only the window hides them. The message has to
    say so, because "wait for the open" implies there is nothing to watch.
    """
    from api.routers import replay as mod

    # 03:35 ET -- six hours before the open, with a night session behind us.
    now = datetime(2026, 8, 20, 3, 35, tzinfo=ET)
    monkeypatch.setattr(mod, "_market_now", lambda: now)
    monkeypatch.setattr(
        mod, "_load_bars",
        lambda req, tf, spec: _bars(43, datetime(2026, 8, 20, 0, 0)),
    )

    r = client.post("/api/replay", json={
        "symbol": "ES", "timeframe": "5m", "data_source": "schwab",
        "strategy_id": "rsi_divergence",
        "start_date": "2026-08-20", "end_date": "2026-08-20",
        "session_start": "09:30:00", "session_end": "16:00:00",
    })
    assert r.status_code == 400
    detail = r.json()["detail"]

    assert "has not opened yet" in detail
    assert "03:35 ET" in detail
    # The two things that make it actionable rather than merely accurate.
    assert "43 bars" in detail, detail
    assert "24 hours" in detail, detail


def test_with_nothing_overnight_it_does_not_invent_bars(monkeypatch):
    """An instrument that really has no bars must not be told to try 24 hours."""
    from api.routers import replay as mod

    now = datetime(2026, 8, 20, 3, 35, tzinfo=ET)
    monkeypatch.setattr(mod, "_market_now", lambda: now)
    monkeypatch.setattr(mod, "_load_bars", lambda req, tf, spec: _bars(0, datetime(2026, 8, 20)))

    r = client.post("/api/replay", json={
        "symbol": "ES", "timeframe": "5m", "data_source": "schwab",
        "strategy_id": "rsi_divergence",
        "start_date": "2026-08-20", "end_date": "2026-08-20",
        "session_start": "09:30:00", "session_end": "16:00:00",
    })
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "has not opened yet" in detail
    assert "24 hours" not in detail, detail
    assert "Wait for the open" in detail
