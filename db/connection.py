"""SQLite connection handling for the result database.

WHY SQLITE AND NOT A SERVER
---------------------------
The whole database is one file. There is no daemon to start, no port to open,
no password, no monthly bill, and no way for it to be down while the app is up.
On a single-desk tool that is the difference between a database that helps and
one that becomes a second thing to keep alive. Postgres, MySQL and Mongo all
buy concurrent writers and replication that a one-process app never uses.

WHAT LIVES HERE AND WHAT DOES NOT
---------------------------------
Scalars and trades go in SQL, because those are what you would ever want to ask
questions about. The equity curve and the OHLCV frame stay as Parquet sidecars;
see the note at the top of schema.sql for why.
"""

import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

#: Override with AUTOTRADER_DB_PATH. The default sits under data/, which
#: docker-compose already mounts as the named volume autotrader-data, so the
#: database survives a redeploy without touching the compose file.
DB_PATH = Path(os.environ.get("AUTOTRADER_DB_PATH", "data/autotrader.db"))

SCHEMA = Path(__file__).with_name("schema.sql")

#: v2 added users + sessions; v3 added oauth_identities + oauth_states;
#: v4 added ownership (backtests.user_id, trades.user_id, users.is_owner);
#: v5 added users.email_verified and made a non-empty email unique;
#: v6 added oauth_pending for sign-ups that need a username before they exist.
SCHEMA_VERSION = 6

#: Columns added to tables that already existed, as (table, column, definition).
#:
#: Everything in schema.sql is CREATE ... IF NOT EXISTS, which is why migrating
#: has so far been free: a new TABLE simply appears. That does not extend to a
#: new COLUMN. `CREATE TABLE IF NOT EXISTS backtests (...)` is a no-op against a
#: database that already has a backtests table, so the added column is silently
#: absent, and the first query naming it fails at runtime rather than at
#: startup -- on the server, after the deploy reported success.
#:
#: SQLite has no ADD COLUMN IF NOT EXISTS, so each one is guarded by reading
#: PRAGMA table_info first. Adding a column is O(1) in SQLite: it rewrites the
#: header, not the rows.
_ADDED_COLUMNS = [
    ("backtests", "user_id", "INTEGER REFERENCES users(id)"),
    ("trades", "user_id", "INTEGER REFERENCES users(id)"),
    ("users", "is_owner", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "email_verified", "INTEGER NOT NULL DEFAULT 0"),
]


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open the database, creating and migrating it if necessary."""
    path = Path(path) if path is not None else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    # timeout: if a write is in flight, wait rather than raising "database is
    # locked" immediately. detect_types is deliberately NOT set -- timestamps
    # are stored as ISO strings and parsed explicitly, because sqlite3's own
    # converters are deprecated in 3.12 and silently drop timezone information.
    conn = sqlite3.connect(path, timeout=10.0, isolation_level=None)
    conn.row_factory = sqlite3.Row

    # WAL lets a reader work while a writer is committing, which matters the
    # moment the dashboard polls a list while a backtest is being saved.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")

    _init(conn, path)
    return conn


def _add_missing_columns(conn: sqlite3.Connection) -> list[str]:
    """Bring an existing database up to the current column set.

    Returns what it added, so the caller can log it. Safe to run on every
    connection: a column that is already there is skipped.
    """
    added = []
    for table, column, definition in _ADDED_COLUMNS:
        # The table may not exist yet on a brand-new file -- executescript has
        # already run by this point, so it does, but a future reordering
        # should not turn this into a crash.
        present = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if not present or column in present:
            continue
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        added.append(f"{table}.{column}")
    return added


def _dedupe_emails(conn: sqlite3.Connection) -> list[str]:
    """Clear duplicate addresses so the v5 unique index can be created.

    schema.sql creates a UNIQUE index over a non-empty email. CREATE UNIQUE
    INDEX fails outright if the data already violates it, and a failure here
    means the application does not start -- so a database holding two accounts
    with one address would be taken off the air by its own upgrade.

    Resolution is deterministic: the lowest user id keeps the address, later
    ones have it cleared. Clearing an email neither deletes an account nor
    locks anyone out, because sign-in is by username; it only means those
    accounts cannot be found by address until someone sets a new one. That is
    the correct outcome, since "which of these accounts owns this address" has
    no answer the database can be trusted to give -- and answering it wrongly
    is an account takeover once OAuth starts matching on it.

    Returns a description of every change, for logging. Normally empty.
    """
    present = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
    if not present or "email" not in present:
        return []

    rows = conn.execute(
        "SELECT id, username, email FROM users "
        "WHERE email != '' AND email IN ("
        "  SELECT email FROM users WHERE email != '' "
        "  GROUP BY email HAVING COUNT(*) > 1) "
        "ORDER BY email, id"
    ).fetchall()
    if not rows:
        return []

    cleared, seen = [], set()
    for r in rows:
        key = r["email"].lower()
        if key not in seen:
            seen.add(key)          # the oldest account keeps it
            continue
        conn.execute("UPDATE users SET email = '' WHERE id = ?", (r["id"],))
        cleared.append(f"{r['username']!r} (id {r['id']}) lost duplicate {r['email']!r}")
    return cleared


def _backfill_ownership(conn: sqlite3.Connection) -> int:
    """Give pre-ownership rows an owner.

    Rows written before v4 have user_id IS NULL. A NULL owner must never be
    readable by everyone -- that is precisely the leak this migration exists to
    close -- so they are assigned to the founding account, the lowest user id,
    which is the operator who ran them.

    If there are no users yet the rows stay NULL and stay unreachable: the
    query layer matches on an explicit user_id and NULL never equals anything
    in SQL, so they are invisible rather than public. They are picked up by the
    next connection after an account exists.
    """
    owner = conn.execute("SELECT MIN(id) AS id FROM users").fetchone()
    if owner is None or owner["id"] is None:
        return 0
    total = 0
    for table in ("backtests", "trades"):
        cur = conn.execute(
            f"UPDATE {table} SET user_id = ? WHERE user_id IS NULL", (owner["id"],)
        )
        total += cur.rowcount or 0
    return total


def _init(conn: sqlite3.Connection, path: Path | None = None) -> None:
    """Apply the schema. Idempotent -- every statement is IF NOT EXISTS."""
    # ORDER MATTERS, and it is the reverse of the obvious one.
    #
    # Columns are added BEFORE the schema script runs, not after. schema.sql
    # ends with `CREATE INDEX IF NOT EXISTS idx_backtests_user ON
    # backtests(user_id, ...)`, and an index over a column that does not exist
    # yet is an error, not a no-op. Running the script first therefore aborts
    # partway through on exactly the databases that need migrating -- every
    # one that predates v4, i.e. production -- while a fresh file, where the
    # table is created complete, succeeds. That asymmetry is what makes the
    # wrong order look correct in testing.
    #
    # On a new file the tables do not exist yet, PRAGMA table_info returns
    # nothing, and this is a no-op.
    added = _add_missing_columns(conn)
    if added:
        log.info("%s: added column(s) %s", path, ", ".join(added))

    # Also before the script, and for the same reason as the columns: the
    # script creates a UNIQUE index over email, and CREATE UNIQUE INDEX fails
    # on data that already violates it. An upgrade must not be able to stop the
    # application from starting.
    cleared = _dedupe_emails(conn)
    for line in cleared:
        log.warning("%s: %s -- duplicate addresses are not allowed from v5", path, line)

    conn.executescript(SCHEMA.read_text(encoding="utf-8"))

    # Backfill last: it reads `users`, which the script above may have created.
    moved = _backfill_ownership(conn)
    if moved:
        log.info("%s: assigned %d pre-ownership row(s) to the founding account",
                 path, moved)

    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    now = datetime.now().isoformat(timespec="seconds")
    if row["v"] is None:
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, now),
        )
    elif row["v"] < SCHEMA_VERSION:
        # New TABLES arrive via the IF NOT EXISTS script above; new COLUMNS
        # arrive via _add_missing_columns. Both have run, so all that is left
        # is to record that the file is now at this version.
        log.info("%s upgraded from schema v%s to v%s", path, row["v"], SCHEMA_VERSION)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, now),
        )
    elif row["v"] > SCHEMA_VERSION:
        # Refuse rather than guess. A newer file may have columns this build
        # does not write, and a partial INSERT would corrupt it quietly.
        raise RuntimeError(
            f"{DB_PATH} is schema v{row['v']}, this build understands v{SCHEMA_VERSION}. "
            "Upgrade the application rather than downgrading the database."
        )


def columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """Column names of a table, in declaration order."""
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]
