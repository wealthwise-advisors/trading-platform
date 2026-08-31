"""Signing in with an emailed six-digit code.

WHY A CODE IS A DIFFERENT PROBLEM FROM A LINK
---------------------------------------------
The reset and confirmation links are 32 random bytes. Guessing one is not a
threat and never will be, so their safety is entirely in their length.

A six-digit code has a million values. Length cannot save it, so two other
things must: it expires in ten minutes, and it is DESTROYED on the fifth wrong
answer. Both are asserted below, because a code that survives unlimited
guessing is a password with an alphabet of ten.

The other half is enumeration. A route that emails a code is a membership
oracle unless it answers identically for an address that has no account -- the
same problem /forgot-password solves, solved the same way.

Registered in tests/conftest.py's _SECURITY_SUITES: most of this file asserts
refusals, and under the session-wide require_user override they would pass
without reaching the guard.
"""

import re

import pytest
from fastapi.testclient import TestClient

from api import auth, verification
from api.main import app
from db import connection
from db import users as repo

PASSWORD = "Correct-Horse-99-Battery"


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "code.db")
    for name in ("throttle", "signup_throttle", "recovery_throttle",
                 "username_throttle", "verify_throttle"):
        monkeypatch.setattr(auth, name, type(getattr(auth, name))())
    monkeypatch.setattr(auth, "_INSECURE", True)
    monkeypatch.setenv(verification.SMTP_HOST_ENV, "smtp.example.test")
    monkeypatch.setenv(verification.SMTP_USER_ENV, "a@example.test")
    monkeypatch.setenv(verification.SMTP_PASSWORD_ENV, "x")
    monkeypatch.setenv(verification.FROM_ENV, "a@example.test")
    monkeypatch.setenv(verification.BASE_URL_ENV, "https://example.test")
    return tmp_path


@pytest.fixture
def sent(monkeypatch):
    """Every message the app tried to deliver, as (to, subject, body)."""
    out = []
    monkeypatch.setattr(verification, "_deliver",
                        lambda to, subject, body, what="": out.append(
                            (to, subject, body)) or True)
    return out


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        yield c


def make_user(username="trader", email="t@example.com", verified=True, **kw):
    return repo.create_user(username, auth.hash_password(PASSWORD),
                            email=email, email_verified=verified, **kw)


def code_from(sent):
    m = re.search(r"\b(\d{6})\b", sent[-1][2])
    return m.group(1) if m else None


def observable(r):
    return (r.status_code, r.text, "set-cookie" in r.headers)


# ── the happy path ───────────────────────────────────────────────────────────

def test_a_code_arrives_and_signs_you_in(client, db, sent):
    make_user()

    r = client.post("/api/auth/request-code", json={"email": "t@example.com"})
    assert r.status_code == 200
    assert len(sent) == 1
    code = code_from(sent)
    assert code and len(code) == 6

    r = client.post("/api/auth/verify-code",
                    json={"email": "t@example.com", "code": code})

    assert r.status_code == 200
    assert "set-cookie" in r.headers
    assert r.json()["username"] == "trader"
    assert client.get("/api/auth/me").status_code == 200


def test_the_code_is_six_digits_not_four(db):
    """Four digits was asked for. Ten thousand combinations is not enough."""
    assert verification.LOGIN_CODE_DIGITS == 6
    uid = make_user()
    assert re.fullmatch(r"\d{6}", verification.new_login_code(uid))


def test_an_account_with_no_password_can_still_use_it(client, db, sent):
    """The point of the feature: a credential resting on the inbox instead."""
    make_user("googler", "g@example.com", has_password=False)

    client.post("/api/auth/request-code", json={"email": "g@example.com"})
    r = client.post("/api/auth/verify-code",
                    json={"email": "g@example.com", "code": code_from(sent)})

    assert r.status_code == 200


# ── the code's own defences ──────────────────────────────────────────────────

def test_a_code_works_once(client, db, sent):
    make_user()
    client.post("/api/auth/request-code", json={"email": "t@example.com"})
    code = code_from(sent)

    first = client.post("/api/auth/verify-code",
                        json={"email": "t@example.com", "code": code})
    second = client.post("/api/auth/verify-code",
                         json={"email": "t@example.com", "code": code})

    assert first.status_code == 200
    assert second.status_code == 401


def test_a_code_dies_after_five_wrong_guesses(client, db, sent):
    """The control that makes six digits safe. Without it this is guessable."""
    make_user()
    client.post("/api/auth/request-code", json={"email": "t@example.com"})
    real = code_from(sent)

    wrong = "000000" if real != "000000" else "111111"
    for _ in range(verification.LOGIN_CODE_MAX_ATTEMPTS):
        client.post("/api/auth/verify-code",
                    json={"email": "t@example.com", "code": wrong})

    # Even the CORRECT code is now refused -- the row is gone, not just locked.
    r = client.post("/api/auth/verify-code",
                    json={"email": "t@example.com", "code": real})
    assert r.status_code == 401

    conn = connection.connect()
    try:
        left = conn.execute("SELECT COUNT(*) AS n FROM email_tokens "
                            "WHERE purpose = 'login'").fetchone()["n"]
    finally:
        conn.close()
    assert left == 0


def test_an_expired_code_is_refused(client, db, sent):
    from datetime import datetime, timedelta
    assert verification.LOGIN_CODE_TTL <= timedelta(minutes=15)

    uid = make_user()
    client.post("/api/auth/request-code", json={"email": "t@example.com"})
    code = code_from(sent)

    conn = connection.connect()
    try:
        conn.execute("UPDATE email_tokens SET expires_at = ? WHERE purpose = 'login'",
                     ((datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds"),))
    finally:
        conn.close()

    r = client.post("/api/auth/verify-code",
                    json={"email": "t@example.com", "code": code})
    assert r.status_code == 401
    assert repo.get_user_by_id(uid) is not None      # the account is untouched


def test_asking_again_invalidates_the_previous_code(client, db, sent):
    make_user()
    client.post("/api/auth/request-code", json={"email": "t@example.com"})
    first = code_from(sent)
    auth.recovery_throttle.__init__()
    client.post("/api/auth/request-code", json={"email": "t@example.com"})
    second = code_from(sent)

    assert first != second
    assert client.post("/api/auth/verify-code",
                       json={"email": "t@example.com", "code": first}).status_code == 401
    assert client.post("/api/auth/verify-code",
                       json={"email": "t@example.com", "code": second}).status_code == 200


def test_the_raw_code_is_never_stored(client, db, sent):
    make_user()
    client.post("/api/auth/request-code", json={"email": "t@example.com"})
    code = code_from(sent)

    conn = connection.connect()
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM email_tokens")]
    finally:
        conn.close()
    for row in rows:
        for value in row.values():
            assert code != str(value)


def test_one_users_code_does_not_work_for_another(client, db, sent):
    """The hash is bound to the owner, so a digest cannot be replayed sideways."""
    make_user("alice", "a@example.com")
    make_user("bob", "b@example.com")

    client.post("/api/auth/request-code", json={"email": "a@example.com"})
    alices = code_from(sent)

    r = client.post("/api/auth/verify-code",
                    json={"email": "b@example.com", "code": alices})
    assert r.status_code == 401


# ── enumeration ──────────────────────────────────────────────────────────────

def test_requesting_a_code_answers_identically_for_a_stranger(client, db, sent):
    make_user()

    known = client.post("/api/auth/request-code", json={"email": "t@example.com"})
    auth.recovery_throttle.__init__()
    unknown = client.post("/api/auth/request-code", json={"email": "nobody@example.com"})

    assert observable(known) == observable(unknown)
    assert len(sent) == 1              # only the real one was actually sent


def test_verifying_answers_identically_for_a_stranger(client, db, sent):
    make_user()
    client.post("/api/auth/request-code", json={"email": "t@example.com"})

    wrong = client.post("/api/auth/verify-code",
                        json={"email": "t@example.com", "code": "000000"})
    stranger = client.post("/api/auth/verify-code",
                           json={"email": "nobody@example.com", "code": "000000"})

    assert observable(wrong) == observable(stranger)


def test_an_unverified_address_gets_no_code(client, db, sent):
    """A code sent to an unproved address hands a way in to whoever typed it.

    Same reasoning that stops /forgot-password issuing a reset link to an
    OAuth-only account whose address nobody confirmed.
    """
    make_user("unproved", "u@example.com", verified=False)

    r = client.post("/api/auth/request-code", json={"email": "u@example.com"})

    assert r.status_code == 200        # identical answer, still no oracle
    assert sent == []                  # and nothing was actually sent


def test_a_disabled_account_gets_no_code(client, db, sent):
    make_user("gone", "g@example.com")
    repo.set_active("gone", False)

    r = client.post("/api/auth/request-code", json={"email": "g@example.com"})

    assert r.status_code == 200
    assert sent == []


# ── rate limiting ────────────────────────────────────────────────────────────

def test_requesting_codes_is_throttled(client, db, sent):
    make_user()
    last = None
    for _ in range(auth.RecoveryThrottle.MAX_PER_WINDOW + 2):
        last = client.post("/api/auth/request-code", json={"email": "t@example.com"})
    assert last.status_code == 429


def test_guessing_codes_spends_the_login_budget(client, db, sent):
    """Guessing a code must not be a cheaper path than guessing a password."""
    make_user()
    client.post("/api/auth/request-code", json={"email": "t@example.com"})

    for _ in range(auth.Throttle.MAX_FAILS):
        client.post("/api/auth/verify-code",
                    json={"email": "t@example.com", "code": "000000"})

    r = client.post("/api/auth/verify-code",
                    json={"email": "t@example.com", "code": code_from(sent)})
    assert r.status_code == 429


def test_the_code_is_not_written_to_the_log(client, db, sent, caplog):
    import logging
    make_user()
    with caplog.at_level(logging.DEBUG):
        client.post("/api/auth/request-code", json={"email": "t@example.com"})
    assert code_from(sent) not in caplog.text
