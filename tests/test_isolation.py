"""One user must never reach another user's data.

Until schema v4 the backtests and trades tables had no owner column. Every
signed-in account could read, and delete, every result any other account had
ever produced. With a single administrator that was invisible; the moment
anyone can sign up it is the entire security model.

WHY THIS SUITE ENUMERATES RATHER THAN LISTING
---------------------------------------------
The obvious way to write this is to name the endpoints. That test passes
forever and protects nothing: the thirteenth sub-resource added next year is
not in the list, so the one route that leaks is the one nobody wrote a case
for. `_owned_routes()` reads the app's own OpenAPI schema instead, so a route
added later is covered on the day it is added, and a route added later that
leaks fails this suite without anyone remembering it exists.

WHY 404 AND NOT 403
-------------------
Someone else's backtest must be indistinguishable from one that does not
exist. A 403 confirms the id is real, which turns any of these endpoints into
an oracle for enumerating other people's runs -- the same reasoning that makes
/api/auth/login refuse an unknown username and a wrong password identically.

NOTE ON conftest.py
-------------------
This module is listed in _SECURITY_SUITES there. Without that it would run with
require_user overridden to a single fixed user, both clients would resolve to
the same person, and every assertion below would pass while proving nothing.
"""



import pytest
from fastapi.testclient import TestClient

from api import auth, store
from api.main import app
from db import backtests as bt_repo
from db import connection
from db import users as repo

# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A scratch database, an empty throttle, and an empty result cache.

    The store cache is module-level and survives between tests in one process,
    so it is cleared here -- otherwise a backtest saved by an earlier test
    could satisfy a later one from memory and the database filtering would
    never be exercised.
    """
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "isolation.db")
    monkeypatch.setattr(bt_repo, "BLOB_DIR", tmp_path / "blobs")
    monkeypatch.setattr(auth, "throttle", auth.Throttle())
    monkeypatch.setattr(auth, "_INSECURE", True)
    monkeypatch.setattr(store, "_store", {})
    return tmp_path


def _make(username: str, email: str) -> int:
    return repo.create_user(username, auth.hash_password("Correct-Horse-99"),
                            full_name=username.title(), email=email, country="IN")


def _sign_in(username: str) -> TestClient:
    c = TestClient(app)
    c.__enter__()
    r = c.post("/api/auth/login",
               json={"username": username, "password": "Correct-Horse-99"})
    assert r.status_code == 200, f"{username} could not sign in: {r.text}"
    return c


@pytest.fixture
def alice(db):
    _make("alice", "alice@example.com")
    c = _sign_in("alice")
    yield c
    c.__exit__(None, None, None)


@pytest.fixture
def bob(db):
    _make("bob", "bob@example.com")
    c = _sign_in("bob")
    yield c
    c.__exit__(None, None, None)


#: The cheapest run that still produces a real stored result with trades.
RUN = {
    "symbol": "ES", "strategy_id": "ma_crossover",
    "params": {"fast": 5, "slow": 20},
    "timeframe": "1h", "start_date": "2024-01-02", "end_date": "2024-02-01",
    "initial_capital": 100000, "data_source": "synthetic",
    "session_start": "09:30:00", "session_end": "16:00:00",
}


@pytest.fixture
def alice_backtest(alice) -> str:
    r = alice.post("/api/backtests", json=RUN)
    assert r.status_code == 200, r.text
    return r.json()["backtest_id"]


# ── the enumerating sweep ────────────────────────────────────────────────────


def _owned_routes() -> list[tuple[str, str]]:
    """Every API path that names a {backtest_id}, from the app's own schema.

    Taken from openapi() rather than app.routes: this FastAPI version wraps an
    included router in an object with no .path and no .methods, so filtering
    app.routes yields nothing and a sweep built that way silently tests zero
    endpoints while reporting a pass.
    """
    out = []
    for path, ops in app.openapi()["paths"].items():
        if "{backtest_id}" not in path:
            continue
        for method in ops:
            if method.lower() in {"get", "post", "put", "patch", "delete"}:
                out.append((method.upper(), path))
    assert len(out) >= 11, f"expected the backtest sub-resources, saw {len(out)}"
    return out


def test_no_backtest_route_serves_another_users_result(bob, alice_backtest):
    """The whole point. Every id-addressed route, swept, as the wrong user."""
    leaked = []
    for method, path in _owned_routes():
        url = path.replace("{backtest_id}", alice_backtest)
        r = bob.request(method, url)
        # 404 is the requirement. 200 is a leak. Anything else (422, 500) means
        # the handler ran far enough to process the id before deciding, which
        # is not a leak but is not the contract either.
        if r.status_code != 404:
            leaked.append(f"{method} {path} -> {r.status_code}")
    assert not leaked, (
        "these served, or acknowledged, another user's backtest:\n  "
        + "\n  ".join(leaked)
    )


def test_the_owner_can_still_read_every_one_of_those_routes(alice, alice_backtest):
    """The sweep above is only meaningful if these return 200 for the owner.

    Without this, deleting the feature entirely would make the isolation test
    pass.
    """
    broken = []
    for method, path in _owned_routes():
        url = path.replace("{backtest_id}", alice_backtest)
        r = alice.request(method, url)
        if r.status_code != 200:
            broken.append(f"{method} {path} -> {r.status_code}")
    assert not broken, "the owner cannot read their own result:\n  " + "\n  ".join(broken)


# ── listing, summarising, deleting ───────────────────────────────────────────


#: There is currently no collection route -- no GET /api/backtests listing and
#: no DELETE. store.list_ids / summaries / delete exist and are unused by HTTP.
#: They are tested at the store layer instead of through a route that does not
#: exist, because that is the layer any future listing endpoint would call, so
#: the isolation is already in place on the day someone adds one.
def test_listing_shows_only_your_own_runs(db, alice_backtest):
    """store.list_ids is what a listing endpoint would be built on."""
    alice_id = repo.get_user("alice").id
    bob_id = _make("bob2", "bob2@example.com")

    assert alice_backtest in store.list_ids(user_id=alice_id)
    assert store.list_ids(user_id=bob_id) == [], "another user's runs were listed"


def test_summaries_show_only_your_own_runs(db, alice_backtest):
    alice_id = repo.get_user("alice").id
    bob_id = _make("bob3", "bob3@example.com")

    mine = store.summaries(user_id=alice_id)
    assert any(r["id"] == alice_backtest for r in mine)
    assert store.summaries(user_id=bob_id) == [], "another user's runs were summarised"


def test_delete_cannot_reach_another_users_run(db, alice_backtest):
    alice_id = repo.get_user("alice").id
    bob_id = _make("bob4", "bob4@example.com")

    assert store.delete(alice_backtest, user_id=bob_id) is False
    # Still there afterwards -- a delete that reports "nothing here" while
    # actually deleting would be the worst of both outcomes.
    assert store.get(alice_backtest, user_id=alice_id) is not None


def test_deleting_your_own_run_still_works(db, alice_backtest):
    alice_id = repo.get_user("alice").id
    assert store.delete(alice_backtest, user_id=alice_id) is True
    assert store.get(alice_backtest, user_id=alice_id) is None


# ── the cache, which bypasses SQL entirely ───────────────────────────────────


def test_the_in_memory_cache_does_not_leak(bob, alice_backtest):
    """A cache hit returns before any query runs.

    Scoping the SQL alone would not have been enough: the result Alice just ran
    is in the process cache, and a lookup keyed by backtest_id alone would hand
    it to Bob without SQLite ever being consulted.
    """
    assert (1, alice_backtest) in store._store or any(
        bid == alice_backtest for _, bid in store._store
    ), "precondition: Alice's result should be cached in-process"
    assert bob.get(f"/api/backtests/{alice_backtest}").status_code == 404


# ── the repository layer, below the HTTP guard ───────────────────────────────


def test_repo_refuses_cross_user_reads(db):
    """Belt and braces: the leak must be closed below the router too."""
    a, b = _make("ra", "ra@example.com"), _make("rb", "rb@example.com")
    from tests._isolation_helpers import tiny_results

    bt_repo.insert("AT-owned", tiny_results(), "synthetic",
                   _t("09:30"), _t("16:00"), user_id=a)

    assert bt_repo.fetch("AT-owned", user_id=a) is not None
    assert bt_repo.fetch("AT-owned", user_id=b) is None, "cross-user fetch"
    assert bt_repo.list_ids(user_id=b) == [], "cross-user listing"
    assert bt_repo.summaries(user_id=b) == [], "cross-user summaries"
    assert bt_repo.delete("AT-owned", user_id=b) is False, "cross-user delete"
    assert bt_repo.fetch("AT-owned", user_id=a) is not None, "survived the attempt"


def test_insert_cannot_overwrite_another_users_row(db):
    a, b = _make("wa", "wa@example.com"), _make("wb", "wb@example.com")
    from tests._isolation_helpers import tiny_results

    bt_repo.insert("AT-collide", tiny_results(), "synthetic",
                   _t("09:30"), _t("16:00"), user_id=a)
    with pytest.raises(PermissionError):
        bt_repo.insert("AT-collide", tiny_results(), "synthetic",
                       _t("09:30"), _t("16:00"), user_id=b)
    assert bt_repo.fetch("AT-collide", user_id=a) is not None


def test_every_repo_function_demands_an_owner():
    """No default owner anywhere -- a forgotten argument must not silently pass.

    A default of None would make the unscoped call the easy one to write, and
    forgetting it is precisely the mistake this whole migration exists to stop.
    """
    import inspect

    missing = []
    for name in ("insert", "fetch", "list_ids", "summaries", "delete"):
        sig = inspect.signature(getattr(bt_repo, name))
        p = sig.parameters.get("user_id")
        if p is None:
            missing.append(f"{name}: no user_id parameter")
        elif p.default is not inspect.Parameter.empty:
            missing.append(f"{name}: user_id defaults to {p.default!r}")
    assert not missing, "\n  ".join(missing)


# ── the migration itself ─────────────────────────────────────────────────────


def test_pre_ownership_rows_are_backfilled_not_left_public(tmp_path, monkeypatch):
    """A v3 database upgraded in place must not leave NULL owners readable."""
    import sqlite3

    path = tmp_path / "legacy.db"
    monkeypatch.setattr(connection, "DB_PATH", path)
    monkeypatch.setattr(bt_repo, "BLOB_DIR", tmp_path / "blobs")

    conn = connection.connect(path)          # creates it at the current version
    conn.close()

    # The founding account must exist BEFORE the raw connection is opened:
    # create_user opens its own connection, and SQLite refuses a second writer
    # while one is held -- "database is locked", which is what this did first.
    owner = _make("founder", "founder@example.com")

    # Simulate a row written before ownership existed.
    raw = sqlite3.connect(path)
    raw.execute("UPDATE backtests SET user_id = NULL")
    raw.execute(
        "INSERT INTO backtests (id, created_at, user_id, symbol, strategy_name,"
        " timeframe, start_date, end_date, initial_capital, data_source,"
        " session_start, session_end, total_pnl, total_return_pct, sharpe_ratio,"
        " sortino_ratio, max_drawdown_pct, win_rate, profit_factor, avg_win,"
        " avg_loss, total_trades, winning_trades, losing_trades,"
        " avg_trade_duration_min, final_capital)"
        " VALUES ('AT-legacy', '2024-01-01T00:00:00', NULL, 'ES', 's', '1h',"
        " '2024-01-01', '2024-01-02', 100000, 'synthetic', '09:30:00',"
        " '16:00:00', 0,0,0,0,0,0,0,0,0,0,0,0,0,100000)")
    raw.commit()
    raw.close()

    # Reconnecting runs the migration, which must claim the orphan.
    conn = connection.connect(path)
    row = conn.execute("SELECT user_id FROM backtests WHERE id = 'AT-legacy'").fetchone()
    conn.close()
    assert row["user_id"] == owner, \
        "a pre-ownership row kept a NULL owner -- it would be invisible or, worse, shared"


def test_schema_v4_columns_exist_on_an_upgraded_database(tmp_path, monkeypatch):
    """ALTER TABLE, not CREATE TABLE IF NOT EXISTS.

    schema.sql is entirely IF NOT EXISTS, which adds new TABLES to an existing
    database for free and adds new COLUMNS not at all. Without the explicit
    ALTER path the added columns would be missing on every database that
    already existed -- i.e. production -- and the first query naming one would
    fail at runtime rather than at startup.
    """
    import sqlite3

    path = tmp_path / "v3.db"
    monkeypatch.setattr(connection, "DB_PATH", path)

    # Build a genuine v3 database by creating the current one and removing the
    # three columns v4 introduced. Hand-writing the old tables instead gets the
    # test wrong in the direction that matters: a stub `backtests (id,
    # created_at)` does not satisfy schema.sql's own indexes, so the failure is
    # the fixture rather than the migration.
    conn = connection.connect(path)
    conn.close()

    raw = sqlite3.connect(path)
    # The v4 indexes reference the v4 columns, and SQLite refuses to drop a
    # column an index depends on. They go first, exactly as they arrived last.
    raw.execute("DROP INDEX IF EXISTS idx_backtests_user")
    raw.execute("DROP INDEX IF EXISTS idx_trades_user")
    for table, column in (("backtests", "user_id"), ("trades", "user_id"),
                          ("users", "is_owner")):
        raw.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
    raw.execute("DELETE FROM schema_version")
    raw.execute("INSERT INTO schema_version VALUES (3, '2024-01-01T00:00:00')")
    raw.commit()
    raw.close()

    # Precondition: this really is a v3 database now.
    raw = sqlite3.connect(path)
    cols = {r[1] for r in raw.execute("PRAGMA table_info(backtests)")}
    raw.close()
    assert "user_id" not in cols, "fixture did not actually produce a v3 database"
    conn = connection.connect(path)
    try:
        assert "user_id" in connection.columns(conn, "backtests")
        assert "user_id" in connection.columns(conn, "trades")
        assert "is_owner" in connection.columns(conn, "users")
        v = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()["v"]
        assert v == connection.SCHEMA_VERSION
    finally:
        conn.close()


def test_new_accounts_never_get_the_broker_role(db):
    """is_owner must default to 0 for anything that creates a user.

    Open signup is coming. There is exactly one Schwab connection and it
    belongs to the operator, so no registration path -- present or future --
    may hand it out.
    """
    uid = _make("newcomer", "newcomer@example.com")
    conn = connection.connect()
    try:
        row = conn.execute("SELECT is_owner FROM users WHERE id = ?", (uid,)).fetchone()
    finally:
        conn.close()
    assert row["is_owner"] == 0


def _t(hhmm: str):
    from datetime import time
    h, m = hhmm.split(":")
    return time(int(h), int(m))
