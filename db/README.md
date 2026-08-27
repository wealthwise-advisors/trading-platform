# `db/` — the result database

SQLite. One file at `data/autotrader.db`, no server, no port, no password, no
monthly bill, and no way for it to be down while the application is up.

| File | Role |
|:---|:---|
| [`schema.sql`](schema.sql) | The tables. Every statement is `IF NOT EXISTS`, so applying it is idempotent |
| [`connection.py`](connection.py) | Opening the file, the PRAGMAs, applying and versioning the schema |
| [`backtests.py`](backtests.py) | The only module that knows the backtest table layout |
| [`users.py`](users.py) | 👥 Accounts, sessions, OAuth identities, email tokens — everything about **people** |
| `__init__.py` | Package docstring |

[`api/store.py`](../api/store.py) is the only caller for backtests, and
[`api/auth.py`](../api/auth.py) the only one for users. Nothing else imports from
here, so the SQL stays in one place and the routers never see a cursor.

### 🔐 What `users.py` guarantees

| Rule | Why |
|---|---|
| Passwords are **argon2id** | Never reversible, never stored in the clear |
| Every token stored as **SHA-256** | A leaked database yields no working session and no usable reset link |
| OAuth matched on **subject**, not email | An address can be released and re-issued; a subject cannot |
| `is_owner` defaults to **0** | The Schwab connection is the operator's own — no route can grant it |

### 🔒 Per-user isolation

`backtests` and `trades` carry a `user_id`, and **no function here takes a
default for it** — a forgotten argument is a `TypeError`, not a leak.

---

## What is in SQL, and what is not

**In SQL:** the scalars — symbol, strategy, dates, capital, and every metric —
plus one row per trade. These are the parts you can ask questions *about*, and
that is the entire reason a database is here rather than a folder of files:

```python
from api import store

store.summaries(symbol="ES", min_sharpe=1.5, since="2026-03-01")
```

**Not in SQL:** the equity curve and the OHLCV frame. Those are two pandas
objects, tens of thousands of rows each, written by every run and read back
whole or not at all. Shredding a 70,000-bar frame into rows would multiply the
database size by two orders of magnitude to support a query nobody makes. They
are written as Parquet in `data/backtests/<backtest_id>/`, which keeps their
dtypes and their `DatetimeIndex` intact, and the row count of each file is
recorded in the `backtests` row so a truncated sidecar is detectable rather
than silently short.

## The cost of using SQL, and what pays it

A schema has columns typed out by hand. Add a metric to `BacktestResults` and
the `INSERT` fails on an unknown column — and because persistence fails soft,
`save()` would swallow that and the number would be dropped on every run with
nothing to notice it.

`tests/test_store_persistence.py::test_schema_covers_every_field_on_the_dataclass`
compares the dataclass against `PRAGMA table_info` and fails the build naming
the field:

```
BacktestResults has ['calmar_ratio'] but the backtests table does not.
Add the column to db/schema.sql and bump SCHEMA_VERSION.
```

That is the deal: SQL costs you a migration, and this test makes sure you are
told to write one instead of finding out months later.

## Failing soft

Persistence must never break a backtest. Every call from `api/store.py` is
wrapped: an unwritable directory, a locked file, a missing Parquet engine — all
of it logs and carries on as the in-memory cache. **A failed write costs
history; a raised exception would cost the run that just finished.**

The corollary is that a broken database is quiet. If results stop surviving
restarts, look for `could not persist backtest` in the logs.

## Operating it

```bash
sqlite3 data/autotrader.db ".tables"
sqlite3 data/autotrader.db "SELECT id, symbol, sharpe_ratio FROM backtests ORDER BY created_at DESC LIMIT 10;"
```

- **Location** — override with `AUTOTRADER_DB_PATH`. The default lives under
  `data/`, which `docker-compose.yml` already mounts as the named volume
  `autotrader-data`, so the database survives a redeploy with no compose change.
- **Backups** — `data/autotrader.db` plus `data/backtests/` is the whole state.
  Copy both or neither; a database without its Parquet sidecars loads rows with
  empty charts.
- **WAL** — journal mode is WAL, so a reader works while a writer commits. That
  also means `autotrader.db-wal` and `autotrader.db-shm` appear beside the file
  and belong to it.
- **Concurrency** — the app runs one uvicorn worker. SQLite would tolerate
  more, but [`api/replay_store.py`](../api/replay_store.py) holds a live engine
  object in memory and would not. Adding workers breaks Live Replay, with or
  without this database.

## Why not Postgres, MySQL, Mongo, Supabase, Firebase

They buy concurrent writers, replication and sharding that a one-process
single-desk tool never uses, and charge a server to run, a schema to migrate
and backups to remember. Supabase and Firebase are mostly bought for their auth
and realtime layers, and this application has no auth at all — and their use
would mean result data leaving the machine that holds the broker credentials.

SQLite is the one on that list with no operational surface: it is a file.
