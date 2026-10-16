"""Accounts and their saved configurations.

The only module that knows the shape of the `users` and `user_configs`
tables, mirroring how db/backtests.py owns the result tables.

Sign-in was removed on 2026-10-16: every request runs as one workspace
account (workspace_user below). The session, OAuth, reset-token, throttle and
phone-code functions went with it. Their TABLES were left in place -- dropping
them would be a schema migration for no functional gain, and delete_account
still clears any rows they hold so a closed account leaves nothing behind.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from db.connection import connect

log = logging.getLogger(__name__)


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
    #: The same distinction for the phone number. Nothing is ever texted to a
    #: number where this is False -- see db/schema.sql.
    phone_verified: bool = False


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


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
                                if "email_verified" in cols else False),
                phone_verified=(bool(r["phone_verified"])
                                if "phone_verified" in cols else False))


def workspace_user(db: Path | None = None) -> User:
    """The one account every request runs as. There is no sign-in any more.

    Removed on request, 2026-10-16: the app opens straight from its link, with
    no login, registration or password. The data model is still per-account
    -- saved configurations, the paper-trading session and the journal all
    key on a user id -- so rather than tear that out, every request is simply
    attributed to one account.

    WHICH ONE. The OWNER account if there is one: that is the account that
    holds the Schwab entitlement (users.is_owner), so live data keeps working
    from the link, and it is the account whose saved configurations already
    exist. Otherwise the oldest active account. Otherwise a fresh "workspace"
    account is created, with no usable password -- nothing can log into it,
    because nothing logs in.
    """
    conn = connect(db)
    try:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
        order = "is_owner DESC, id ASC" if "is_owner" in cols else "id ASC"
        row = conn.execute(
            f"SELECT * FROM users WHERE is_active = 1 ORDER BY {order} LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if row is not None:
        return _row_to_user(row)  # type: ignore[return-value]
    uid = create_user("workspace", "!", full_name="Workspace",
                      has_password=False, email_verified=True, db=db)
    return get_user_by_id(uid, db)  # type: ignore[return-value]


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
