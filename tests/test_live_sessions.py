"""The paper-trading endpoints, driven the way a browser drives them.

The dashboard pushes closed bars. That makes the interesting failures network
failures rather than trading ones: a reload that re-sends bars, two tabs
pushing the same bar, a laptop that sleeps mid-session. Each of those turns
into a duplicate order if nothing stops it, so each has a test here.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routers import live as live_router

T0 = datetime(2026, 9, 18, 9, 30)


@pytest.fixture(autouse=True)
def _clean_sessions():
    live_router._SESSIONS.clear()
    yield
    live_router._SESSIONS.clear()


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A scratch database."""
    from db import connection
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "live.db")
    return tmp_path


def _visitor() -> TestClient:
    """A browser opening the app. No sign-in: every request is the workspace."""
    c = TestClient(app)
    c.__enter__()
    return c


@pytest.fixture
def client(db):
    c = _visitor()
    yield c
    c.__exit__(None, None, None)


def _start(c, **kw):
    body = {"strategy_id": "rsi_divergence", "symbol": "ES",
            "params": {}, "contracts": 1}
    body.update(kw)
    return c.post("/api/live/start", json=body)


def _bar(c, minute, close=4500.0):
    t = (T0 + timedelta(minutes=minute)).isoformat()
    return c.post("/api/live/bar", json={"t": t, "o": close, "h": close + 1,
                                         "l": close - 1, "c": close, "v": 100})


# ── the routes refuse other websites ──────────────────────────────────────
#: Sign-in was removed on 2026-10-16, so there is no "anonymous caller" to
#: refuse any more. What every route still refuses is a state-changing request
#: from ANOTHER WEBSITE -- the cross-origin check in api/auth.py, which matters
#: more without sign-in, since nothing else stops a page elsewhere from driving
#: paper trades through a visitor's browser.
@pytest.mark.parametrize("path,body", [
    ("/api/live/start",
     {"strategy_id": "rsi_divergence", "symbol": "ES", "params": {}, "contracts": 1}),
    ("/api/live/bar", {"t": "2026-09-18T09:30:00", "o": 1, "h": 1, "l": 1, "c": 1}),
    ("/api/live/heartbeat", None),
    ("/api/live/stop", None),
])
def test_every_live_route_refuses_another_website(client, path, body):
    r = client.post(path, headers={"Origin": "https://evil.example"},
                    **({"json": body} if body is not None else {}))
    assert r.status_code == 403, f"{path} -> {r.status_code} {r.text[:80]}"


def test_the_same_site_is_let_through(client):
    """The other half: the check must not refuse the app itself."""
    r = client.post(
        "/api/live/start", headers={"Origin": "http://testserver"},
        json={"strategy_id": "rsi_divergence", "symbol": "ES", "params": {}, "contracts": 1})
    assert r.status_code == 200, r.text


# ── lifecycle ─────────────────────────────────────────────────────────────
def test_status_with_no_session_is_idle_not_an_error(client):
    """The dashboard polls this on every load; a 404 on the ordinary case
    would fill the console with noise that means nothing."""
    r = client.get("/api/live/status")
    assert r.status_code == 200
    assert r.json()["running"] is False


def test_starting_a_session_reports_paper_mode(client):
    r = _start(client)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["running"] is True
    assert body["mode"] == "paper"
    assert body["symbol"] == "ES"


def test_a_second_session_is_refused_while_one_runs(client):
    """Two sessions would trade one account from two places, and whichever
    filled first would leave the other acting on a stale position."""
    _start(client)
    r = _start(client)
    assert r.status_code == 409


def test_stopping_then_starting_again_is_allowed(client):
    _start(client)
    assert client.post("/api/live/stop").status_code == 200
    assert _start(client).status_code == 200


def test_stop_with_no_session_is_a_404(client):
    assert client.post("/api/live/stop").status_code == 404


def test_an_unknown_strategy_is_refused(client):
    assert _start(client, strategy_id="does_not_exist").status_code == 400


def test_an_absurd_order_size_is_refused_at_the_boundary(client):
    """Bounded here as well as in the guard -- a request for 10,000 contracts
    should never get as far as constructing a session."""
    assert _start(client, contracts=10_000).status_code == 422


# ── duplicate bars ────────────────────────────────────────────────────────
def test_the_same_bar_twice_is_counted_once(client):
    _start(client)
    _bar(client, 0)
    first = _bar(client, 0).json()
    assert first["bars_seen"] == 1
    assert first["duplicates_ignored"] == 1


def test_an_out_of_order_bar_is_ignored(client):
    """Arrival order is not bar order: a retry can land after a newer bar."""
    _start(client)
    _bar(client, 5)
    body = _bar(client, 3).json()
    assert body["bars_seen"] == 1
    assert body["duplicates_ignored"] == 1


def test_a_reconnect_replaying_recent_bars_changes_nothing(client):
    """THE RELOAD CASE. A dashboard coming back re-sends what it has; none of
    it may re-open the trades those bars already caused."""
    _start(client)
    for m in range(5):
        _bar(client, m)
    after_first_pass = client.get("/api/live/status").json()

    for m in range(5):                      # the reload, replaying the lot
        _bar(client, m)
    after_replay = client.get("/api/live/status").json()

    assert after_replay["bars_seen"] == after_first_pass["bars_seen"]
    assert after_replay["orders_sent"] == after_first_pass["orders_sent"]
    assert after_replay["position"] == after_first_pass["position"]
    assert after_replay["duplicates_ignored"] == 5


def test_a_new_bar_after_a_replay_is_still_processed(client):
    """Deduplication must not wedge the session shut."""
    _start(client)
    _bar(client, 0)
    _bar(client, 0)
    body = _bar(client, 1).json()
    assert body["bars_seen"] == 2


def test_an_unparseable_bar_time_is_refused(client):
    _start(client)
    r = client.post("/api/live/bar",
                       json={"t": "not-a-time", "o": 1, "h": 1, "l": 1, "c": 1})
    assert r.status_code == 400


def test_pushing_a_bar_with_no_session_is_a_404(client):
    assert _bar(client, 0).status_code == 404


# ── disconnect ────────────────────────────────────────────────────────────
def test_a_session_whose_dashboard_went_quiet_is_stopped(client, monkeypatch):
    """A closed tab does not get to say goodbye -- it can be killed, slept or
    dropped -- so the session watches for silence instead."""
    _start(client)
    monkeypatch.setattr(live_router, "STALE_AFTER_SECONDS", -1.0)
    body = client.get("/api/live/status").json()
    assert body["running"] is False
    assert "disconnected" in " ".join(e["text"] for e in body["events"])


def test_a_heartbeat_keeps_a_quiet_session_alive(client):
    """Bars can be minutes apart; without this a session on a 5m chart would
    look abandoned for most of its life."""
    _start(client)
    assert client.post("/api/live/heartbeat").json()["running"] is True
    assert client.get("/api/live/status").json()["running"] is True


def test_bars_pushed_after_a_disconnect_do_not_restart_trading(client, monkeypatch):
    """A tab that wakes up late must not resume trading on its own."""
    _start(client)
    monkeypatch.setattr(live_router, "STALE_AFTER_SECONDS", -1.0)
    client.get("/api/live/status")                 # reaps it
    before = client.get("/api/live/status").json()["orders_sent"]
    body = _bar(client, 9).json()
    assert body["running"] is False
    assert body["orders_sent"] == before


# ── one shared workspace ──────────────────────────────────────────────────
def test_a_second_visitor_sees_the_same_session(client):
    """There is one workspace, so there is one paper session, seen by everyone.

    This used to assert the opposite -- one account's session invisible to
    another -- and that stopped being possible when sign-in was removed. Pinned
    here so the shared behaviour is a stated fact rather than a surprise: two
    people with the link are driving the same paper account.
    """
    _start(client)
    other = _visitor()
    try:
        assert other.get("/api/live/status").json()["running"] is True
    finally:
        other.__exit__(None, None, None)
