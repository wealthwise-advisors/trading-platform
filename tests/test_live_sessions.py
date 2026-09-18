"""The paper-trading endpoints, driven the way a browser drives them.

The dashboard pushes closed bars. That makes the interesting failures network
failures rather than trading ones: a reload that re-sends bars, two tabs
pushing the same bar, a laptop that sleeps mid-session. Each of those turns
into a duplicate order if nothing stops it, so each has a test here.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from api import auth
from api.main import app
from api.routers import live as live_router

T0 = datetime(2026, 9, 18, 9, 30)
PASSWORD = "Correct-Horse-99"


@pytest.fixture(autouse=True)
def _clean_sessions():
    live_router._SESSIONS.clear()
    yield
    live_router._SESSIONS.clear()


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A scratch database, and cookies that survive http://testserver.

    auth._INSECURE is the same switch tests/test_isolation.py flips: without
    it the session cookie is marked Secure and a TestClient talking plain HTTP
    never sends it back, so every request after the login is anonymous. This
    module runs against the REAL guard (see _SECURITY_SUITES in conftest), so
    that would look exactly like the guard rejecting a signed-in user.
    """
    from db import connection
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "live.db")
    monkeypatch.setattr(auth, "_INSECURE", True)
    return tmp_path


def _sign_in(username: str) -> TestClient:
    from db import users as user_repo
    user_repo.create_user(username, auth.hash_password(PASSWORD))
    c = TestClient(app)
    c.__enter__()
    r = c.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert r.status_code == 200, f"{username} could not sign in: {r.text}"
    return c


@pytest.fixture
def signed_in(db):
    """A real account and a real cookie -- these routes are guarded."""
    return _sign_in("live-check")


def _start(c, **kw):
    body = {"strategy_id": "rsi_divergence", "symbol": "ES",
            "params": {}, "contracts": 1}
    body.update(kw)
    return c.post("/api/live/start", json=body)


def _bar(c, minute, close=4500.0):
    t = (T0 + timedelta(minutes=minute)).isoformat()
    return c.post("/api/live/bar", json={"t": t, "o": close, "h": close + 1,
                                         "l": close - 1, "c": close, "v": 100})


# ── the routes are guarded ────────────────────────────────────────────────
@pytest.mark.parametrize("method,path,body", [
    ("post", "/api/live/start",
     {"strategy_id": "rsi_divergence", "symbol": "ES", "params": {}, "contracts": 1}),
    ("post", "/api/live/bar", {"t": "2026-09-18T09:30:00", "o": 1, "h": 1, "l": 1, "c": 1}),
    ("post", "/api/live/heartbeat", None),
    ("post", "/api/live/stop", None),
    ("get", "/api/live/status", None),
])
def test_every_live_route_refuses_an_anonymous_caller(method, path, body):
    anon = TestClient(app)
    r = getattr(anon, method)(path, **({"json": body} if body is not None else {}))
    assert r.status_code == 401, f"{path} -> {r.status_code} {r.text[:80]}"


# ── lifecycle ─────────────────────────────────────────────────────────────
def test_status_with_no_session_is_idle_not_an_error(signed_in):
    """The dashboard polls this on every load; a 404 on the ordinary case
    would fill the console with noise that means nothing."""
    r = signed_in.get("/api/live/status")
    assert r.status_code == 200
    assert r.json()["running"] is False


def test_starting_a_session_reports_paper_mode(signed_in):
    r = _start(signed_in)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["running"] is True
    assert body["mode"] == "paper"
    assert body["symbol"] == "ES"


def test_a_second_session_is_refused_while_one_runs(signed_in):
    """Two sessions would trade one account from two places, and whichever
    filled first would leave the other acting on a stale position."""
    _start(signed_in)
    r = _start(signed_in)
    assert r.status_code == 409


def test_stopping_then_starting_again_is_allowed(signed_in):
    _start(signed_in)
    assert signed_in.post("/api/live/stop").status_code == 200
    assert _start(signed_in).status_code == 200


def test_stop_with_no_session_is_a_404(signed_in):
    assert signed_in.post("/api/live/stop").status_code == 404


def test_an_unknown_strategy_is_refused(signed_in):
    assert _start(signed_in, strategy_id="does_not_exist").status_code == 400


def test_an_absurd_order_size_is_refused_at_the_boundary(signed_in):
    """Bounded here as well as in the guard -- a request for 10,000 contracts
    should never get as far as constructing a session."""
    assert _start(signed_in, contracts=10_000).status_code == 422


# ── duplicate bars ────────────────────────────────────────────────────────
def test_the_same_bar_twice_is_counted_once(signed_in):
    _start(signed_in)
    _bar(signed_in, 0)
    first = _bar(signed_in, 0).json()
    assert first["bars_seen"] == 1
    assert first["duplicates_ignored"] == 1


def test_an_out_of_order_bar_is_ignored(signed_in):
    """Arrival order is not bar order: a retry can land after a newer bar."""
    _start(signed_in)
    _bar(signed_in, 5)
    body = _bar(signed_in, 3).json()
    assert body["bars_seen"] == 1
    assert body["duplicates_ignored"] == 1


def test_a_reconnect_replaying_recent_bars_changes_nothing(signed_in):
    """THE RELOAD CASE. A dashboard coming back re-sends what it has; none of
    it may re-open the trades those bars already caused."""
    _start(signed_in)
    for m in range(5):
        _bar(signed_in, m)
    after_first_pass = signed_in.get("/api/live/status").json()

    for m in range(5):                      # the reload, replaying the lot
        _bar(signed_in, m)
    after_replay = signed_in.get("/api/live/status").json()

    assert after_replay["bars_seen"] == after_first_pass["bars_seen"]
    assert after_replay["orders_sent"] == after_first_pass["orders_sent"]
    assert after_replay["position"] == after_first_pass["position"]
    assert after_replay["duplicates_ignored"] == 5


def test_a_new_bar_after_a_replay_is_still_processed(signed_in):
    """Deduplication must not wedge the session shut."""
    _start(signed_in)
    _bar(signed_in, 0)
    _bar(signed_in, 0)
    body = _bar(signed_in, 1).json()
    assert body["bars_seen"] == 2


def test_an_unparseable_bar_time_is_refused(signed_in):
    _start(signed_in)
    r = signed_in.post("/api/live/bar",
                       json={"t": "not-a-time", "o": 1, "h": 1, "l": 1, "c": 1})
    assert r.status_code == 400


def test_pushing_a_bar_with_no_session_is_a_404(signed_in):
    assert _bar(signed_in, 0).status_code == 404


# ── disconnect ────────────────────────────────────────────────────────────
def test_a_session_whose_dashboard_went_quiet_is_stopped(signed_in, monkeypatch):
    """A closed tab does not get to say goodbye -- it can be killed, slept or
    dropped -- so the session watches for silence instead."""
    _start(signed_in)
    monkeypatch.setattr(live_router, "STALE_AFTER_SECONDS", -1.0)
    body = signed_in.get("/api/live/status").json()
    assert body["running"] is False
    assert "disconnected" in " ".join(e["text"] for e in body["events"])


def test_a_heartbeat_keeps_a_quiet_session_alive(signed_in):
    """Bars can be minutes apart; without this a session on a 5m chart would
    look abandoned for most of its life."""
    _start(signed_in)
    assert signed_in.post("/api/live/heartbeat").json()["running"] is True
    assert signed_in.get("/api/live/status").json()["running"] is True


def test_bars_pushed_after_a_disconnect_do_not_restart_trading(signed_in, monkeypatch):
    """A tab that wakes up late must not resume trading on its own."""
    _start(signed_in)
    monkeypatch.setattr(live_router, "STALE_AFTER_SECONDS", -1.0)
    signed_in.get("/api/live/status")                 # reaps it
    before = signed_in.get("/api/live/status").json()["orders_sent"]
    body = _bar(signed_in, 9).json()
    assert body["running"] is False
    assert body["orders_sent"] == before


# ── isolation ─────────────────────────────────────────────────────────────
def test_one_users_session_is_invisible_to_another(signed_in):
    """Sessions are per account. Under the conftest override both clients
    would resolve to one user and this would pass while proving nothing --
    which is why this module is in _SECURITY_SUITES."""
    _start(signed_in)
    other = _sign_in("other-live")
    assert other.get("/api/live/status").json()["running"] is False
