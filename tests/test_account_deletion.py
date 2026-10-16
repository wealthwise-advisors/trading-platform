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

Closing an account is an OPERATOR action now -- scripts/manage_users.py
delete. The "Close this account" screen and its DELETE /api/auth/me route went
with sign-in on 2026-10-16, and their tests with them; what is tested here is
the repository function that command calls.
"""

import sqlite3

import pytest

from db import backtests as blobs
from db import connection
from db import users as repo


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A scratch database and sidecars under tmp_path."""
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "accounts.db")
    monkeypatch.setattr(blobs, "BLOB_DIR", tmp_path / "backtests")
    return tmp_path


def make_user(username="trader", email="") -> int:
    """An account row. No password: nothing signs in any more."""
    return repo.create_user(username, "!", full_name="A Trader", email=email,
                            country="IN", has_password=False)


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
