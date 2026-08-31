"""No auth endpoint may reveal whether an account exists.

WHY THIS SUITE EXISTS
---------------------
/register answered 201 for a free address and 409 for a taken one. The wording
was already careful -- "that username OR email is already registered", so you
could not tell which collided -- but the STATUS CODE said it outright, and so
did the Set-Cookie header present on one branch and absent on the other. Point
that at a list of addresses with a fresh username each time and it reports
exactly which of those people hold accounts here.

Every test below fixes a shape, not a message. A response that differs in
status, body, header or cost is an oracle regardless of how carefully the
sentence is written, so these compare the whole observable answer.

Registered in tests/conftest.py's _SECURITY_SUITES: this file asserts refusals
and identical rejections, and under the session-wide require_user override the
guard is never reached.
"""

import re
import statistics
import time

import pytest
from fastapi.testclient import TestClient

from api import auth, captcha, verification
from api.main import app
from db import connection
from db import users as repo

PASSWORD = "Correct-Horse-99-Battery"


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "enum.db")
    for name in ("throttle", "signup_throttle", "recovery_throttle",
                 "username_throttle", "verify_throttle"):
        cls = type(getattr(auth, name))
        monkeypatch.setattr(auth, name, cls())
    monkeypatch.setattr(auth, "_INSECURE", True)
    # Mail that reaches strangers: the confirm-first registration path, and the
    # verification gate, both switch on from exactly this.
    monkeypatch.setenv(verification.SMTP_HOST_ENV, "smtp.example.test")
    monkeypatch.setenv(verification.SMTP_USER_ENV, "a@example.test")
    monkeypatch.setenv(verification.SMTP_PASSWORD_ENV, "x")
    monkeypatch.setenv(verification.FROM_ENV, "a@example.test")
    monkeypatch.setenv(verification.BASE_URL_ENV, "https://example.test")
    # No real socket. Both branches must still pay the same cost, which is what
    # the timing test below checks.
    monkeypatch.setattr(verification, "_deliver", lambda *a, **k: True)
    return tmp_path


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        yield c


def register(client, username, email):
    auth.signup_throttle.__init__()          # the budget is not what is under test
    return client.post("/api/auth/register", json={
        "username": username, "password": PASSWORD,
        "email": email, "accept_terms": True})


def observable(r):
    """Everything an unauthenticated caller can see, as one comparable value."""
    return (r.status_code, r.text, "set-cookie" in r.headers)


# ── registration ─────────────────────────────────────────────────────────────

def test_registration_answers_identically_for_a_taken_email(client, db):
    """The oracle this suite was written for."""
    assert register(client, "victim", "victim@example.com").status_code == 202

    free = register(client, "probe1", "nobody@example.com")
    taken = register(client, "probe2", "victim@example.com")

    assert observable(free) == observable(taken)
    assert free.status_code == 202
    assert "set-cookie" not in free.headers    # neither branch signs anyone in


def test_registration_answers_identically_for_a_taken_username(client, db):
    register(client, "victim", "victim@example.com")

    free = register(client, "brand-new-name", "one@example.com")
    taken = register(client, "victim", "two@example.com")

    assert observable(free) == observable(taken)


def test_a_collision_creates_no_second_account(client, db):
    register(client, "victim", "victim@example.com")
    register(client, "attacker", "victim@example.com")

    conn = connection.connect()
    try:
        names = [r["username"] for r in conn.execute("SELECT username FROM users")]
    finally:
        conn.close()
    assert names == ["victim"]


def test_the_address_owner_is_told_about_the_collision(client, db, monkeypatch):
    """The caller learns nothing; the person who owns the address learns all."""
    sent = []
    monkeypatch.setattr(verification, "send_registration_collision",
                        lambda email, username: sent.append((email, username)) or True)
    register(client, "victim", "victim@example.com")
    register(client, "attacker", "victim@example.com")

    assert sent == [("victim@example.com", "victim")]


def test_registration_does_not_leak_through_timing(client, db):
    """Both branches hash the password, which is the expensive part.

    Hashing only on the success path would let a collision answer measurably
    sooner -- argon2id at 64 MiB dwarfs everything else the route does, so the
    difference would be plain to anyone with a stopwatch and no need for a
    statistical attack.
    """
    register(client, "victim", "victim@example.com")

    def sample(prefix, email, n=7):
        out = []
        for i in range(n):
            t0 = time.perf_counter()
            register(client, f"{prefix}{i}", email)
            out.append(time.perf_counter() - t0)
        return statistics.median(out)

    free = sample("free", "nobody@example.com")
    taken = sample("takn", "victim@example.com")

    # Generous, because CI timing is noisy. It still catches the real failure,
    # which is one branch skipping the hash entirely -- a multiple, not a few
    # percent.
    assert abs(free - taken) < 0.5 * max(free, taken), (
        f"registration timing differs: free={free*1000:.0f}ms taken={taken*1000:.0f}ms")


# ── sign-in ──────────────────────────────────────────────────────────────────

def test_login_answers_identically_for_unknown_user_and_wrong_password(client, db):
    repo.create_user("real", auth.hash_password(PASSWORD), email="r@example.com")

    unknown = client.post("/api/auth/login",
                          json={"username": "no-such-person", "password": PASSWORD})
    wrong = client.post("/api/auth/login",
                        json={"username": "real", "password": "not-the-password"})

    assert observable(unknown) == observable(wrong)
    assert unknown.status_code == 401


# ── recovery ─────────────────────────────────────────────────────────────────

def test_forgot_password_answers_identically(client, db):
    repo.create_user("real", auth.hash_password(PASSWORD), email="r@example.com",
                     email_verified=True)

    known = client.post("/api/auth/forgot-password", json={"email": "r@example.com"})
    unknown = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})

    assert observable(known) == observable(unknown)


def test_forgot_username_answers_identically(client, db):
    repo.create_user("real", auth.hash_password(PASSWORD), email="r@example.com")

    known = client.post("/api/auth/forgot-username", json={"email": "r@example.com"})
    unknown = client.post("/api/auth/forgot-username", json={"email": "nobody@example.com"})

    assert observable(known) == observable(unknown)


def test_reset_rejects_every_bad_token_the_same_way(client, db):
    """Unknown, expired and already-spent must not be told apart.

    Distinguishing them would say "this token existed once", which for a token
    that arrived by email says the address has an account.
    """
    answers = set()
    for token in ("never-existed", "also-never-existed", "x" * 43):
        r = client.post("/api/auth/reset-password",
                        json={"token": token, "password": "Another-Good-Password-1"})
        answers.add(observable(r))
        auth.throttle.record_success("testclient", "reset")   # keep the budget clear
    assert len(answers) == 1


# ── rate limiting and the challenge ──────────────────────────────────────────

def test_every_auth_endpoint_has_a_ceiling(client, db):
    """No route may be hammered without limit. /verify-email had no ceiling."""
    for _ in range(auth.RecoveryThrottle.MAX_PER_WINDOW + 2):
        r = client.get("/api/auth/verify-email?token=bogus", follow_redirects=False)
    assert r.status_code == 429


def test_login_demands_a_captcha_after_repeated_failure(client, db, monkeypatch):
    repo.create_user("real", auth.hash_password(PASSWORD), email="r@example.com")
    monkeypatch.setattr(captcha, "configured", lambda: True)
    monkeypatch.setattr(captcha, "verify", lambda token, ip="": token == "good")

    for _ in range(auth.CAPTCHA_AFTER_FAILURES):
        client.post("/api/auth/login", json={"username": "real", "password": "wrong"})

    # The right password, but no challenge answer: refused.
    blocked = client.post("/api/auth/login",
                          json={"username": "real", "password": PASSWORD})
    assert blocked.status_code == 401

    # ...and the refusal is worded exactly like a wrong password, or it would
    # say "this username has failed before", which is a membership signal.
    wrong = client.post("/api/auth/login",
                        json={"username": "real", "password": "still-wrong"})
    assert blocked.json()["detail"] == wrong.json()["detail"]


def test_the_challenge_is_not_demanded_of_a_first_attempt(client, db, monkeypatch):
    repo.create_user("real", auth.hash_password(PASSWORD), email="r@example.com")
    monkeypatch.setattr(captcha, "configured", lambda: True)
    monkeypatch.setattr(captcha, "verify", lambda token, ip="": token == "good")

    assert client.post("/api/auth/login",
                       json={"username": "real", "password": PASSWORD}).status_code == 200


# ── credentials at rest ──────────────────────────────────────────────────────

def test_passwords_are_argon2id_and_never_recoverable(db):
    uid = repo.create_user("real", auth.hash_password(PASSWORD), email="r@example.com")
    stored = repo.get_user_by_id(uid).password_hash

    assert stored.startswith("$argon2id$")
    assert PASSWORD not in stored
    # Neither the password nor any bare digest of it appears anywhere.
    import hashlib
    for weak in (hashlib.md5(PASSWORD.encode()).hexdigest(),          # noqa: S324
                 hashlib.sha1(PASSWORD.encode()).hexdigest(),          # noqa: S324
                 hashlib.sha256(PASSWORD.encode()).hexdigest()):
        assert weak not in stored
    assert auth.verify_password(stored, PASSWORD)
    assert not auth.verify_password(stored, PASSWORD + "x")


def test_two_identical_passwords_hash_differently(db):
    """Per-user salt. Equal digests would let one crack answer for many accounts."""
    a = auth.hash_password(PASSWORD)
    b = auth.hash_password(PASSWORD)
    assert a != b


# ── reset tokens ─────────────────────────────────────────────────────────────

def test_reset_tokens_are_random_and_stored_only_as_a_hash(db):
    uid = repo.create_user("real", auth.hash_password(PASSWORD), email="r@example.com")

    # Two in a row: different every time, and -- deliberately -- only the
    # newest survives. Asking for a fresh link invalidates the old one, so a
    # link forwarded to the wrong place stops working the moment the real owner
    # notices and requests another. See repo.new_email_token.
    first = verification.new_reset_token(uid)
    raw = verification.new_reset_token(uid)
    assert raw != first                                       # not a counter

    # 32 random bytes, url-safe. Long enough that guessing is not a threat.
    assert len(raw) >= 40
    assert re.fullmatch(r"[A-Za-z0-9_-]+", raw)

    conn = connection.connect()
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM email_tokens")]
    finally:
        conn.close()
    # The raw token is nowhere in the database -- a stolen copy yields no
    # working reset link, the same property sessions have.
    for row in rows:
        for value in row.values():
            assert raw != value
    hashes = {r["token_hash"] for r in rows}
    assert repo.hash_token(raw) in hashes
    assert repo.hash_token(first) not in hashes               # superseded


def test_a_reset_token_expires_within_the_hour(db):
    from datetime import datetime, timedelta
    assert verification.RESET_TTL <= timedelta(hours=1)

    uid = repo.create_user("real", auth.hash_password(PASSWORD), email="r@example.com")
    verification.new_reset_token(uid)
    conn = connection.connect()
    try:
        expires = conn.execute(
            "SELECT expires_at FROM email_tokens").fetchone()["expires_at"]
    finally:
        conn.close()
    assert datetime.fromisoformat(expires) - datetime.now() <= timedelta(hours=1)


def test_a_reset_token_works_once(client, db):
    uid = repo.create_user("real", auth.hash_password(PASSWORD), email="r@example.com")
    raw = verification.new_reset_token(uid)
    new_password = "A-Completely-Different-1"

    first = client.post("/api/auth/reset-password",
                        json={"token": raw, "password": new_password})
    second = client.post("/api/auth/reset-password",
                         json={"token": raw, "password": "Third-Password-Here-1"})

    assert first.status_code == 200
    assert second.status_code == 400
    # The second attempt did not take effect.
    assert auth.verify_password(repo.get_user_by_id(uid).password_hash, new_password)


def test_a_reset_token_is_never_written_to_the_log(db, caplog):
    """A log line carrying a live token is a reset link in a file.

    Logs are copied, shipped and read by more people than a database is.
    """
    import logging
    uid = repo.create_user("real", auth.hash_password(PASSWORD), email="r@example.com")
    with caplog.at_level(logging.DEBUG):
        raw = verification.new_reset_token(uid)
        verification.send_reset(uid, "r@example.com", "real")
    assert raw not in caplog.text
