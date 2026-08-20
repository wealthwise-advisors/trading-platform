"""
Setting up before the chosen session opens.

Someone who picks 09:30-16:00 has said which session they trade. Opening the
app at 03:00 to set up for it is normal, and the window being empty at that
moment is not a mistake. The app used to refuse and tell them to switch to
24-hour hours -- which meant abandoning the setting they had deliberately
chosen just to get the app to work at all.

It now creates the session and waits.
"""
from datetime import datetime, timedelta, timezone

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)
ET = timezone(timedelta(hours=-4))


def _bars(n: int, start: datetime, minutes: int = 1) -> pd.DataFrame:
    if n == 0:
        return pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"],
            index=pd.DatetimeIndex([], name="timestamp"),
        ).astype(float)
    idx = pd.date_range(start, periods=n, freq=f"{minutes}min")
    return pd.DataFrame(
        {"open": 4500.0, "high": 4501.0, "low": 4499.0, "close": 4500.5,
         "volume": 100.0},
        index=idx,
    )


def _post(**over):
    body = {
        "symbol": "ES", "timeframe": "5m", "data_source": "schwab",
        "strategy_id": "rsi_divergence",
        "start_date": "2026-08-20", "end_date": "2026-08-20",
        "session_start": "09:30:00", "session_end": "16:00:00",
    }
    body.update(over)
    return client.post("/api/replay", json=body)


def test_before_the_open_the_session_is_created_and_waits(monkeypatch):
    """The chosen window is respected; nobody is told to change it."""
    from api.routers import replay as mod

    # 03:35 ET, with a night session behind us that this window excludes.
    monkeypatch.setattr(mod, "_market_now",
                        lambda: datetime(2026, 8, 20, 3, 35, tzinfo=ET))
    monkeypatch.setattr(mod, "_load_bars",
                        lambda req, tf, spec: _bars(215, datetime(2026, 8, 20, 0, 0)))

    r = _post()
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["replay_id"]
    # Nothing has printed inside 09:30-16:00 yet, so the tape starts empty and
    # fills in as the open arrives.
    assert body["total_bars"] == 0


def test_any_chosen_window_is_equally_respected(monkeypatch):
    """
    The fix must not be special-cased to the New York open. An evening window
    picked for any reason behaves the same way.

    Note this deliberately does NOT use 18:00-17:00: that window WRAPS midnight,
    so 09:00 is inside it and bars do exist -- an earlier version of this test
    asserted an empty tape for a session that was legitimately open.
    """
    from api.routers import replay as mod

    monkeypatch.setattr(mod, "_market_now",
                        lambda: datetime(2026, 8, 20, 9, 0, tzinfo=ET))
    monkeypatch.setattr(mod, "_load_bars",
                        lambda req, tf, spec: _bars(300, datetime(2026, 8, 20, 4, 0)))

    r = _post(session_start="20:00:00", session_end="23:00:00")
    assert r.status_code == 200, r.text
    assert r.json()["total_bars"] == 0


def test_a_range_with_no_bars_at_all_is_still_an_error(monkeypatch):
    """
    Waiting only makes sense for a session that is going to open. A weekend, a
    holiday or a window this instrument never trades must still say so rather
    than hand back a tape that will never fill.
    """
    from api.routers import replay as mod

    # 14:00 ET -- the window is OPEN and still produced nothing.
    monkeypatch.setattr(mod, "_market_now",
                        lambda: datetime(2026, 8, 20, 14, 0, tzinfo=ET))
    monkeypatch.setattr(mod, "_load_bars",
                        lambda req, tf, spec: _bars(0, datetime(2026, 8, 20)))

    r = _post()
    assert r.status_code == 400
    assert "No ES bars" in r.json()["detail"]


def test_a_past_date_before_the_open_time_is_not_treated_as_waiting(monkeypatch):
    """
    "Before the open" is only meaningful for today. Asking for last Tuesday and
    getting nothing is an error, not something to sit and wait for.
    """
    from api.routers import replay as mod

    monkeypatch.setattr(mod, "_market_now",
                        lambda: datetime(2026, 8, 20, 3, 35, tzinfo=ET))
    monkeypatch.setattr(mod, "_load_bars",
                        lambda req, tf, spec: _bars(0, datetime(2026, 8, 11)))

    r = _post(start_date="2026-08-11", end_date="2026-08-11")
    assert r.status_code == 400
