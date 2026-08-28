"""A WAL-safe copy of a live SQLite database, verified before it is trusted.

    py -3.12 scripts/sqlite_online_backup.py SOURCE.db DEST.db

WHY NOT `cp`
------------
This database runs in WAL mode. A plain file copy of a live WAL database can be
torn: the copy catches the main file mid-write, or catches it without the -wal
sidecar that holds the committed pages. The result opens without complaint and
is missing recent transactions -- which is the worst possible failure for a
backup, because you find out at restore time, on the day you needed it.

`sqlite3.Connection.backup()` is SQLite's own online backup API. It takes the
pages under a read lock, copes with a concurrent writer, and produces a
consistent snapshot without stopping the application.

WHY THE INTEGRITY CHECK IS HERE AND NOT IN THE SHELL SCRIPT
-----------------------------------------------------------
A backup nobody verified is a guess. `PRAGMA integrity_check` runs against the
COPY, before it is compressed or uploaded, so a corrupt snapshot fails loudly
at 03:00 instead of silently becoming the newest object in the bucket -- where
it would displace the last good one in any retention policy.

This module is imported by the restore test as well as run by backup.sh, on
purpose: a test that re-implements the thing it is testing proves only that two
copies agree.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


class BackupError(RuntimeError):
    """The snapshot could not be taken, or could not be trusted."""


def online_backup(source: Path, dest: Path) -> dict:
    """Copy `source` to `dest` while it may be being written to.

    Returns a small report. Raises BackupError if the copy is not sound --
    never returns a path to a file it could not verify.
    """
    source, dest = Path(source), Path(dest)
    if not source.is_file():
        raise BackupError(f"no database at {source}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()

    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    dst = sqlite3.connect(dest)
    try:
        # The API that makes this safe against a live writer.
        with dst:
            src.backup(dst)
    finally:
        src.close()
        dst.close()

    # Verify the COPY, not the original. The original being healthy says
    # nothing about whether the bytes just written are.
    check = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)
    try:
        row = check.execute("PRAGMA integrity_check").fetchone()
        if not row or row[0] != "ok":
            raise BackupError(f"integrity_check on the copy returned {row!r}")
        counts = {}
        for table in ("users", "sessions", "oauth_identities", "backtests"):
            try:
                counts[table] = check.execute(
                    f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.OperationalError:
                counts[table] = None       # table not in this schema version
    finally:
        check.close()

    # An empty users table in a database that is supposed to hold accounts is
    # not a healthy backup -- it is a backup of the wrong file, or of a
    # database that was recreated. Better to fail than to keep it.
    if counts.get("users") == 0:
        raise BackupError("the copy has zero users; refusing to call it a backup")

    return {"bytes": dest.stat().st_size, "counts": counts}


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    try:
        report = online_backup(Path(argv[1]), Path(argv[2]))
    except BackupError as exc:
        print(f"BACKUP FAILED: {exc}", file=sys.stderr)
        return 1
    counts = " · ".join(f"{k}={v}" for k, v in report["counts"].items()
                        if v is not None)
    print(f"ok  {report['bytes']:,} bytes  {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
