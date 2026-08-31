"""An unproved email address blocks the application -- but only when it can be proved.

WHY THIS SUITE EXISTS
---------------------
`users.email_verified` was written, stored, and read by nothing. Registration
set it, the confirmation link cleared it, and no route ever consulted it, so
anyone could register with an address they did not control and use the product
in full. The column described a property the system did not enforce.

Enforcing it is easy to get dangerously wrong, and most of this file is about
the wrong ways rather than the right one. A gate keyed on "is verification
implemented" locks out every deployment where mail is not configured -- a
laptop, this test run. A gate keyed on "is mail configured" locks out this
product's own live host, which HAS a Resend key but sends from the shared
sandbox domain that delivers only to the account owner: every user would be
told to open a link that was never going to arrive, with no way back. Both are
outages, not security.

So the rule is: the gate turns itself on only when a confirmation email can
actually reach a stranger. The tests below pin every branch of that.

Registered in tests/conftest.py's _SECURITY_SUITES -- this suite exists to
watch require_user REFUSE, and the session-wide override would hide that.
"""

import pytest
from fastapi.testclient import TestClient

from api import auth, verification
from api.main import app
from db import connection
from db import users as repo

PASSWORD = "Correct-Horse-99-Battery"


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "verify.db")
    monkeypatch.setattr(auth, "throttle", auth.Throttle())
    monkeypatch.setattr(auth, "signup_throttle", auth.SignupThrottle())
    monkeypatch.setattr(auth, "verify_throttle", auth.RecoveryThrottle())
    monkeypatch.setattr(auth, "_INSECURE", True)
    return tmp_path


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        yield c


def mail(monkeypatch, *, key="re_test", sender="no-reply@autotrader.example",
         base="https://autotrader.example"):
    """Point the mail settings wherever a test needs them."""
    for name, value in ((verification.API_KEY_ENV, key),
                        (verification.FROM_ENV, sender),
                        (verification.BASE_URL_ENV, base)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


def make_user(username="trader", email="t@example.com", verified=False,
              **kw) -> int:
    return repo.create_user(username, auth.hash_password(PASSWORD),
                            email=email, email_verified=verified, **kw)


def sign_in(client, username="trader"):
    r = client.post("/api/auth/login",
                    json={"username": username, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r


# ── when the gate is OFF, and why ────────────────────────────────────────────

def test_unconfigured_mail_does_not_enforce(client, db, monkeypatch):
    """No key, no sender: nobody can verify, so nobody may be blocked."""
    mail(monkeypatch, key=None, sender=None, base=None)
    make_user(verified=False)
    sign_in(client)

    assert auth.verification_enforced() is False
    assert client.get("/api/strategies").status_code == 200


def test_a_sandbox_sender_does_not_enforce(client, db, monkeypatch):
    """The live-site case. Configured, but undeliverable to anyone else.

    This is the assertion that stands between the gate and an outage on the
    deployed host. Remove it and the next person to "tidy up" the condition
    into `verification.configured()` locks every user out silently.
    """
    mail(monkeypatch, sender="onboarding@resend.dev")
    make_user(verified=False)
    sign_in(client)

    assert verification.configured() is True
    assert verification.sandboxed() is True
    assert auth.verification_enforced() is False
    assert client.get("/api/strategies").status_code == 200


def test_the_operator_can_switch_it_off(client, db, monkeypatch):
    mail(monkeypatch)
    monkeypatch.setenv(auth.REQUIRE_VERIFIED_ENV, "0")
    make_user(verified=False)
    sign_in(client)

    assert auth.verification_enforced() is False
    assert client.get("/api/strategies").status_code == 200


# ── when the gate is ON ──────────────────────────────────────────────────────

def test_an_unverified_account_is_refused(client, db, monkeypatch):
    mail(monkeypatch)
    make_user(verified=False)
    sign_in(client)

    r = client.get("/api/strategies")

    assert r.status_code == 403
    # 403, never 401: the client bounces a 401 to the sign-in page, which this
    # person would pass, landing them straight back here.
    assert r.headers.get(auth.UNVERIFIED_HEADER) == auth.UNVERIFIED_REASON
    assert "confirm" in r.json()["detail"].lower()


def test_a_verified_account_is_let_through(client, db, monkeypatch):
    mail(monkeypatch)
    make_user(verified=True)
    sign_in(client)

    assert client.get("/api/strategies").status_code == 200


def test_confirming_the_address_opens_the_door(client, db, monkeypatch):
    """The whole journey: blocked, verify, allowed -- on one session."""
    mail(monkeypatch)
    uid = make_user(verified=False)
    sign_in(client)
    assert client.get("/api/strategies").status_code == 403

    repo.set_email_verified(uid, True)

    assert client.get("/api/strategies").status_code == 200


def test_signing_in_again_still_works_while_unverified(client, db, monkeypatch):
    """The front door is not the gate. Login must still succeed.

    Refusing the login itself would leave someone unable to reach the resend
    button, which lives behind a session.
    """
    mail(monkeypatch)
    make_user(verified=False)

    r = client.post("/api/auth/login",
                    json={"username": "trader", "password": PASSWORD})

    assert r.status_code == 200
    assert r.json()["verification_required"] is True
    assert r.json()["email_verified"] is False


def test_me_still_answers_so_the_page_can_explain_itself(client, db, monkeypatch):
    mail(monkeypatch)
    make_user(verified=False)
    sign_in(client)

    r = client.get("/api/auth/me")

    assert r.status_code == 200
    assert r.json()["verification_required"] is True


def test_resend_is_reachable_while_blocked(client, db, monkeypatch):
    """The way forward must not be behind the gate it exists to open."""
    mail(monkeypatch)
    make_user(verified=False)
    sign_in(client)

    assert client.post("/api/auth/resend-verification").status_code == 200


def test_closing_the_account_is_reachable_while_blocked(client, db, monkeypatch):
    """And so must the way out.

    Someone who registered with a typo'd address can never verify it. If the
    delete route sat behind the gate, that account could not be closed by the
    only person entitled to close it.
    """
    mail(monkeypatch)
    make_user(verified=False)
    sign_in(client)

    r = client.request("DELETE", "/api/auth/me",
                       json={"confirm": "trader", "password": PASSWORD})

    assert r.status_code == 200, r.text
    assert repo.get_user("trader") is None


# ── who is deliberately NOT blocked ──────────────────────────────────────────

def test_an_account_with_no_address_is_not_blocked(client, db, monkeypatch):
    """X reports no email at any scope. There is nothing to send a link to."""
    mail(monkeypatch)
    make_user(username="xuser", email="", verified=False)
    sign_in(client, "xuser")

    assert client.get("/api/strategies").status_code == 200


def test_a_provider_verified_account_is_not_blocked(client, db, monkeypatch):
    """Google/LinkedIn/GitHub vouch for the address, and oauth.py only believes
    them when they positively say so. That is a stronger proof than our link."""
    mail(monkeypatch)
    make_user(username="googler", email="g@example.com", verified=True,
              has_password=False)
    token = repo.new_session(repo.get_user("googler").id)
    client.cookies.set(auth.COOKIE, token)

    assert client.get("/api/strategies").status_code == 200


# ── the socket, which does not run the dependency chain ──────────────────────

@pytest.mark.anyio
async def test_the_websocket_guard_applies_the_same_rule(db, monkeypatch):
    """A rule enforced only on the HTTP half is a rule with a way around it."""
    mail(monkeypatch)
    uid = make_user(verified=False)
    token = repo.new_session(uid)

    class FakeSocket:
        cookies = {auth.COOKIE: token}

    assert await auth.user_for_websocket(FakeSocket()) is None

    repo.set_email_verified(uid, True)
    assert await auth.user_for_websocket(FakeSocket()) is not None


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── the helper the gate is built on ──────────────────────────────────────────

def test_verification_blocks_matrix(db, monkeypatch):
    mail(monkeypatch)
    blocked = repo.get_user_by_id(make_user("a", "a@example.com", verified=False))
    proved = repo.get_user_by_id(make_user("b", "b@example.com", verified=True))
    address_less = repo.get_user_by_id(make_user("c", "", verified=False))

    assert auth.verification_blocks(blocked) is True
    assert auth.verification_blocks(proved) is False
    assert auth.verification_blocks(address_less) is False


def test_sandboxed_recognises_the_shared_domain(monkeypatch):
    mail(monkeypatch, sender="onboarding@resend.dev")
    assert verification.sandboxed() is True
    mail(monkeypatch, sender="hello@mail.autotrader.example")
    assert verification.sandboxed() is False
