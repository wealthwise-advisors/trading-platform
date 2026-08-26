"""Users and sessions.

The only module that knows the shape of the `users` and `sessions` tables,
mirroring how db/backtests.py owns the result tables. api/auth.py talks to
this and nothing else.

A session token is generated as 32 random bytes, handed to the browser once,
and stored here only as its SHA-256. Reading this table therefore does not
yield a usable cookie -- the same reason a password is stored as a hash.
"""

import hashlib
import logging
import secrets
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


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── users ────────────────────────────────────────────────────────────────────
def create_user(username: str, password_hash: str, *, full_name: str = "",
                email: str = "", country: str = "", phone: str = "",
                db: Path | None = None) -> int:
    conn = connect(db)
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, full_name, email, "
            "country, phone, is_active, created_at) VALUES (?,?,?,?,?,?,1,?)",
            (username, password_hash, full_name, email, country, phone, _now()),
        )
        return int(cur.lastrowid)
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
    return User(id=r["id"], username=r["username"], password_hash=r["password_hash"],
                full_name=r["full_name"], email=r["email"], country=r["country"],
                phone=r["phone"], is_active=bool(r["is_active"]))


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
