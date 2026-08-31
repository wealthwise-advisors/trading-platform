"""Saved configurations, data export, onboarding, and a throttle that survives a restart.

Registered in tests/conftest.py's _SECURITY_SUITES. That is not optional here:
half this file signs in as two DIFFERENT people and asserts neither can reach
the other's configurations. Under the session-wide require_user override both
clients resolve to the same TEST_USER, so every one of those assertions would
pass while testing nothing -- the exact failure that set exists to prevent.
"""

import json

import pytest
from fastapi.testclient import TestClient

from api import auth
from api.main import app
from db import connection
from db import users as repo

PASSWORD = "Correct-Horse-99-Battery"


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "account.db")
    monkeypatch.setattr(auth, "throttle", auth.Throttle())
    monkeypatch.setattr(auth, "signup_throttle", auth.SignupThrottle())
    monkeypatch.setattr(auth, "_INSECURE", True)
    return tmp_path


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        yield c


def make_user(username="trader", email="t@example.com") -> int:
    return repo.create_user(username, auth.hash_password(PASSWORD),
                            full_name="A Trader", email=email,
                            email_verified=True, country="IN")


def sign_in(client, username="trader"):
    r = client.post("/api/auth/login",
                    json={"username": username, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r


def as_user(username, db_fixture):
    """A second client, signed in as someone else, sharing the same database."""
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return c


# ── saved configurations: the round trip ─────────────────────────────────────

def test_save_list_update_and_delete(client, db):
    make_user()
    sign_in(client)

    assert client.get("/api/account/configs").json() == []

    r = client.put("/api/account/configs/My%20Setup",
                   json={"config": {"symbol": "ES", "timeframe": "5m"}})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "My Setup"

    listed = client.get("/api/account/configs").json()
    assert len(listed) == 1
    assert listed[0]["config"] == {"symbol": "ES", "timeframe": "5m"}

    # Saving the same name replaces rather than duplicating.
    client.put("/api/account/configs/My%20Setup",
               json={"config": {"symbol": "NQ", "timeframe": "1m"}})
    listed = client.get("/api/account/configs").json()
    assert len(listed) == 1
    assert listed[0]["config"]["symbol"] == "NQ"

    assert client.delete("/api/account/configs/My%20Setup").status_code == 200
    assert client.get("/api/account/configs").json() == []


def test_configs_survive_a_new_session(client, db):
    """Sign out, sign back in -- the whole point of moving these off the device."""
    make_user()
    sign_in(client)
    client.put("/api/account/configs/Kept", json={"config": {"symbol": "ES"}})

    client.post("/api/auth/logout")
    assert client.get("/api/account/configs").status_code == 401

    sign_in(client)
    assert [c["name"] for c in client.get("/api/account/configs").json()] == ["Kept"]


def test_a_second_device_sees_the_same_configs(client, db):
    """A different client with its own cookie jar: the second-device case."""
    make_user()
    sign_in(client)
    client.put("/api/account/configs/Shared", json={"config": {"symbol": "ES"}})

    other_device = as_user("trader", db)
    assert [c["name"] for c in other_device.get("/api/account/configs").json()] == ["Shared"]


def test_deleting_an_unknown_name_is_404(client, db):
    make_user()
    sign_in(client)
    assert client.delete("/api/account/configs/never-existed").status_code == 404


def test_an_oversized_payload_is_refused(client, db):
    make_user()
    sign_in(client)
    r = client.put("/api/account/configs/Huge",
                   json={"config": {"blob": "x" * 70_000}})
    assert r.status_code == 400
    assert "too large" in r.json()["detail"].lower()


# ── saved configurations: isolation ──────────────────────────────────────────

def test_one_user_cannot_list_anothers_configs(client, db):
    make_user("alice", "a@example.com")
    make_user("bob", "b@example.com")

    alice = as_user("alice", db)
    alice.put("/api/account/configs/Alices", json={"config": {"symbol": "ES"}})

    bob = as_user("bob", db)
    assert bob.get("/api/account/configs").json() == []


def test_one_user_cannot_delete_anothers_config(client, db):
    """A name they do not own is 404, not 403 -- a 403 would confirm it exists."""
    make_user("alice", "a@example.com")
    make_user("bob", "b@example.com")
    alice = as_user("alice", db)
    alice.put("/api/account/configs/Secret", json={"config": {"symbol": "ES"}})

    bob = as_user("bob", db)
    assert bob.delete("/api/account/configs/Secret").status_code == 404

    # And Alice still has it.
    assert [c["name"] for c in alice.get("/api/account/configs").json()] == ["Secret"]


def test_the_same_name_is_two_different_configs(client, db):
    """The primary key is (user_id, name), so a common name is not a collision."""
    make_user("alice", "a@example.com")
    make_user("bob", "b@example.com")
    alice, bob = as_user("alice", db), as_user("bob", db)

    alice.put("/api/account/configs/Default", json={"config": {"symbol": "ES"}})
    bob.put("/api/account/configs/Default", json={"config": {"symbol": "NQ"}})

    assert alice.get("/api/account/configs").json()[0]["config"]["symbol"] == "ES"
    assert bob.get("/api/account/configs").json()[0]["config"]["symbol"] == "NQ"


def test_configs_are_refused_to_anonymous_callers(client, db):
    make_user()
    assert client.get("/api/account/configs").status_code == 401
    assert client.put("/api/account/configs/x", json={"config": {}}).status_code == 401
    assert client.delete("/api/account/configs/x").status_code == 401


def test_closing_the_account_takes_the_configs_with_it(client, db):
    """The gap that moving these server-side was partly meant to close."""
    uid = make_user()
    sign_in(client)
    client.put("/api/account/configs/Doomed", json={"config": {"symbol": "ES"}})

    repo.delete_account(uid)

    conn = connection.connect()
    try:
        left = conn.execute("SELECT COUNT(*) AS n FROM user_configs").fetchone()["n"]
    finally:
        conn.close()
    assert left == 0


# ── data export ──────────────────────────────────────────────────────────────

def test_export_returns_the_accounts_own_data(client, db):
    make_user()
    sign_in(client)
    client.put("/api/account/configs/Exported", json={"config": {"symbol": "ES"}})

    r = client.get("/api/auth/export")

    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")
    body = r.json()
    assert body["account"]["username"] == "trader"
    assert [c["name"] for c in body["saved_configs"]] == ["Exported"]
    for key in ("sessions", "oauth_identities", "backtests", "trades"):
        assert key in body


def test_export_never_carries_credentials(client, db):
    """A hash is a key, not a fact about a person, and this file gets emailed."""
    make_user()
    sign_in(client)

    body = client.get("/api/auth/export").json()

    assert "password_hash" not in body["account"]
    blob = json.dumps(body)
    assert "argon2" not in blob
    assert "$argon2id$" not in blob
    for session in body["sessions"]:
        assert "token_hash" not in session


def test_export_is_only_ever_your_own(client, db):
    make_user("alice", "a@example.com")
    make_user("bob", "b@example.com")
    bob = as_user("bob", db)

    body = bob.get("/api/auth/export").json()

    # No parameter names an account, so the closest thing to an attack is
    # asking and seeing whose data comes back.
    assert body["account"]["username"] == "bob"


def test_export_is_refused_to_anonymous_callers(client, db):
    make_user()
    assert client.get("/api/auth/export").status_code == 401


# ── onboarding ───────────────────────────────────────────────────────────────

def test_a_new_account_is_not_onboarded(client, db):
    make_user()
    r = sign_in(client)
    assert r.json()["onboarded"] is False


def test_finishing_onboarding_sticks(client, db):
    make_user()
    sign_in(client)

    assert client.post("/api/auth/onboarded").status_code == 200
    assert client.get("/api/auth/me").json()["onboarded"] is True

    # And across a new session, which localStorage could never do.
    client.post("/api/auth/logout")
    assert sign_in(client).json()["onboarded"] is True


def test_finishing_twice_does_not_move_the_date(client, db):
    uid = make_user()
    sign_in(client)
    client.post("/api/auth/onboarded")

    conn = connection.connect()
    try:
        first = conn.execute("SELECT onboarded_at FROM users WHERE id = ?",
                             (uid,)).fetchone()["onboarded_at"]
    finally:
        conn.close()

    client.post("/api/auth/onboarded")

    conn = connection.connect()
    try:
        second = conn.execute("SELECT onboarded_at FROM users WHERE id = ?",
                              (uid,)).fetchone()["onboarded_at"]
    finally:
        conn.close()
    assert first == second


def test_onboarding_is_refused_to_anonymous_callers(client, db):
    assert client.post("/api/auth/onboarded").status_code == 401


# ── the throttle, which now outlives the process ─────────────────────────────

def test_the_throttle_blocks_after_the_sixth_failure(client, db):
    make_user()
    for _ in range(auth.Throttle.MAX_FAILS):
        client.post("/api/auth/login",
                    json={"username": "trader", "password": "wrong"})

    r = client.post("/api/auth/login",
                    json={"username": "trader", "password": PASSWORD})

    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_the_block_survives_a_restart(client, db):
    """The regression. A dict lost this on every deploy; a table does not."""
    make_user()
    for _ in range(auth.Throttle.MAX_FAILS):
        client.post("/api/auth/login",
                    json={"username": "trader", "password": "wrong"})

    # A brand-new Throttle instance is what a restarted process gets.
    fresh = auth.Throttle()

    assert fresh.retry_after("testclient", "trader") > 0


def test_a_success_clears_only_the_pair_budget(client, db):
    make_user()
    ip = "1.2.3.4"
    for _ in range(3):
        auth.throttle.record_failure(ip, "trader")
    auth.throttle.record_success(ip, "trader")

    assert auth.throttle.retry_after(ip, "trader") == 0
    conn = connection.connect()
    try:
        # The pair row is gone; the per-IP ceiling deliberately is not.
        keys = {r["scope_key"] for r in conn.execute(
            "SELECT scope_key FROM login_attempts")}
    finally:
        conn.close()
    assert f"pair:{ip}|trader" not in keys
    assert f"ip:{ip}" in keys


def test_the_pair_key_does_not_let_one_ip_lock_out_an_account(db):
    """Keying on the pair is what stops a stranger locking someone else out."""
    make_user()
    for _ in range(auth.Throttle.MAX_FAILS):
        auth.throttle.record_failure("attacker-ip", "trader")

    assert auth.throttle.retry_after("attacker-ip", "trader") > 0
    assert auth.throttle.retry_after("the-real-owner-ip", "trader") == 0


def test_purge_clears_only_what_can_no_longer_block(db):
    make_user()
    auth.throttle.record_failure("1.2.3.4", "trader")
    assert repo.purge_login_attempts() == 0        # too recent to drop
    conn = connection.connect()
    try:
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM login_attempts").fetchone()["n"] == 2
    finally:
        conn.close()
