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

    -- Who ran it (schema v4). NULL means "from before ownership existed";
    -- connection.py backfills those to the founding account on upgrade, so a
    -- NULL never survives a migration and is never treated as public.
    --
    -- Deliberately NOT "ON DELETE CASCADE": deleting a person should not
    -- silently destroy the record of what was run. The row is reassigned or
    -- kept, and that is a decision for whoever removes the account.
    user_id                 INTEGER REFERENCES users(id),

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

    -- Denormalised owner (schema v4). Ownership is derivable by joining to
    -- backtests, so this column is redundant -- on purpose. A query that
    -- reaches trades directly and forgets the join returns another user's
    -- fills, and that is the exact mistake this table is most likely to
    -- suffer. Writing it costs nothing: it is set inside the same transaction
    -- as the parent row, from the same value.
    user_id         INTEGER REFERENCES users(id),

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

-- Ownership indexes (v4). Every list and every summary now filters on user_id
-- first, so without these the common query degrades to a full scan the moment
-- there is more than one account.
CREATE INDEX IF NOT EXISTS idx_backtests_user     ON backtests(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_user        ON trades(user_id);

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

    -- Has this NUMBER been proved to belong to whoever is using the
    -- account (schema v10)? Exactly the same distinction email_verified
    -- draws, and it exists for the same reason: `phone` above is a
    -- string somebody typed at sign-up and nothing has ever checked it.
    --
    -- Nothing may be DELIVERED to a number until this is 1. A sign-in
    -- code texted to an unproved number hands account access to whoever
    -- happens to hold it -- including the stranger who owns the number
    -- that was mistyped at registration.
    phone_verified INTEGER NOT NULL DEFAULT 0,
    is_active     INTEGER NOT NULL DEFAULT 1,

    -- The Schwab entitlement (schema v4).
    --
    -- There is ONE brokerage connection and it belongs to the operator, not to
    -- the application: one config/credentials.yaml, one schwab_tokens.json, no
    -- per-user notion anywhere in src/data/schwab_provider.py. So this is not
    -- a permission level that a person can earn by signing up or by verifying
    -- an email address -- verifying an inbox says nothing about whether
    -- someone should reach the operator's broker.
    --
    -- DEFAULT 0 is the security property: every account created by any route
    -- that exists now or later starts without it. It is granted only by
    -- scripts/manage_users.py, which needs shell access on the server.
    is_owner      INTEGER NOT NULL DEFAULT 0,

    -- Has this address been proved to belong to whoever is using it (v5)?
    --
    -- Set by clicking a link sent to the address, or by an OAuth provider that
    -- positively reports the address as verified. Never set by the person
    -- typing it in: an address someone typed is a claim, not a fact.
    --
    -- This is what makes email-matched OAuth safe. Signing in with Google
    -- finds a local account by address, so an unverified address that anyone
    -- could type would let a stranger claim someone else's account simply by
    -- registering with their email first.
    email_verified INTEGER NOT NULL DEFAULT 0,

    -- Does a real password exist for this account (schema v7)?
    --
    -- An OAuth-created account stores argon2 over random bytes, so nothing
    -- verifies against it -- but the hash is well-formed and cannot be told
    -- apart from a real one by inspection. This records the distinction at
    -- creation instead of trying to infer it later.
    --
    -- It decides one thing: whether "forgot password" may issue a link. For an
    -- account that HAS a password, reset restores what was there. For one that
    -- does not, it creates a new kind of credential -- which is only safe on an
    -- address somebody proved, never one that was merely typed.
    has_password  INTEGER NOT NULL DEFAULT 1,

    created_at    TEXT    NOT NULL,
    last_login_at TEXT
);

-- One account per address (v5).
--
-- The column was merely a label while accounts came from a CLI. Open signup
-- plus OAuth-by-email makes duplicates dangerous: two accounts sharing an
-- address make "which account does this Google identity belong to" ambiguous,
-- and an ambiguous answer resolved the wrong way is an account takeover.
--
-- Partial, because the empty string is the default and several accounts may
-- legitimately have no address at all -- a plain UNIQUE would collide them
-- with each other. COLLATE NOCASE on the column means Foo@x.com and
-- foo@x.com are already the same address to this index.
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email
    ON users(email) WHERE email != '';

-- ── email verification (schema v5) ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS email_tokens (
    -- SHA-256 of the token, never the token. Same reasoning as sessions: a
    -- leaked database must not hand over working verification links, and a
    -- verification link is a means of taking over an account.
    token_hash  TEXT    PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    expires_at  TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    -- Set when spent. Kept rather than deleted so a second click on the same
    -- link can be told apart from a forgery in the log.
    used_at     TEXT,

    -- What this token is for (schema v7): 'verify' or 'reset'.
    --
    -- Not cosmetic. Issuing a token deletes the user's earlier ones so an old
    -- link stops working, and without this column that delete is not scoped --
    -- so sending a verification email would silently destroy a password reset
    -- the same person had just requested, and the link in their inbox would
    -- fail with no explanation.
    --
    -- It also keeps the two from being interchangeable: a verification link
    -- must not be spendable as a password reset, which would turn "click here
    -- to confirm your address" into "click here to let someone set a
    -- password".
    purpose     TEXT    NOT NULL DEFAULT 'verify',
    -- Wrong guesses against this token (schema v9). Only sign-in codes
    -- use it: a 32-byte link is not guessable, but a six-digit code is
    -- one million tries, so the cap -- not the hashing -- is what makes
    -- it safe. The row is destroyed on the fifth wrong answer.
    attempts    INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_email_tokens_user ON email_tokens(user_id, purpose);

-- ── half-finished OAuth sign-ups (schema v6) ────────────────────────────────
-- Twitter/X returns no email address at any scope, so an X identity arriving
-- for the first time cannot be matched to an account and cannot create one
-- either -- there is nothing to create it from. Rather than refuse outright,
-- the identity is parked here and the person is asked for a username and an
-- address.
--
-- This is NOT a session and must never become one. It proves only that someone
-- controls an X account; it grants nothing until the details come back and a
-- real account is made. Hence a separate table with its own short expiry
-- rather than a row in `sessions`.
-- UNUSED since X sign-in stopped asking for details. Nothing reads or writes
-- this table any more: an X identity now creates its account directly, with
-- no address, which the users table has always allowed. Kept rather than
-- dropped because removing a table from a live database earns nothing here
-- -- it is empty, unreferenced, and costs a few bytes. Do not build on it.
CREATE TABLE IF NOT EXISTS oauth_pending (
    -- SHA-256 of the handle given to the browser, never the handle itself --
    -- same reasoning as sessions and email tokens.
    token_hash  TEXT    PRIMARY KEY,
    provider    TEXT    NOT NULL,
    subject     TEXT    NOT NULL,
    -- What the provider volunteered, to prefill the form. Advisory only: the
    -- person can change it, and the server revalidates whatever comes back.
    suggested   TEXT    NOT NULL DEFAULT '',
    next_path   TEXT    NOT NULL DEFAULT '/',
    expires_at  TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    UNIQUE (provider, subject)
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

-- ── saved backtest configurations (schema v8) ───────────────────────────────
--
-- These lived in the browser's localStorage, which made them look persistent
-- and made them nothing of the sort: clearing site data destroyed them, they
-- never followed anyone to a second machine, and -- the part that mattered for
-- the privacy policy -- they sat outside every server-side guarantee it makes.
-- Closing an account could not remove them because the server had never seen
-- them.
--
-- ON DELETE CASCADE here, unlike backtests. A saved config is form state a
-- person named, not a record of something that happened; there is no reason to
-- keep one whose owner is gone, and every reason not to.
CREATE TABLE IF NOT EXISTS user_configs (
    user_id     INTEGER NOT NULL,
    name        TEXT    NOT NULL,
    -- The ConfigSnapshot, verbatim, as JSON. Deliberately opaque to SQL: the
    -- sidebar's field set changes with the product, and a column per field
    -- would turn every new knob into a migration. Nothing here is queried by
    -- content -- it is fetched whole, by owner.
    payload     TEXT    NOT NULL,
    saved_at    TEXT    NOT NULL,

    PRIMARY KEY (user_id, name),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── login throttle state (schema v8) ────────────────────────────────────────
--
-- The throttle counted failures in a process-local dict, so a restart handed
-- every attacker a fresh budget -- and a deploy is a restart. Keeping the
-- counters here makes them survive that, and makes them shared if a second
-- worker is ever added, without introducing Redis for two integers.
--
-- Rows are disposable: purge_login_attempts() clears anything past its window.
-- Losing this table costs a throttle reset, nothing more.
CREATE TABLE IF NOT EXISTS login_attempts (
    -- "pair:<ip>|<username>" or "ip:<ip>". One table, two scopes, because they
    -- expire and are purged identically.
    scope_key      TEXT    PRIMARY KEY,
    fails          INTEGER NOT NULL DEFAULT 0,
    -- Wall-clock ISO, not monotonic: monotonic time is meaningless once it has
    -- to outlive the process that read it.
    blocked_until  TEXT,
    first_seen_at  TEXT    NOT NULL,
    last_seen_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_login_attempts_blocked
    ON login_attempts(blocked_until);
