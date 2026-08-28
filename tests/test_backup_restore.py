"""The backup can be restored and signed in to.

A backup nobody restores is a guess, and this is the guess that costs the most
when it turns out wrong -- signup is open, so the database now holds other
people's accounts, not just the operator's.

These tests exercise scripts/sqlite_online_backup.py ITSELF rather than a
re-implementation of it. A test that copies the logic it is testing proves only
that two copies of the same mistake agree with each other.

WHY THIS MODULE IS IN _SECURITY_SUITES
--------------------------------------
It asserts that an anonymous caller is REFUSED by the restored database. Every
suite outside `_SECURITY_SUITES` runs with `require_user` overridden to a
signed-in user, so without that entry this file would assert a 401 against a
fixture that can never produce one -- and pass while testing nothing. See
tests/conftest.py.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tarfile
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from sqlite_online_backup import BackupError, online_backup  # noqa: E402

PASSWORD = "Restore-Test-Passw0rd"
USERNAME = "restoreprobe"


@pytest.fixture()
def seeded(tmp_path, monkeypatch):
    """A database with a real account, an OAuth identity and a session."""
    from db import connection
    from db import users as repo
    from api import auth

    db = tmp_path / "live" / "autotrader.db"
    db.parent.mkdir(parents=True)
    monkeypatch.setattr(connection, "DB_PATH", db)
    connection.connect(db).close()

    uid = repo.create_user(USERNAME, auth.hash_password(PASSWORD),
                           full_name="Restore Probe",
                           email="restore@example.invalid",
                           email_verified=True, db=db)
    repo.link_identity(uid, "google", "restore-subject-1",
                       email="restore@example.invalid")
    repo.new_session(uid, ip="127.0.0.1", user_agent="restore-test", db=db)
    return db, uid


def test_a_plain_copy_of_a_wal_database_is_not_a_backup(tmp_path):
    """The reason sqlite_online_backup.py exists, demonstrated rather than claimed.

    This is NOT a race. `cp` copies the main database file only; anything
    committed into the -wal sidecar and not yet checkpointed is simply not in
    the copy. Here that includes the CREATE TABLE, so the naive copy does not
    merely lose rows -- it does not open.
    """
    src = tmp_path / "wal.db"
    conn = sqlite3.connect(src)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (v TEXT)")
    conn.commit()
    conn.executemany("INSERT INTO t VALUES (?)", [(str(i),) for i in range(500)])
    conn.commit()

    naive = tmp_path / "naive.db"
    shutil.copyfile(src, naive)                     # exactly what cp does

    proper = tmp_path / "proper.db"
    ro = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    dst = sqlite3.connect(proper)
    with dst:
        ro.backup(dst)
    ro.close()
    dst.close()
    conn.close()

    def rows(path):
        try:
            c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                return c.execute("SELECT COUNT(*) FROM t").fetchone()[0]
            finally:
                c.close()
        except sqlite3.Error:
            return None                              # unreadable

    assert rows(proper) == 500, "the online backup must keep every committed row"
    assert rows(naive) != 500, (
        "a plain copy appeared complete -- if this ever passes, the reasoning "
        "behind using the online backup API needs revisiting"
    )


def test_the_snapshot_is_consistent_under_a_concurrent_writer(seeded):
    """The case a plain copy gets wrong, run against the real helper."""
    db, uid = seeded
    stop = threading.Event()
    written = {"n": 0}

    def churn():
        c = sqlite3.connect(db, timeout=30)
        c.execute("PRAGMA journal_mode=WAL")
        while not stop.is_set():
            c.execute(
                "INSERT INTO sessions (user_id, token_hash, created_at,"
                " expires_at, last_seen_at, ip, user_agent)"
                " VALUES (?,?,?,?,?,?,?)",
                (uid, os.urandom(16).hex(), "2026-01-01T00:00:00",
                 "2099-01-01T00:00:00", "2026-01-01T00:00:00",
                 "127.0.0.1", "churn"))
            c.commit()
            written["n"] += 1
            time.sleep(0.001)
        c.close()

    worker = threading.Thread(target=churn, daemon=True)
    worker.start()
    time.sleep(0.3)
    try:
        report = online_backup(db, db.parent.parent / "snap.db")
    finally:
        stop.set()
        worker.join(timeout=5)

    # A load test that applies no load passes everything. The first version of
    # this omitted a NOT NULL column, so every insert raised and the "writer"
    # wrote nothing -- this assertion is what caught it.
    assert written["n"] > 20, "the concurrent writer never actually wrote"
    assert report["counts"]["users"] == 1


def test_an_empty_database_is_refused_as_a_backup(tmp_path, monkeypatch):
    """Zero users is a backup of the wrong file, not a healthy snapshot."""
    from db import connection

    empty = tmp_path / "empty.db"
    connection.connect(empty).close()
    with pytest.raises(BackupError, match="zero users"):
        online_backup(empty, tmp_path / "out.db")


def test_a_restored_backup_can_be_signed_in_to(seeded, tmp_path, monkeypatch):
    """The only question that actually matters."""
    db, _ = seeded
    snap = tmp_path / "snap" / "autotrader.db"
    online_backup(db, snap)

    # Package and unpackage exactly as scripts/backup.sh does.
    cfg = snap.parent / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "schwab_tokens.json").write_text('{"access_token": "NOT-REAL"}')
    tarball = tmp_path / "backup.tar.gz"
    with tarfile.open(tarball, "w:gz") as tf:
        tf.add(snap, arcname="autotrader.db")
        tf.add(cfg, arcname="config")

    restored_dir = tmp_path / "restored"
    with tarfile.open(tarball) as tf:
        tf.extractall(restored_dir)
    restored = restored_dir / "autotrader.db"

    assert (restored_dir / "config" / "schwab_tokens.json").is_file(), \
        "the credentials that exist nowhere else must survive the round trip"

    check = sqlite3.connect(f"file:{restored}?mode=ro", uri=True)
    assert check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert check.execute("SELECT COUNT(*) FROM oauth_identities").fetchone()[0] == 1
    check.close()

    # Point the real application at the restored file and sign in over HTTP.
    from db import connection
    from api import auth as auth_mod
    monkeypatch.setattr(connection, "DB_PATH", restored)
    # Patch the FLAG, not the environment variable. _INSECURE is read once at
    # import time, and api.auth is already imported by the time this test runs
    # -- so setenv here would leave Secure=True on the cookie, TestClient would
    # drop it over http, and the session would vanish between login and the
    # very next request. That failure looks exactly like a broken restore,
    # which is the wrong thing for this test to be able to say.
    monkeypatch.setattr(auth_mod, "_INSECURE", True)
    from api.main import app

    with TestClient(app) as client:
        assert client.get("/api/auth/me").status_code == 401, \
            "the restored database must still refuse an anonymous caller"

        signed_in = client.post("/api/auth/login",
                                json={"username": USERNAME, "password": PASSWORD})
        assert signed_in.status_code == 200, \
            f"could not sign in to the restored data: {signed_in.text}"

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["username"] == USERNAME

        assert client.post("/api/auth/login",
                           json={"username": USERNAME, "password": "wrong"}
                           ).status_code != 200, \
            "a restored database must not accept a wrong password"
