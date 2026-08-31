"""Closing an account actually closes it.

WHY THIS SUITE EXISTS
---------------------
`repo.delete_user` deletes the users row and nothing else, and SQLite REFUSED
it for anyone who had ever run a backtest: `backtests.user_id` references that
row with no ON DELETE action, so the default NO ACTION applies and the delete
raises IntegrityError. The command therefore worked only on accounts that had
never used the product -- which is to say, it worked on nobody who would ever
ask.

web/public/privacy.html §6 promises deletion on request, so that was a promise
the code could not keep. `repo.delete_account` deals with the dependents first;
these tests hold it to that, and the FK regression is asserted directly so it
cannot come back quietly.

Registered in tests/conftest.py's _SECURITY_SUITES: several tests here assert a
REFUSAL, and under the session-wide require_user override they would pass
without reaching the guard.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from api import auth
from api.main import app
from db import backtests as blobs
from db import connection
from db import users as repo


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A scratch database, fresh throttles, and sidecars under tmp_path."""
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "accounts.db")
    monkeypatch.setattr(blobs, "BLOB_DIR", tmp_path / "backtests")
    monkeypatch.setattr(auth, "throttle", auth.Throttle())
    monkeypatch.setattr(auth, "signup_throttle", auth.SignupThrottle())
    monkeypatch.setattr(auth, "_INSECURE", True)     # TestClient speaks http://
    return tmp_path


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        yield c


PASSWORD = "Correct-Horse-99-Battery"


def make_user(username="trader", email="") -> int:
    return repo.create_user(username, auth.hash_password(PASSWORD),
                            full_name="A Trader", email=email, country="IN")


def sign_in(client, username=PASSWORD and "trader", password=PASSWORD):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r


def add_backtest(user_id: int, backtest_id: str, *, trades: int = 0) -> None:
    """A row in `backtests` owned by user_id, plus optional `trades` children.

    Columns are filled from PRAGMA rather than typed out, so this keeps working
    when the results table gains a metric -- which it does, guarded by its own
    test. What matters here is ownership and the foreign key, not the numbers.
    """
    conn = connection.connect()
    try:
        def filler(table, overrides):
            cols, vals = [], []
            for r in conn.execute(f"PRAGMA table_info({table})"):
                name, decl, notnull, pk = r[1], (r[2] or "").upper(), r[3], r[5]
                if name in overrides:
                    cols.append(name)
                    vals.append(overrides[name])
                elif notnull and not pk:
                    cols.append(name)
                    vals.append(0 if decl in {"REAL", "INTEGER"} else "x")
            return cols, vals

        cols, vals = filler("backtests", {"id": backtest_id, "user_id": user_id})
        conn.execute(f"INSERT INTO backtests ({','.join(cols)}) "
                     f"VALUES ({','.join('?' * len(cols))})", vals)
        # `seq` is half of the composite primary key, so PRAGMA reports it as a
        # pk column and the filler skips it -- it still has to be supplied, and
        # distinctly, or the second trade collides with the first.
        for seq in range(trades):
            cols, vals = filler("trades", {"backtest_id": backtest_id,
                                           "seq": seq,
                                           "user_id": user_id})
            conn.execute(f"INSERT INTO trades ({','.join(cols)}) "
                         f"VALUES ({','.join('?' * len(cols))})", vals)
    finally:
        conn.close()


def counts():
    conn = connection.connect()
    try:
        return {t: conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
                for t in ("users", "backtests", "trades", "sessions")}
    finally:
        conn.close()


# ── the regression this suite was written for ────────────────────────────────

def test_bare_delete_user_still_refuses_an_owner(db):
    """The old path is unchanged, and still raises. Proof the FK is real.

    If this ever stops raising, the schema gained a cascade and the reasoning
    in db/schema.sql:30 was overruled somewhere -- which is a decision, not a
    detail, and should not happen silently.
    """
    uid = make_user()
    add_backtest(uid, "bt-owned")
    with pytest.raises(sqlite3.IntegrityError):
        repo.delete_user("trader")


def test_delete_account_removes_an_owner_with_backtests(db):
    uid = make_user()
    add_backtest(uid, "bt-1", trades=3)
    add_backtest(uid, "bt-2", trades=2)

    removed = repo.delete_account(uid)

    assert removed["backtests"] == 2
    assert removed["trades"] == 5
    assert counts() == {"users": 0, "backtests": 0, "trades": 0, "sessions": 0}


def test_delete_account_on_a_brand_new_account(db):
    uid = make_user()
    assert repo.delete_account(uid)["backtests"] == 0
    assert counts()["users"] == 0


def test_delete_account_is_none_for_an_unknown_id(db):
    make_user()
    assert repo.delete_account(9999) is None
    assert counts()["users"] == 1


def test_keep_results_detaches_instead_of_deleting(db):
    """The operator's escape hatch: the rows outlive the account, ownerless."""
    uid = make_user()
    add_backtest(uid, "bt-keep", trades=2)

    removed = repo.delete_account(uid, keep_results=True)

    assert removed["backtests"] == 0
    assert removed["backtests_detached"] == 1
    c = counts()
    assert c["users"] == 0 and c["backtests"] == 1 and c["trades"] == 2

    conn = connection.connect()
    try:
        owner = conn.execute("SELECT user_id FROM backtests").fetchone()["user_id"]
    finally:
        conn.close()
    assert owner is None


def test_one_users_deletion_leaves_the_others_data_alone(db):
    mine = make_user("mine")
    theirs = make_user("theirs")
    add_backtest(mine, "bt-mine", trades=2)
    add_backtest(theirs, "bt-theirs", trades=4)

    repo.delete_account(mine)

    conn = connection.connect()
    try:
        left = [r["id"] for r in conn.execute("SELECT id FROM backtests")]
        trades = conn.execute("SELECT COUNT(*) AS n FROM trades").fetchone()["n"]
    finally:
        conn.close()
    assert left == ["bt-theirs"]
    assert trades == 4
    assert repo.get_user("theirs") is not None


def test_sidecars_are_removed_with_the_account(db):
    uid = make_user()
    add_backtest(uid, "bt-blob")
    d = blobs.BLOB_DIR / "bt-blob"
    d.mkdir(parents=True)
    (d / "equity.parquet").write_bytes(b"not really parquet")

    removed = repo.delete_account(uid)
    blobs.purge_blobs(removed["backtest_ids"])

    assert not d.exists()


def test_database_is_still_consistent_afterwards(db):
    """No dangling user_id anywhere, and the FK check has nothing to say."""
    uid = make_user()
    other = make_user("other")
    add_backtest(uid, "bt-a", trades=2)
    add_backtest(other, "bt-b", trades=1)

    repo.delete_account(uid)

    conn = connection.connect()
    try:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        orphans = conn.execute(
            "SELECT COUNT(*) AS n FROM backtests b "
            "LEFT JOIN users u ON u.id = b.user_id "
            "WHERE b.user_id IS NOT NULL AND u.id IS NULL").fetchone()["n"]
    finally:
        conn.close()
    assert orphans == 0


# ── the HTTP route ───────────────────────────────────────────────────────────

def test_route_refuses_an_anonymous_caller(client):
    r = client.request("DELETE", "/api/auth/me",
                       json={"confirm": "trader", "password": PASSWORD})
    assert r.status_code == 401


def test_route_closes_the_account_and_its_data(client, db):
    uid = make_user()
    add_backtest(uid, "bt-http", trades=3)
    sign_in(client)

    r = client.request("DELETE", "/api/auth/me",
                       json={"confirm": "trader", "password": PASSWORD})

    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "backtests": 1, "trades": 3}
    assert counts() == {"users": 0, "backtests": 0, "trades": 0, "sessions": 0}


def test_the_session_is_dead_immediately_afterwards(client, db):
    make_user()
    sign_in(client)
    assert client.get("/api/auth/me").status_code == 200

    client.request("DELETE", "/api/auth/me",
                   json={"confirm": "trader", "password": PASSWORD})

    # The same client, still holding whatever the server left it.
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/strategies").status_code == 401


def test_a_closed_account_cannot_sign_in_again(client, db):
    make_user()
    sign_in(client)
    client.request("DELETE", "/api/auth/me",
                   json={"confirm": "trader", "password": PASSWORD})

    r = client.post("/api/auth/login",
                    json={"username": "trader", "password": PASSWORD})
    assert r.status_code == 401


def test_a_wrong_password_does_not_close_the_account(client, db):
    make_user()
    sign_in(client)

    r = client.request("DELETE", "/api/auth/me",
                       json={"confirm": "trader", "password": "not-the-password"})

    assert r.status_code == 401
    assert counts()["users"] == 1
    assert client.get("/api/auth/me").status_code == 200   # still signed in


def test_the_username_must_be_typed(client, db):
    make_user()
    sign_in(client)

    r = client.request("DELETE", "/api/auth/me",
                       json={"confirm": "", "password": PASSWORD})

    assert r.status_code == 400
    assert counts()["users"] == 1


def test_confirming_someone_elses_name_does_not_reach_them(client, db):
    """There is no parameter that aims this at another account.

    The identity comes from the session, so the closest thing to an attempt is
    typing somebody else's username into the confirmation box -- which fails
    the confirmation check rather than deleting either account.
    """
    make_user("mine")
    victim = make_user("victim")
    add_backtest(victim, "bt-victim")
    sign_in(client, "mine")

    r = client.request("DELETE", "/api/auth/me",
                       json={"confirm": "victim", "password": PASSWORD})

    assert r.status_code == 400
    assert repo.get_user("victim") is not None
    assert repo.get_user("mine") is not None


def test_an_oauth_only_account_closes_without_a_password(client, db):
    """No password to re-enter, so the typed username is the confirmation."""
    uid = repo.create_user("googler", auth.hash_password("unreachable-by-design"),
                           email="g@example.com", email_verified=True,
                           has_password=False)
    add_backtest(uid, "bt-oauth")
    token = repo.new_session(uid)
    client.cookies.set(auth.COOKIE, token)

    r = client.request("DELETE", "/api/auth/me",
                       json={"confirm": "googler", "password": ""})

    assert r.status_code == 200, r.text
    assert counts()["users"] == 0
