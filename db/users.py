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
                email_verified: bool = False,
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
            "country, phone, is_active, email_verified, created_at) "
            "VALUES (?,?,?,?,?,?,1,?,?)",
            (username, password_hash, full_name, email, country, phone,
             1 if email_verified else 0, _now()),
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
        cur = conn.execute("UPDATE users SET password_hash = ? WHERE username = ?",
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
    conn = connect(db)
    try:
        cur = conn.execute("DELETE FROM users WHERE username = ?", (username,))
        return cur.rowcount > 0
    finally:
        conn.close()


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
def new_verification_token(user_id: int, token_hash: str, expires_at: str,
                           db: Path | None = None) -> None:
    """Record a verification token, superseding any earlier one.

    Earlier tokens for the same account are deleted rather than left valid:
    asking for a new link should invalidate the old one, or a link forwarded
    to the wrong place stays usable after the person has already noticed and
    requested another.
    """
    conn = connect(db)
    try:
        conn.execute("DELETE FROM email_tokens WHERE user_id = ?", (user_id,))
        conn.execute(
            "INSERT INTO email_tokens (token_hash, user_id, expires_at, created_at) "
            "VALUES (?,?,?,?)", (token_hash, user_id, expires_at, _now()))
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
            "SELECT user_id, expires_at, used_at FROM email_tokens "
            "WHERE token_hash = ?", (token_hash,)).fetchone()
        if row is None or row["used_at"] is not None:
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
                       email_verified=email_verified, db=db)


# ── pending OAuth sign-ups ───────────────────────────────────────────────────
def new_pending_oauth(token_hash: str, provider: str, subject: str,
                      suggested: str, next_path: str, expires_at: str,
                      db: Path | None = None) -> None:
    """Park an identity that needs a username before it can become an account."""
    conn = connect(db)
    try:
        # One pending row per identity: asking again replaces the old handle so
        # an abandoned link cannot be used later.
        conn.execute("DELETE FROM oauth_pending WHERE provider = ? AND subject = ?",
                     (provider, subject))
        conn.execute(
            "INSERT INTO oauth_pending (token_hash, provider, subject, suggested,"
            " next_path, expires_at, created_at) VALUES (?,?,?,?,?,?,?)",
            (token_hash, provider, subject, suggested, next_path, expires_at, _now()))
    finally:
        conn.close()


def take_pending_oauth(token_hash: str, db: Path | None = None):
    """Spend a pending handle. Returns the row, or None.

    Single-use and deleted on read, inside one connection, so two submissions
    of the same form cannot both create an account.
    """
    conn = connect(db)
    try:
        row = conn.execute(
            "SELECT provider, subject, suggested, next_path, expires_at "
            "FROM oauth_pending WHERE token_hash = ?", (token_hash,)).fetchone()
        if row is None or row["expires_at"] <= _now():
            return None
        cur = conn.execute("DELETE FROM oauth_pending WHERE token_hash = ?",
                           (token_hash,))
        if cur.rowcount == 0:
            return None                     # someone else spent it first
        return dict(row)
    finally:
        conn.close()


def purge_pending_oauth(db: Path | None = None) -> int:
    conn = connect(db)
    try:
        return conn.execute("DELETE FROM oauth_pending WHERE expires_at <= ?",
                            (_now(),)).rowcount or 0
    finally:
        conn.close()
