-- AutoTrader result database -- schema v1
--
-- Two tables and a version marker. Everything here is IF NOT EXISTS, so
-- applying it to an existing database is a no-op and it can run on every
-- connection without a separate "is it set up yet" check.
--
-- What is NOT in here: the equity curve and the OHLCV frame. Those are two
-- pandas objects, tens of thousands of rows each, written by every run and
-- read back whole or not at all. Shredding them into rows would multiply the
-- database size by two orders of magnitude to support a query nobody makes.
-- They live next to the database as Parquet, and `equity_rows` / `price_rows`
-- below record how many rows each file should have so a truncated file is
-- detectable rather than silently short.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER NOT NULL,
    applied_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS backtests (
    id                      TEXT    PRIMARY KEY,
    created_at              TEXT    NOT NULL,

    -- what was run
    symbol                  TEXT    NOT NULL,
    strategy_name           TEXT    NOT NULL,
    timeframe               TEXT    NOT NULL,
    start_date              TEXT    NOT NULL,
    end_date                TEXT    NOT NULL,
    initial_capital         REAL    NOT NULL,
    data_source             TEXT    NOT NULL,
    session_start           TEXT    NOT NULL,
    session_end             TEXT    NOT NULL,

    -- what came out. One column per metric on BacktestResults; a guard test
    -- fails the build if that dataclass gains a field this table has not got,
    -- so the answer is a migration and never a silently dropped number.
    total_pnl               REAL    NOT NULL,
    total_return_pct        REAL    NOT NULL,
    sharpe_ratio            REAL    NOT NULL,
    sortino_ratio           REAL    NOT NULL,
    max_drawdown_pct        REAL    NOT NULL,
    win_rate                REAL    NOT NULL,
    profit_factor           REAL    NOT NULL,
    avg_win                 REAL    NOT NULL,
    avg_loss                REAL    NOT NULL,
    total_trades            INTEGER NOT NULL,
    winning_trades          INTEGER NOT NULL,
    losing_trades           INTEGER NOT NULL,
    avg_trade_duration_min  REAL    NOT NULL,
    final_capital           REAL    NOT NULL,

    -- the two Parquet sidecars, by row count
    equity_rows             INTEGER NOT NULL DEFAULT 0,
    price_rows              INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS trades (
    backtest_id     TEXT    NOT NULL,
    seq             INTEGER NOT NULL,          -- order within the run

    symbol          TEXT    NOT NULL,
    direction       TEXT    NOT NULL,
    quantity        INTEGER NOT NULL,
    entry_time      TEXT    NOT NULL,
    entry_price     REAL    NOT NULL,
    exit_time       TEXT,                      -- NULL while the trade is open
    exit_price      REAL,                      -- NULL while the trade is open
    pnl             REAL    NOT NULL,
    commission      REAL    NOT NULL,
    strategy        TEXT    NOT NULL DEFAULT '',
    entry_order_id  TEXT    NOT NULL DEFAULT '',
    exit_order_id   TEXT    NOT NULL DEFAULT '',

    PRIMARY KEY (backtest_id, seq),
    FOREIGN KEY (backtest_id) REFERENCES backtests(id) ON DELETE CASCADE
);

-- The indexes exist for the questions a database is actually here to answer:
-- this symbol's runs, the newest runs, and the ones that scored well.
CREATE INDEX IF NOT EXISTS idx_backtests_symbol   ON backtests(symbol);
CREATE INDEX IF NOT EXISTS idx_backtests_created  ON backtests(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_backtests_sharpe   ON backtests(sharpe_ratio DESC);
CREATE INDEX IF NOT EXISTS idx_backtests_strategy ON backtests(strategy_name);
CREATE INDEX IF NOT EXISTS idx_trades_backtest    ON trades(backtest_id);
CREATE INDEX IF NOT EXISTS idx_trades_entry_time  ON trades(entry_time);

-- ── auth (schema v2) ────────────────────────────────────────────────────────
-- Added when the app stopped being open to the internet. Both tables are
-- IF NOT EXISTS like the rest of this file, so applying it to a v1 database
-- simply adds them; connection.py bumps the recorded version afterwards.

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    -- argon2id, produced by argon2-cffi. The full encoded string is stored:
    -- it carries the algorithm, its parameters and the per-user salt, so the
    -- cost can be raised later and old hashes still verify.
    password_hash TEXT    NOT NULL,
    full_name     TEXT    NOT NULL DEFAULT '',
    email         TEXT    NOT NULL DEFAULT '' COLLATE NOCASE,
    country       TEXT    NOT NULL DEFAULT '',
    phone         TEXT    NOT NULL DEFAULT '',
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    -- SHA-256 of the cookie value, never the value itself. Someone who reads
    -- this table cannot mint a working cookie from it.
    token_hash  TEXT    PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    created_at  TEXT    NOT NULL,
    expires_at  TEXT    NOT NULL,
    last_seen_at TEXT   NOT NULL,
    user_agent  TEXT    NOT NULL DEFAULT '',
    ip          TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_user    ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

-- ── OAuth sign-in (schema v3) ───────────────────────────────────────────────
-- Signing in with Google/LinkedIn/Twitter. These tables let an EXISTING account
-- be entered a second way; they never create one. There is still exactly one
-- route to a new account, and it is scripts/manage_users.py.

CREATE TABLE IF NOT EXISTS oauth_identities (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    provider     TEXT    NOT NULL,          -- 'google' | 'linkedin' | 'twitter'
    -- The provider's permanent, opaque id for the person. Matching happens on
    -- THIS, not on the email: an email address can be released and re-issued to
    -- somebody else, and it can change on the provider's side, while the
    -- subject cannot. The email below is kept only so an administrator can see
    -- which account a link came from.
    subject      TEXT    NOT NULL,
    email        TEXT    NOT NULL DEFAULT '' COLLATE NOCASE,
    linked_at    TEXT    NOT NULL,
    last_used_at TEXT,

    -- One provider account signs in as exactly one local user. Without this a
    -- second row could quietly point the same Google account at somebody
    -- else's login.
    UNIQUE (provider, subject),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_oauth_identities_user ON oauth_identities(user_id);

-- The in-flight half of an authorization-code exchange.
--
-- Deliberately a TABLE and not a cookie. The state has to survive a top-level
-- redirect back from another site, and it carries the PKCE code_verifier, which
-- must never be readable by the browser -- a verifier the client can read
-- defeats the entire point of PKCE. Rows are single-use and short-lived.
CREATE TABLE IF NOT EXISTS oauth_states (
    state         TEXT PRIMARY KEY,          -- the opaque value sent to the provider
    provider      TEXT NOT NULL,
    code_verifier TEXT NOT NULL,
    next_path     TEXT NOT NULL DEFAULT '/', -- validated same-site before storing
    created_at    TEXT NOT NULL,
    expires_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_oauth_states_expires ON oauth_states(expires_at);
