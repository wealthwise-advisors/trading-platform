"""The application was open to the internet. These tests hold it shut.

The point is not that a login screen exists -- it is that every route refuses
an anonymous caller, including the websocket, which does not run the router's
HTTP dependencies and is the usual thing left open.
"""

import re
import sqlite3

import pytest
from fastapi.testclient import TestClient

from api import auth
from api.main import app
from db import connection
from db import users as repo


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A scratch database, and a throttle that has not seen anything."""
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "auth.db")
    monkeypatch.setattr(auth, "throttle", auth.Throttle())
    monkeypatch.setattr(auth, "_INSECURE", True)   # TestClient speaks http://
    return tmp_path


@pytest.fixture
def user(db):
    repo.create_user("trader", auth.hash_password("Correct-Horse-99"),
                     full_name="A Trader", email="t@example.com", country="IN")
    return "trader", "Correct-Horse-99"


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        yield c


def login(client, username, password):
    return client.post("/api/auth/login",
                       json={"username": username, "password": password})


# ── passwords ────────────────────────────────────────────────────────────────
def test_password_is_never_stored_in_plaintext(db):
    repo.create_user("x", auth.hash_password("Correct-Horse-99"))
    stored = repo.get_user("x").password_hash
    assert "Correct-Horse-99" not in stored
    assert stored.startswith("$argon2id$"), "must be argon2id"
    assert auth.verify_password(stored, "Correct-Horse-99")
    assert not auth.verify_password(stored, "correct-horse-99")


def test_same_password_hashes_differently(db):
    """Per-user salt: two accounts with one password must not look alike."""
    a, b = auth.hash_password("Correct-Horse-99"), auth.hash_password("Correct-Horse-99")
    assert a != b


@pytest.mark.parametrize("pw,ok", [
    ("short", False), ("alllowercaseletters", False), ("Password1234", True),
    ("N0t-Bad-Enough!", True), ("aaaaaaaaaaaa", False),
])
def test_password_strength_is_checked_server_side(pw, ok):
    assert (auth.password_problem(pw) is None) is ok


# ── sessions ─────────────────────────────────────────────────────────────────
def test_session_token_is_stored_only_as_a_hash(db, user):
    uid = repo.get_user("trader").id
    raw = repo.new_session(uid)
    conn = connection.connect()
    rows = [r["token_hash"] for r in conn.execute("SELECT token_hash FROM sessions")]
    conn.close()
    assert raw not in rows, "the raw cookie value must never be in the table"
    assert repo.hash_token(raw) in rows


def test_expired_session_stops_resolving(db, user, monkeypatch):
    from datetime import timedelta
    monkeypatch.setattr(repo, "SESSION_TTL", timedelta(seconds=-1))
    raw = repo.new_session(repo.get_user("trader").id)
    assert repo.resolve_session(raw) is None


def test_disabling_an_account_kills_its_sessions(db, user):
    raw = repo.new_session(repo.get_user("trader").id)
    assert repo.resolve_session(raw) is not None
    repo.set_active("trader", False)
    assert repo.resolve_session(raw) is None


# ── login ────────────────────────────────────────────────────────────────────
def test_login_succeeds_and_sets_an_httponly_cookie(client, user):
    r = login(client, *user)
    assert r.status_code == 200
    assert r.json()["username"] == "trader"

    raw = r.headers.get("set-cookie", "")
    assert auth.COOKIE in raw
    assert "HttpOnly" in raw, "cookie must be unreadable from JavaScript"
    assert "samesite=lax" in raw.lower(), "must not ride along on cross-site POSTs"


def test_wrong_password_and_unknown_user_are_indistinguishable(client, user):
    a = login(client, "trader", "wrong-password-here")
    b = login(client, "nobody-at-all", "wrong-password-here")
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"], "response must not reveal existence"


def test_disabled_account_cannot_sign_in(client, user):
    repo.set_active("trader", False)
    assert login(client, *user).status_code == 401


def test_logout_revokes_the_session_server_side(client, user):
    login(client, *user)
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_a_stolen_cookie_is_useless_after_logout(client, user):
    login(client, *user)
    stolen = client.cookies.get(auth.COOKIE)
    client.post("/api/auth/logout")
    client.cookies.set(auth.COOKIE, stolen)          # replay it
    assert client.get("/api/auth/me").status_code == 401


# ── registration is closed on the server ─────────────────────────────────────
def test_registration_endpoint_refuses_everyone(client, db):
    r = client.post("/api/auth/register",
                    json={"username": "intruder", "password": "Correct-Horse-99"})
    assert r.status_code == 403
    assert repo.get_user("intruder") is None, "no account may be created"


# ── route protection ─────────────────────────────────────────────────────────
PUBLIC = {"/api/health", "/api/version",
          "/api/auth/login", "/api/auth/logout", "/api/auth/me", "/api/auth/register",
          # OAuth has to be reachable without a session -- that is the point of
          # it -- and the provider redirects the browser back to the callback
          # carrying none of our cookies. These defend themselves with a
          # single-use server-side state plus PKCE instead; see
          # tests/test_oauth_auth.py, which is where that is proven.
          "/api/auth/oauth/providers",
          "/api/auth/oauth/{name}/start",
          "/api/auth/oauth/{name}/callback"}


def _app_routes():
    """Every API path+method, taken from the OpenAPI schema.

    NOT from app.routes: this FastAPI version wraps an included router in an
    _IncludedRouter object that has no .path and no .methods, so filtering
    app.routes for those attributes collected the four /docs routes and
    nothing else -- and this sweep silently tested zero endpoints while
    reporting a pass. The schema is the app's own published surface.
    """
    schema = app.openapi()
    out = []
    for path, ops in schema["paths"].items():
        if not path.startswith("/api"):
            continue
        methods = {m.upper() for m in ops if m.lower() in
                   {"get", "post", "put", "patch", "delete"}}
        if methods:
            out.append((path, methods))
    assert len(out) >= 25, f"expected the full API surface, saw {len(out)}"
    return out


def test_every_api_route_is_either_public_or_guarded(client, db):
    """Enumerated from the app itself, so a route added later is covered."""
    unguarded = []
    for path, methods in _app_routes():
        if path in PUBLIC:
            continue
        url = re.sub(r"\{[^}]+\}", "test-id", path)
        method = "GET" if "GET" in methods else sorted(methods - {"HEAD", "OPTIONS"})[0]
        r = client.request(method, url, json={})
        # 401 is the point. 422 would mean the body was validated BEFORE the
        # guard ran, which still leaks that the endpoint exists and works.
        if r.status_code != 401:
            unguarded.append(f"{method} {path} -> {r.status_code}")
    assert not unguarded, "these answer an anonymous caller:\n  " + "\n  ".join(unguarded)


def test_health_and_version_stay_public(client, db):
    """The deploy asserts the running commit through /api/version before any
    human signs in; gating it would break the deployment gate."""
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/version").status_code == 200


def test_a_signed_in_caller_reaches_a_protected_route(client, user):
    assert client.get("/api/strategies").status_code == 401
    login(client, *user)
    assert client.get("/api/strategies").status_code == 200


# ── websocket ────────────────────────────────────────────────────────────────
def test_websocket_refuses_an_anonymous_connection(client, db):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect("/api/replay/ws/anything"):
            pass
    assert e.value.code == 1008, "policy violation, closed before accept()"


def test_websocket_accepts_a_signed_in_connection(client, user):
    """It must get past the auth gate. An unknown replay id is then reported
    as an application-level error, which is the correct next failure."""
    login(client, *user)
    with client.websocket_connect("/api/replay/ws/RP-nonexistent") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "not found" in msg["message"].lower()


# ── throttle ─────────────────────────────────────────────────────────────────
def test_repeated_failures_are_throttled(client, user):
    for _ in range(auth.Throttle.MAX_FAILS):
        login(client, "trader", "wrong-password-here")
    r = login(client, "trader", "wrong-password-here")
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0


def test_throttling_one_pair_cannot_lock_another_out(client, user):
    """Keying on username alone would let anyone lock a known account out."""
    t = auth.throttle
    for _ in range(t.MAX_FAILS):
        t.record_failure("10.0.0.1", "trader")
    assert t.retry_after("10.0.0.1", "trader") > 0      # the attacker
    assert t.retry_after("10.0.0.2", "trader") == 0     # the real user


def test_a_correct_login_clears_the_failure_count(client, user):
    for _ in range(auth.Throttle.MAX_FAILS - 1):
        login(client, "trader", "wrong-password-here")
    assert login(client, *user).status_code == 200
    assert auth.throttle.retry_after("testclient", "trader") == 0


# ── forwarded-for cannot be forged past the throttle ────────────────────────
def test_only_the_last_forwarded_hop_is_trusted():
    class Req:
        headers = {"x-forwarded-for": "1.2.3.4, 203.0.113.9"}
        client = None
    assert auth.client_ip(Req()) == "203.0.113.9", (
        "trusting the first entry would let a caller forge its own IP")


# ── the database keeps working ───────────────────────────────────────────────
def test_v1_database_upgrades_without_losing_data(tmp_path, monkeypatch):
    """An existing results database must gain the auth tables, not be replaced."""
    dbfile = tmp_path / "old.db"
    monkeypatch.setattr(connection, "DB_PATH", dbfile)
    conn = connection.connect()
    conn.execute("INSERT INTO backtests (id, created_at, symbol, strategy_name, "
                 "timeframe, start_date, end_date, initial_capital, data_source, "
                 "session_start, session_end, total_pnl, total_return_pct, "
                 "sharpe_ratio, sortino_ratio, max_drawdown_pct, win_rate, "
                 "profit_factor, avg_win, avg_loss, total_trades, winning_trades, "
                 "losing_trades, avg_trade_duration_min, final_capital) "
                 "VALUES ('AT-keepme','x','ES','MA','1m','x','x',1,'s','09:30','16:00',"
                 "0,0,0,0,0,0,0,0,0,0,0,0,0,0)")
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version, applied_at) VALUES (1,'x')")
    conn.close()

    conn = connection.connect()          # reopening runs the upgrade
    try:
        assert conn.execute("SELECT COUNT(*) c FROM backtests").fetchone()["c"] == 1
        names = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"users", "sessions"} <= names
        assert conn.execute("SELECT MAX(version) v FROM schema_version"
                            ).fetchone()["v"] == connection.SCHEMA_VERSION
    finally:
        conn.close()


def test_usernames_are_unique_case_insensitively(db):
    repo.create_user("Trader", auth.hash_password("Correct-Horse-99"))
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_user("trader", auth.hash_password("Correct-Horse-99"))
