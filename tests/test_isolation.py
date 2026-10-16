"""One account must never reach another account's data -- at the data layer.

Until schema v4 the backtests and trades tables had no owner column. That
gap was closed in the repository layer, and these tests keep it closed.

SIGN-IN WAS REMOVED on 2026-10-16. Every HTTP request now runs as one
workspace account, so "Bob signs in and requests Alice's backtest over HTTP"
is no longer a scenario that can happen, and those route-level tests went with
sign-in. What stays is everything BELOW the router: the repository and store
still scope every read, write and delete by owner, and a second account in the
same database still cannot see the first one's rows. That guarantee does not
depend on sign-in, and is what any future multi-account setup would rest on.

The one HTTP sweep kept is the positive half: every route addressed by a
{backtest_id} must still serve the workspace's own result. It enumerates the
app's own OpenAPI schema rather than a hand-written list, so a route added
later is covered on the day it is added.
"""



import pytest
from fastapi.testclient import TestClient

from api import store
from api.main import app
from db import backtests as bt_repo
from db import connection
from db import users as repo

# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A scratch database and an empty result cache.

    The store cache is module-level and survives between tests in one process,
    so it is cleared here -- otherwise a backtest saved by an earlier test
    could satisfy a later one from memory and the database filtering would
    never be exercised.
    """
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "isolation.db")
    monkeypatch.setattr(bt_repo, "BLOB_DIR", tmp_path / "blobs")
    monkeypatch.setattr(store, "_store", {})
    return tmp_path


def _make(username: str, email: str) -> int:
    """An account row. No password: nothing signs in any more."""
    return repo.create_user(username, "!", full_name=username.title(),
                            email=email, country="IN", has_password=False)


@pytest.fixture
def client(db):
    """The app as a visitor sees it: no sign-in, every request is the workspace."""
    with TestClient(app) as c:
        yield c


#: The cheapest run that still produces a real stored result with trades.
RUN = {
    "symbol": "ES", "strategy_id": "ma_crossover",
    "params": {"fast": 5, "slow": 20},
    "timeframe": "1h", "start_date": "2024-01-02", "end_date": "2024-02-01",
    "initial_capital": 100000, "data_source": "synthetic",
    "session_start": "09:30:00", "session_end": "16:00:00",
}


@pytest.fixture
def workspace_backtest(client) -> str:
    r = client.post("/api/backtests", json=RUN)
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


def test_every_backtest_route_serves_the_workspaces_own_result(client, workspace_backtest):
    """Every id-addressed route, swept, returns 200 for the result it names.

    The positive half of what used to be a two-user sweep. It is what proves
    the store's owner scoping is applied with the RIGHT owner: a route that
    looked results up under the wrong account would 404 its own runs here.
    """
    broken = []
    for method, path in _owned_routes():
        url = path.replace("{backtest_id}", workspace_backtest)
        r = client.request(method, url)
        if r.status_code != 200:
            broken.append(f"{method} {path} -> {r.status_code}")
    assert not broken, "the workspace cannot read its own result:\n  " + "\n  ".join(broken)


# ── listing, summarising, deleting ───────────────────────────────────────────


#: There is currently no collection route -- no GET /api/backtests listing and
#: no DELETE. store.list_ids / summaries / delete exist and are unused by HTTP.
#: They are tested at the store layer instead of through a route that does not
#: exist, because that is the layer any future listing endpoint would call, so
#: the isolation is already in place on the day someone adds one.
def _seed(user_id: int, bid: str) -> str:
    from tests._isolation_helpers import tiny_results
    bt_repo.insert(bid, tiny_results(), "synthetic", _t("09:30"), _t("16:00"), user_id=user_id)
    return bid


def test_listing_shows_only_your_own_runs(db):
    """store.list_ids is what a listing endpoint would be built on."""
    a, b = _make("alice", "alice@example.com"), _make("bob", "bob@example.com")
    bid = _seed(a, "AT-list")
    assert bid in store.list_ids(user_id=a)
    assert store.list_ids(user_id=b) == [], "another account's runs were listed"


def test_summaries_show_only_your_own_runs(db):
    a, b = _make("alice", "alice@example.com"), _make("bob", "bob@example.com")
    bid = _seed(a, "AT-sum")
    assert any(r["id"] == bid for r in store.summaries(user_id=a))
    assert store.summaries(user_id=b) == [], "another account's runs were summarised"


def test_delete_cannot_reach_another_users_run(db):
    a, b = _make("alice", "alice@example.com"), _make("bob", "bob@example.com")
    bid = _seed(a, "AT-del")
    assert store.delete(bid, user_id=b) is False
    # Still there afterwards -- a delete that reports "nothing here" while
    # actually deleting would be the worst of both outcomes.
    assert store.get(bid, user_id=a) is not None


def test_deleting_your_own_run_still_works(db):
    a = _make("alice", "alice@example.com")
    bid = _seed(a, "AT-own")
    assert store.delete(bid, user_id=a) is True
    assert store.get(bid, user_id=a) is None


def test_the_in_memory_cache_does_not_leak(client, workspace_backtest):
    """A cache hit returns before any query runs, so the cache must be scoped too.

    The run just made over HTTP is in the process cache under the workspace
    account. A lookup for the same id under any OTHER account must still miss.
    """
    assert any(bid == workspace_backtest for _, bid in store._store), (
        "precondition: the result should be cached in-process")
    other = _make("someone-else", "else@example.com")
    assert store.get(workspace_backtest, user_id=other) is None


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

    There is exactly one Schwab connection and it belongs to the operator,
    so nothing that creates an account may hand it out -- including the
    workspace account created when the app is first opened.
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
