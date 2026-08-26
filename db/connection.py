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

SCHEMA_VERSION = 2


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


def _init(conn: sqlite3.Connection, path: Path | None = None) -> None:
    """Apply the schema. Idempotent -- every statement is IF NOT EXISTS."""
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    now = datetime.now().isoformat(timespec="seconds")
    if row["v"] is None:
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, now),
        )
    elif row["v"] < SCHEMA_VERSION:
        # Every statement in schema.sql is IF NOT EXISTS, so the executescript
        # above has already added whatever the newer version introduced. All
        # that is left is to record that the file is now at this version.
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
