"""Users and sessions.

The only module that knows the shape of the `users`, `sessions`,
`oauth_identities` and `oauth_states` tables, mirroring how db/backtests.py
owns the result tables. api/auth.py talks to this and nothing else.

A session token is generated as 32 random bytes, handed to the browser once,
and stored here only as its SHA-256. Reading this table therefore does not
yield a usable cookie -- the same reason a password is stored as a hash.
"""

import hashlib
import logging
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from db.connection import connect

log = logging.getLogger(__name__)

#: How long a session stays valid without being used again.
SESSION_TTL = timedelta(days=7)

#: Sliding renewal: a session seen within this window of expiry is extended,
#: so an active user is not logged out mid-session, while an abandoned one
#: still ages out.
SESSION_RENEW_WITHIN = timedelta(days=1)


@dataclass(frozen=True)
class User:
    id: int
    username: str
    password_hash: str
    full_name: str
    email: str
    country: str
    phone: str
    is_active: bool
    #: The Schwab entitlement. See users.is_owner in db/schema.sql -- it is not
    #: something an account can earn by signing up or verifying an address.
    is_owner: bool = False
    #: False for an account whose only credential is a provider. See
    #: users.has_password in db/schema.sql.
    has_password: bool = True
    #: Whether the address has been PROVED to belong to the holder, as opposed
    #: to merely typed in. What makes email-matched OAuth safe.
    email_verified: bool = False


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── users ────────────────────────────────────────────────────────────────────
def create_user(username: str, password_hash: str, *, full_name: str = "",
                email: str = "", country: str = "", phone: str = "",
                email_verified: bool = False, has_password: bool = True,
                db: Path | None = None) -> int:
    """Create an account. Raises sqlite3.IntegrityError on a taken name or email.

    `is_owner` is deliberately not a parameter. It is the Schwab entitlement
    and there is exactly one brokerage connection, belonging to the operator --
    so no caller, including a public registration endpoint, can grant it by
    passing an argument. It is set only by scripts/manage_users.py.

    `email_verified` defaults to False and should stay False for anything a
    person typed. Pass True only when an identity provider has positively
    reported the address as verified.
    """
    conn = connect(db)
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, full_name, email, "
            "country, phone, is_active, email_verified, created_at, has_password) "
            "VALUES (?,?,?,?,?,?,1,?,?,?)",
            (username, password_hash, full_name, email, country, phone,
             1 if email_verified else 0, _now(), 1 if has_password else 0),
        )
        return int(cur.lastrowid)
    finally:
        conn.close()


def get_user_by_email(email: str, db: Path | None = None) -> User | None:
    """Find an account by address. Empty never matches.

    The empty string is the default for an account with no address, so a blank
    lookup would otherwise return an arbitrary one of them -- which, on the
    OAuth path that matches by address, is somebody else's account.
    """
    if not (email or "").strip():
        return None
    conn = connect(db)
    try:
        return _row_to_user(conn.execute(
            "SELECT * FROM users WHERE email = ? AND email != ''",
            (email.strip(),)).fetchone())
    finally:
        conn.close()


def set_email_verified(user_id: int, verified: bool = True,
                       db: Path | None = None) -> bool:
    conn = connect(db)
    try:
        cur = conn.execute("UPDATE users SET email_verified = ? WHERE id = ?",
                           (1 if verified else 0, user_id))
        return cur.rowcount > 0
    finally:
        conn.close()


def get_user(username: str, db: Path | None = None) -> User | None:
    conn = connect(db)
    try:
        r = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    finally:
        conn.close()
    return _row_to_user(r)


def get_user_by_id(user_id: int, db: Path | None = None) -> User | None:
    conn = connect(db)
    try:
        r = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    finally:
        conn.close()
    return _row_to_user(r)


def _row_to_user(r) -> User | None:
    if r is None:
        return None
    # .keys() rather than direct indexing: this same function reads rows from a
    # database that may not have been migrated yet in a test, and a missing
    # column should degrade to the safe default (not an owner, not verified)
    # rather than raising.
    cols = r.keys()
    return User(id=r["id"], username=r["username"], password_hash=r["password_hash"],
                full_name=r["full_name"], email=r["email"], country=r["country"],
                phone=r["phone"], is_active=bool(r["is_active"]),
                is_owner=bool(r["is_owner"]) if "is_owner" in cols else False,
                has_password=(bool(r["has_password"])
                              if "has_password" in cols else True),
                email_verified=(bool(r["email_verified"])
                                if "email_verified" in cols else False))


def list_users(db: Path | None = None) -> list[dict]:
    conn = connect(db)
    try:
        return [
            {k: r[k] for k in ("id", "username", "full_name", "email", "country",
                               "is_active", "created_at", "last_login_at")}
            for r in conn.execute("SELECT * FROM users ORDER BY id")
        ]
    finally:
        conn.close()


def set_password(username: str, password_hash: str, db: Path | None = None) -> bool:
    conn = connect(db)
    try:
        cur = conn.execute("UPDATE users SET password_hash = ?, has_password = 1 "
                           "WHERE username = ?",
                           (password_hash, username))
        return cur.rowcount > 0
    finally:
        conn.close()


def set_active(username: str, active: bool, db: Path | None = None) -> bool:
    conn = connect(db)
    try:
        cur = conn.execute("UPDATE users SET is_active = ? WHERE username = ?",
                           (1 if active else 0, username))
        changed = cur.rowcount > 0
        if changed and not active:
            # Deactivating must end the sessions too, or the account stays
            # usable until its cookie happens to expire.
            conn.execute(
                "DELETE FROM sessions WHERE user_id = (SELECT id FROM users "
                "WHERE username = ?)", (username,))
        return changed
    finally:
        conn.close()


def delete_user(username: str, db: Path | None = None) -> bool:
    """Remove the account row only.

    Kept as it was, and it still RAISES sqlite3.IntegrityError when the person
    owns a backtest -- `backtests.user_id` references this row with no ON
    DELETE action, so SQLite refuses. That refusal is the correct answer for a
    bare row delete: the alternative is a dangling user_id. Callers that mean
    "close this account" want delete_account() below, which deals with the
    dependents first.
    """
    conn = connect(db)
    try:
        cur = conn.execute("DELETE FROM users WHERE username = ?", (username,))
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_account(user_id: int, *, keep_results: bool = False,
                   db: Path | None = None) -> dict | None:
    """Close an account for good. Returns what was removed, or None if no such id.

    WHY THIS IS DELETION AND NOT ANONYMISATION
    ------------------------------------------
    schema.sql declines ON DELETE CASCADE on `backtests.user_id`, reasoning
    that removing a person should not silently destroy the record of what was
    run. That reasoning holds for the SILENT part, and this function keeps it:
    the removal is explicit, counted and logged.

    It does not hold for keeping the rows. Every read path is scoped by
    user_id -- api/routers/backtests.py routes everything through
    _get_or_404(id, user) -- so a backtest whose owner is gone is reachable by
    nobody. Retaining it stores a person's trading history, plus its Parquet
    sidecars, in a form that serves no reader and that web/public/privacy.html
    §6 promises to delete on request. Dead data is not a safer default than no
    data.

    `keep_results=True` is the operator's escape hatch for the case the schema
    comment had in mind -- a run whose record must outlive the account. It
    detaches the rows (user_id NULL) instead of removing them, and is reachable
    only from scripts/manage_users.py, never from an HTTP route.

    Sessions, email tokens and OAuth identities are ON DELETE CASCADE already,
    so they go with the user row. Backtests and trades are not, and are dealt
    with here, before it.
    """
    conn = connect(db)
    try:
        row = conn.execute("SELECT username FROM users WHERE id = ?",
                           (user_id,)).fetchone()
        if row is None:
            return None
        username = row["username"]

        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM backtests WHERE user_id = ?", (user_id,))]

        # One transaction: a half-deleted account is worse than a failed
        # delete, because the caller is told it worked.
        conn.execute("BEGIN IMMEDIATE")
        try:
            sessions = conn.execute(
                "SELECT COUNT(*) AS n FROM sessions WHERE user_id = ?",
                (user_id,)).fetchone()["n"]
            if keep_results:
                conn.execute("UPDATE trades    SET user_id = NULL WHERE user_id = ?",
                             (user_id,))
                conn.execute("UPDATE backtests SET user_id = NULL WHERE user_id = ?",
                             (user_id,))
                trades = 0
            else:
                trades = conn.execute("DELETE FROM trades WHERE user_id = ?",
                                      (user_id,)).rowcount
                conn.execute("DELETE FROM backtests WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()

    removed = {
        "username": username,
        "backtests": 0 if keep_results else len(ids),
        "backtests_detached": len(ids) if keep_results else 0,
        "trades": trades,
        "sessions": sessions,
        "backtest_ids": [] if keep_results else ids,
    }
    log.info("account closed: %s (backtests=%s detached=%s trades=%s sessions=%s)",
             username, removed["backtests"], removed["backtests_detached"],
             removed["trades"], removed["sessions"])
    return removed


def touch_login(user_id: int, db: Path | None = None) -> None:
    conn = connect(db)
    try:
        conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (_now(), user_id))
    finally:
        conn.close()


# ── sessions ─────────────────────────────────────────────────────────────────
def new_session(user_id: int, *, user_agent: str = "", ip: str = "",
                db: Path | None = None) -> str:
    """Create a session and return the RAW token -- the only time it exists."""
    raw = secrets.token_urlsafe(32)
    now = datetime.now()
    conn = connect(db)
    try:
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at, expires_at, "
            "last_seen_at, user_agent, ip) VALUES (?,?,?,?,?,?,?)",
            (hash_token(raw), user_id, now.isoformat(timespec="seconds"),
             (now + SESSION_TTL).isoformat(timespec="seconds"),
             now.isoformat(timespec="seconds"), user_agent[:200], ip[:64]),
        )
    finally:
        conn.close()
    return raw


def resolve_session(raw: str, db: Path | None = None) -> User | None:
    """The user behind a cookie, or None if it is unknown, expired or disabled."""
    if not raw:
        return None
    conn = connect(db)
    try:
        r = conn.execute(
            "SELECT s.token_hash, s.expires_at, u.* FROM sessions s "
            "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
            (hash_token(raw),),
        ).fetchone()
        if r is None:
            return None

        now = datetime.now()
        if datetime.fromisoformat(r["expires_at"]) <= now:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (r["token_hash"],))
            return None
        if not r["is_active"]:
            return None

        # sliding renewal, only when it is close to lapsing
        if datetime.fromisoformat(r["expires_at"]) - now < SESSION_RENEW_WITHIN:
            conn.execute("UPDATE sessions SET expires_at = ? WHERE token_hash = ?",
                         ((now + SESSION_TTL).isoformat(timespec="seconds"),
                          r["token_hash"]))
        conn.execute("UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?",
                     (now.isoformat(timespec="seconds"), r["token_hash"]))
        return _row_to_user(r)
    finally:
        conn.close()


def revoke_session(raw: str, db: Path | None = None) -> bool:
    conn = connect(db)
    try:
        cur = conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(raw),))
        return cur.rowcount > 0
    finally:
        conn.close()


def revoke_all(user_id: int, db: Path | None = None) -> int:
    conn = connect(db)
    try:
        return conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,)).rowcount
    finally:
        conn.close()


def purge_expired(db: Path | None = None) -> int:
    conn = connect(db)
    try:
        return conn.execute("DELETE FROM sessions WHERE expires_at <= ?",
                            (_now(),)).rowcount
    finally:
        conn.close()


# ── OAuth identities ─────────────────────────────────────────────────────────
# A link between an existing local account and one provider account. Creating a
# link never creates a USER -- see api/routers/oauth.py for the rule these
# functions serve.

@dataclass(frozen=True)
class Identity:
    provider: str
    subject: str
    email: str
    user_id: int
    linked_at: str
    last_used_at: str | None


def link_identity(user_id: int, provider: str, subject: str, *, email: str = "",
                  db: Path | None = None) -> bool:
    """Bind a provider account to a local user.

    Returns False if that provider account is already bound -- to this user or
    to anyone else. It is never re-pointed here: silently moving a link would
    let whoever controls the provider account take over a different login.
    """
    conn = connect(db)
    try:
        conn.execute(
            "INSERT INTO oauth_identities (user_id, provider, subject, email, "
            "linked_at) VALUES (?,?,?,?,?)",
            (user_id, provider, subject, email, _now()),
        )
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def identity_user(provider: str, subject: str, db: Path | None = None) -> User | None:
    """The local user a provider account signs in as, if it has been linked."""
    conn = connect(db)
    try:
        r = conn.execute(
            "SELECT u.* FROM oauth_identities i JOIN users u ON u.id = i.user_id "
            "WHERE i.provider = ? AND i.subject = ?", (provider, subject),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_user(r)


def touch_identity(provider: str, subject: str, db: Path | None = None) -> None:
    conn = connect(db)
    try:
        conn.execute("UPDATE oauth_identities SET last_used_at = ? "
                     "WHERE provider = ? AND subject = ?", (_now(), provider, subject))
    finally:
        conn.close()


def unlink_identity(user_id: int, provider: str, db: Path | None = None) -> int:
    conn = connect(db)
    try:
        return conn.execute("DELETE FROM oauth_identities WHERE user_id = ? "
                            "AND provider = ?", (user_id, provider)).rowcount
    finally:
        conn.close()


def list_identities(user_id: int | None = None, db: Path | None = None) -> list[Identity]:
    conn = connect(db)
    try:
        sql = ("SELECT provider, subject, email, user_id, linked_at, last_used_at "
               "FROM oauth_identities")
        args: tuple = ()
        if user_id is not None:
            sql += " WHERE user_id = ?"
            args = (user_id,)
        return [Identity(**dict(r)) for r in conn.execute(sql + " ORDER BY provider", args)]
    finally:
        conn.close()


# ── OAuth in-flight state ────────────────────────────────────────────────────
# One row per authorization request we have started but not yet completed. The
# PKCE verifier lives here and never leaves the server.

#: How long a started sign-in may take before it has to be restarted.
OAUTH_STATE_TTL = timedelta(minutes=10)


@dataclass(frozen=True)
class OAuthState:
    provider: str
    code_verifier: str
    next_path: str


def new_oauth_state(provider: str, code_verifier: str, next_path: str,
                    db: Path | None = None) -> str:
    """Record a started sign-in and return the opaque state to send onward."""
    state = secrets.token_urlsafe(32)
    now = datetime.now()
    conn = connect(db)
    try:
        conn.execute(
            "INSERT INTO oauth_states (state, provider, code_verifier, next_path, "
            "created_at, expires_at) VALUES (?,?,?,?,?,?)",
            (state, provider, code_verifier, next_path,
             now.isoformat(timespec="seconds"),
             (now + OAUTH_STATE_TTL).isoformat(timespec="seconds")),
        )
    finally:
        conn.close()
    return state


def take_oauth_state(state: str, db: Path | None = None) -> OAuthState | None:
    """Consume a state. Single use -- the row is deleted whether or not it was
    still valid, so a replayed callback finds nothing the second time."""
    if not state:
        return None
    conn = connect(db)
    try:
        r = conn.execute("SELECT * FROM oauth_states WHERE state = ?", (state,)).fetchone()
        if r is None:
            return None
        conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
        if datetime.fromisoformat(r["expires_at"]) <= datetime.now():
            return None
        return OAuthState(provider=r["provider"], code_verifier=r["code_verifier"],
                          next_path=r["next_path"])
    finally:
        conn.close()


def purge_oauth_states(db: Path | None = None) -> int:
    conn = connect(db)
    try:
        return conn.execute("DELETE FROM oauth_states WHERE expires_at <= ?",
                            (_now(),)).rowcount
    finally:
        conn.close()


# ── email verification tokens ────────────────────────────────────────────────
def new_email_token(user_id: int, token_hash: str, expires_at: str,
                    purpose: str = "verify", db: Path | None = None) -> None:
    """Record a token, superseding any earlier one FOR THE SAME PURPOSE.

    Earlier tokens are deleted rather than left valid: asking for a new link
    should invalidate the old one, or a link forwarded to the wrong place stays
    usable after the person has noticed and requested another.

    Scoped by purpose, which is the whole reason that column exists. An
    unscoped delete means sending a verification email destroys a password
    reset the same person requested a minute earlier, and the link already
    sitting in their inbox fails for no visible reason.
    """
    conn = connect(db)
    try:
        conn.execute("DELETE FROM email_tokens WHERE user_id = ? AND purpose = ?",
                     (user_id, purpose))
        conn.execute(
            "INSERT INTO email_tokens (token_hash, user_id, expires_at, created_at,"
            " purpose) VALUES (?,?,?,?,?)",
            (token_hash, user_id, expires_at, _now(), purpose))
    finally:
        conn.close()


def new_verification_token(user_id: int, token_hash: str, expires_at: str,
                           db: Path | None = None) -> None:
    """Back-compatible alias for the verification case."""
    new_email_token(user_id, token_hash, expires_at, purpose="verify", db=db)


def take_reset_token(token_hash: str, new_password_hash: str,
                     db: Path | None = None) -> int | None:
    """Spend a reset token and set the new password. Returns the user id.

    None for unknown, already-used, expired and wrong-purpose alike -- there is
    nothing an unauthenticated caller gains from being told which.

    Everything happens in ONE transaction: the token is marked used, the
    password is replaced, and every session that user had is revoked. Split
    across separate connections, a crash between them could leave a spent token
    with the old password still in place, or a changed password with the
    attacker's session still live.

    Revoking sessions is the point of the whole flow, not a nicety. Someone
    resets a password because they think another person has it -- and if that
    person is already signed in, leaving their session alive means the reset
    changed nothing for them.
    """
    conn = connect(db)
    try:
        row = conn.execute(
            "SELECT user_id, expires_at, used_at, purpose FROM email_tokens "
            "WHERE token_hash = ?", (token_hash,)).fetchone()
        if row is None or row["used_at"] is not None:
            return None
        # A verification link must not be spendable as a password reset.
        if row["purpose"] != "reset":
            return None
        if row["expires_at"] <= _now():
            return None

        conn.execute("BEGIN")
        cur = conn.execute(
            "UPDATE email_tokens SET used_at = ? WHERE token_hash = ? "
            "AND used_at IS NULL", (_now(), token_hash))
        if cur.rowcount == 0:
            conn.execute("ROLLBACK")        # someone else spent it first
            return None
        conn.execute("UPDATE users SET password_hash = ?, has_password = 1 "
                     "WHERE id = ?", (new_password_hash, row["user_id"]))
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (row["user_id"],))
        # Any other outstanding reset for this account dies with it.
        conn.execute("DELETE FROM email_tokens WHERE user_id = ? AND purpose = 'reset'"
                     " AND token_hash != ?", (row["user_id"], token_hash))
        conn.execute("COMMIT")
        return int(row["user_id"])
    finally:
        conn.close()


def take_verification_token(token_hash: str, db: Path | None = None) -> int | None:
    """Spend a token and mark the address verified. Returns the user id.

    None for unknown, already-used and expired alike. Single-use is enforced
    here rather than by the caller, inside the same connection that marks the
    account, so two simultaneous clicks cannot both succeed.
    """
    conn = connect(db)
    try:
        row = conn.execute(
            "SELECT user_id, expires_at, used_at, purpose FROM email_tokens "
            "WHERE token_hash = ?", (token_hash,)).fetchone()
        if row is None or row["used_at"] is not None:
            return None
        # Symmetrical with take_reset_token: the two are not interchangeable.
        if row["purpose"] != "verify":
            return None
        if row["expires_at"] <= _now():
            return None
        conn.execute("BEGIN")
        cur = conn.execute(
            "UPDATE email_tokens SET used_at = ? WHERE token_hash = ? "
            "AND used_at IS NULL", (_now(), token_hash))
        if cur.rowcount == 0:
            conn.execute("ROLLBACK")       # someone else spent it first
            return None
        conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?",
                     (row["user_id"],))
        conn.execute("COMMIT")
        return int(row["user_id"])
    finally:
        conn.close()


# ── OAuth account creation ───────────────────────────────────────────────────
def username_from(seed: str, db: Path | None = None) -> str:
    """A free username derived from an email local part or a display name.

    Providers hand back things like "Akash Nandepu" or "a.nandepu+news@x.com".
    This reduces that to something the username rules accept, then appends a
    number until it is free. It is only a SUGGESTION for the account that gets
    created -- nothing here is authoritative, and the person can be given the
    chance to change it.
    """
    import re as _re

    base = _re.sub(r"[^a-zA-Z0-9._-]", "", (seed or "").split("@")[0].replace(" ", "."))
    base = _re.sub(r"[._-]{2,}", ".", base).strip("._-").lower()[:24]
    if len(base) < 3:
        base = f"user{base}" if base else "user"

    if get_user(base, db) is None:
        return base
    # Bounded: a suffix search that never terminates is a hang, not a name.
    for n in range(2, 1000):
        candidate = f"{base}{n}"[:32]
        if get_user(candidate, db) is None:
            return candidate
    import secrets as _secrets
    return f"{base[:20]}{_secrets.token_hex(4)}"


def create_oauth_user(username: str, *, full_name: str = "", email: str = "",
                      email_verified: bool = False,
                      db: Path | None = None) -> int:
    """Create an account that has no password and cannot be signed into with one.

    password_hash is NOT NULL, so something has to go there. It is a hash of
    random bytes that are immediately discarded: no string verifies against it,
    including the empty one. That matters -- a placeholder like '' or 'x' would
    make the account reachable by anyone who guessed the placeholder, turning
    every OAuth account into a password account with a known password.

    The person can set a real password later; until then the provider is the
    only way in.
    """
    import secrets as _secrets

    from api.auth import hash_password        # local: avoids a circular import

    unusable = hash_password(_secrets.token_urlsafe(32))
    return create_user(username, unusable, full_name=full_name, email=email,
                       email_verified=email_verified, has_password=False, db=db)


# ── saved backtest configurations (v8) ───────────────────────────────────────
#
# Every function here takes user_id and no default, matching the rule the rest
# of this module follows: a forgotten owner is a TypeError, never a leak.

def list_configs(user_id: int, db: Path | None = None) -> list[dict]:
    conn = connect(db)
    try:
        return [{"name": r["name"], "saved_at": r["saved_at"],
                 "payload": r["payload"]}
                for r in conn.execute(
                    "SELECT name, saved_at, payload FROM user_configs "
                    "WHERE user_id = ? ORDER BY saved_at DESC", (user_id,))]
    finally:
        conn.close()


def save_config(user_id: int, name: str, payload: str,
                db: Path | None = None) -> str:
    """Create or replace one named config. Returns its saved_at.

    UPSERT rather than delete-then-insert: saving over a name that already
    exists is the common case (adjust a knob, save again), and the two-step
    version leaves a window where the config exists nowhere.
    """
    now = _now()
    conn = connect(db)
    try:
        conn.execute(
            "INSERT INTO user_configs (user_id, name, payload, saved_at) "
            "VALUES (?,?,?,?) "
            "ON CONFLICT(user_id, name) DO UPDATE SET "
            "payload = excluded.payload, saved_at = excluded.saved_at",
            (user_id, name, payload, now))
        return now
    finally:
        conn.close()


def delete_config(user_id: int, name: str, db: Path | None = None) -> bool:
    """Remove one of THIS user's configs. False if they do not have it.

    Scoped by user_id in the WHERE clause, not checked afterwards: the delete
    simply cannot reach a row belonging to somebody else, so there is no
    ordering of checks that could get it wrong.
    """
    conn = connect(db)
    try:
        cur = conn.execute(
            "DELETE FROM user_configs WHERE user_id = ? AND name = ?",
            (user_id, name))
        return cur.rowcount > 0
    finally:
        conn.close()


# ── onboarding (v8) ──────────────────────────────────────────────────────────

def mark_onboarded(user_id: int, db: Path | None = None) -> bool:
    """Record that this person has seen the introduction. Idempotent.

    Only ever sets the timestamp if it is NULL, so pressing Skip twice -- or a
    duplicate request -- does not move the date and cannot be used to make an
    old account look new.
    """
    conn = connect(db)
    try:
        cur = conn.execute(
            "UPDATE users SET onboarded_at = ? "
            "WHERE id = ? AND onboarded_at IS NULL", (_now(), user_id))
        return cur.rowcount > 0
    finally:
        conn.close()


def is_onboarded(user_id: int, db: Path | None = None) -> bool:
    conn = connect(db)
    try:
        r = conn.execute("SELECT onboarded_at FROM users WHERE id = ?",
                         (user_id,)).fetchone()
    finally:
        conn.close()
    return bool(r and r["onboarded_at"])


# ── the account's own data, for export (v8) ──────────────────────────────────

def export_account(user_id: int, db: Path | None = None) -> dict | None:
    """Everything this account holds, as plain data. None if no such id.

    web/public/privacy.html §6 offers "a copy of your data" and there was no
    code that could produce one; the operator would have had to hand-write SQL.
    This is that copy.

    What is deliberately NOT in it:

    * `password_hash` -- an argon2 digest is a credential, not information
      about you. Handing it out in a file someone may email to themselves is a
      downgrade in security for no gain.
    * session and email token hashes -- same reasoning; they are keys.

    Session METADATA is included (when, from where, which browser), because
    "where has my account been signed in" is exactly the kind of question a
    data export exists to answer.
    """
    conn = connect(db)
    try:
        u = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if u is None:
            return None

        def rows(sql, *args):
            return [dict(r) for r in conn.execute(sql, args)]

        account = {k: u[k] for k in u.keys()
                   if k not in {"password_hash", "id"}}
        return {
            "exported_at": _now(),
            "account": account,
            "sessions": rows(
                "SELECT created_at, expires_at, last_seen_at, ip, user_agent "
                "FROM sessions WHERE user_id = ? ORDER BY created_at", user_id),
            "oauth_identities": rows(
                "SELECT provider, email, linked_at FROM oauth_identities "
                "WHERE user_id = ? ORDER BY linked_at", user_id),
            "saved_configs": rows(
                "SELECT name, saved_at, payload FROM user_configs "
                "WHERE user_id = ? ORDER BY saved_at", user_id),
            "backtests": rows(
                "SELECT * FROM backtests WHERE user_id = ? ORDER BY created_at",
                user_id),
            "trades": rows(
                "SELECT * FROM trades WHERE user_id = ? "
                "ORDER BY backtest_id, seq", user_id),
        }
    finally:
        conn.close()


# ── login throttle state (v8) ────────────────────────────────────────────────
#
# The counters used to live in a process-local dict, so every restart -- and a
# deploy is a restart -- handed an attacker a fresh budget. These four
# functions are the same buckets, kept where they survive that.

def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def throttle_blocked_for(scope_key: str, db: Path | None = None) -> int:
    """Seconds still to wait on this key, or 0."""
    conn = connect(db)
    try:
        r = conn.execute(
            "SELECT blocked_until FROM login_attempts WHERE scope_key = ?",
            (scope_key,)).fetchone()
    finally:
        conn.close()
    until = _parse(r["blocked_until"]) if r else None
    if until is None:
        return 0
    remaining = (until - datetime.now()).total_seconds()
    return int(remaining) + 1 if remaining > 0 else 0


def throttle_record_failure(scope_key: str, *, max_fails: int,
                            block_seconds: int, window_seconds: int | None = None,
                            db: Path | None = None) -> None:
    """Count one failure against this key, blocking it once it hits max_fails.

    `window_seconds` gives the per-IP ceiling its budget back after a quiet
    period. It is a FIXED window rather than the sliding one the in-memory
    version used -- that kept a timestamp per failure, which is a list to store
    and prune per row for no protective gain. The property that matters is
    unchanged: N failures inside the window blocks the key.
    """
    now = datetime.now()
    now_iso = now.isoformat(timespec="seconds")
    conn = connect(db)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            r = conn.execute(
                "SELECT fails, first_seen_at FROM login_attempts WHERE scope_key = ?",
                (scope_key,)).fetchone()

            fails = (r["fails"] if r else 0) + 1
            first = _parse(r["first_seen_at"]) if r else None
            if window_seconds and first and (now - first).total_seconds() > window_seconds:
                fails, first = 1, now          # the window rolled over

            blocked_until = None
            if fails >= max_fails:
                blocked_until = (now + timedelta(seconds=block_seconds)
                                 ).isoformat(timespec="seconds")
                fails = 0                      # spent, as in the original

            conn.execute(
                "INSERT INTO login_attempts "
                "(scope_key, fails, blocked_until, first_seen_at, last_seen_at) "
                "VALUES (?,?,?,?,?) "
                "ON CONFLICT(scope_key) DO UPDATE SET "
                "fails = excluded.fails, "
                # COALESCE so a fresh block never shortens one already running.
                "blocked_until = COALESCE(excluded.blocked_until, login_attempts.blocked_until), "
                "first_seen_at = excluded.first_seen_at, "
                "last_seen_at = excluded.last_seen_at",
                (scope_key, fails, blocked_until,
                 (first or now).isoformat(timespec="seconds"), now_iso))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def throttle_failures(scope_key: str, db: Path | None = None) -> int:
    """Failures recorded against this key, or 0. Never raises."""
    conn = connect(db)
    try:
        r = conn.execute("SELECT fails FROM login_attempts WHERE scope_key = ?",
                         (scope_key,)).fetchone()
    finally:
        conn.close()
    return int(r["fails"]) if r else 0


def throttle_clear(scope_key: str, db: Path | None = None) -> None:
    conn = connect(db)
    try:
        conn.execute("DELETE FROM login_attempts WHERE scope_key = ?", (scope_key,))
    finally:
        conn.close()


def purge_login_attempts(db: Path | None = None) -> int:
    """Drop rows that can no longer block anything."""
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat(timespec="seconds")
    conn = connect(db)
    try:
        cur = conn.execute(
            "DELETE FROM login_attempts WHERE last_seen_at < ? "
            "AND (blocked_until IS NULL OR blocked_until < ?)",
            (cutoff, datetime.now().isoformat(timespec="seconds")))
        return cur.rowcount
    finally:
        conn.close()


def take_login_code(user_id: int, code: str, max_attempts: int,
                    db: Path | None = None) -> bool:
    """Spend a sign-in code. True only for the right one, once.

    Looked up by OWNER rather than by the code's hash, which is the whole
    reason a wrong guess can be counted at all: a lookup keyed on the hash
    simply finds nothing when the guess is wrong, leaving nowhere to record
    that an attempt happened and no way to ever stop guessing.

    The code dies on the max_attempts-th wrong answer rather than merely
    refusing it. Six digits is a million combinations, so a code that survives
    unlimited guesses is a password with a very small alphabet.
    """
    now = _now()
    conn = connect(db)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            r = conn.execute(
                "SELECT token_hash, expires_at, used_at, attempts FROM email_tokens "
                "WHERE user_id = ? AND purpose = 'login'", (user_id,)).fetchone()
            if r is None or r["used_at"]:
                conn.execute("COMMIT")
                return False
            if datetime.fromisoformat(r["expires_at"]) <= datetime.now():
                conn.execute("DELETE FROM email_tokens WHERE token_hash = ?",
                             (r["token_hash"],))
                conn.execute("COMMIT")
                return False

            if not secrets.compare_digest(r["token_hash"],
                                          hash_token(f"{user_id}:{code}")):
                spent = r["attempts"] + 1
                if spent >= max_attempts:
                    conn.execute("DELETE FROM email_tokens WHERE token_hash = ?",
                                 (r["token_hash"],))
                    log.warning("sign-in code destroyed after %d wrong attempts "
                                "for user %s", spent, user_id)
                else:
                    conn.execute("UPDATE email_tokens SET attempts = ? "
                                 "WHERE token_hash = ?", (spent, r["token_hash"]))
                conn.execute("COMMIT")
                return False

            # Correct. Spend it -- deleted, not merely marked, because unlike a
            # reset link there is no second click to tell apart from a forgery.
            conn.execute("DELETE FROM email_tokens WHERE token_hash = ?",
                         (r["token_hash"],))
            conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?",
                         (now, user_id))
            conn.execute("COMMIT")
            return True
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
