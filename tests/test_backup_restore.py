"""The backup can be restored, and the restored app works.

A backup nobody restores is a guess, and this is the guess that costs the most
when it turns out wrong.

These tests exercise scripts/sqlite_online_backup.py ITSELF rather than a
re-implementation of it. A test that copies the logic it is testing proves only
that two copies of the same mistake agree with each other.

Sign-in was removed on 2026-10-16, so "can it be signed in to" is no longer the
question. The question is the same one underneath: pointed at the restored
file, does the app come up as the same workspace with the same data?
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

USERNAME = "restoreprobe"
CONFIG_NAME = "restore-probe-config"


@pytest.fixture()
def seeded(tmp_path, monkeypatch):
    """A database with an account and a saved configuration on it."""
    from db import connection
    from db import users as repo

    db = tmp_path / "live" / "autotrader.db"
    db.parent.mkdir(parents=True)
    monkeypatch.setattr(connection, "DB_PATH", db)
    connection.connect(db).close()

    uid = repo.create_user(USERNAME, "!", full_name="Restore Probe",
                           email="restore@example.invalid",
                           has_password=False, db=db)
    repo.save_config(uid, CONFIG_NAME, '{"symbol": "ES"}', db=db)
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
            # Saved configurations: real, still-used account data, and a
            # unique name per row so every insert genuinely writes.
            c.execute(
                "INSERT INTO user_configs (user_id, name, payload, saved_at)"
                " VALUES (?,?,?,?)",
                (uid, os.urandom(8).hex(), "{}", "2026-01-01T00:00:00"))
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


def test_a_restored_backup_opens_as_the_same_workspace(seeded, tmp_path, monkeypatch):
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
    assert check.execute("SELECT COUNT(*) FROM user_configs").fetchone()[0] == 1
    check.close()

    # Point the real application at the restored file and open it over HTTP.
    from db import connection
    monkeypatch.setattr(connection, "DB_PATH", restored)
    from api.main import app

    with TestClient(app) as client:
        me = client.get("/api/auth/me")
        assert me.status_code == 200, f"the restored app did not open: {me.text}"
        assert me.json()["username"] == USERNAME, (
            "the restored app came up as a different workspace -- "
            "the data is not the original's")
        names = [c["name"] for c in client.get("/api/account/configs").json()]
        assert CONFIG_NAME in names, "the saved configuration did not survive the restore"
