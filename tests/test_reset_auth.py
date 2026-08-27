"""Password reset: the only way back into a self-registered account.

Until registration opened, a forgotten password was an administrator's problem
-- two people existed and manage_users.py fixed it. Now anyone can sign up, so
anyone can lock themselves out, and there is nobody who knows who they are.

WHAT THIS SUITE IS MOSTLY ABOUT
------------------------------
Not that reset works. That a reset endpoint is a gift to an attacker unless
three things hold:

  * it never reveals whether an address has an account, in the body, the
    status, or the time taken
  * a token cannot be reused, guessed, or borrowed from another purpose
  * completing one destroys every session the account had -- people reset
    precisely because they think somebody else is signed in

Named to end in _auth so conftest.py's _SECURITY_SUITES exemption applies:
without it these run with require_user overridden and the session assertions
would pass without reaching the guard.
"""

import re


import pytest
from fastapi.testclient import TestClient

from api import auth, verification
from api.main import app
from db import connection
from db import users as repo


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "reset.db")
    monkeypatch.setattr(auth, "throttle", auth.Throttle())
    monkeypatch.setattr(auth, "signup_throttle", auth.SignupThrottle())
    monkeypatch.setattr(auth, "_INSECURE", True)
    return tmp_path


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sent(monkeypatch):
    """Capture reset emails instead of sending them.

    Patched at send_reset, the same named-seam convention the Schwab tests use
    -- the network is not what is under test here, and mail is dormant in CI
    anyway, so without this every one of these tests would pass vacuously.
    """
    out = []

    def fake(user_id, email, username):
        token = verification.new_reset_token(user_id)
        out.append({"user_id": user_id, "email": email,
                    "username": username, "token": token})
        return True

    monkeypatch.setattr(verification, "send_reset", fake)
    return out


@pytest.fixture
def user(db):
    uid = repo.create_user("trader", auth.hash_password("Correct-Horse-99"),
                           full_name="A Trader", email="t@example.com")
    return repo.get_user_by_id(uid)


def forgot(client, email):
    return client.post("/api/auth/forgot-password", json={"email": email})


# ── it must not say who has an account ───────────────────────────────────────


def test_a_known_and_an_unknown_address_answer_identically(client, db, user, sent):
    a = forgot(client, "t@example.com")
    b = forgot(client, "nobody-at-all@example.com")

    assert a.status_code == b.status_code == 200
    assert a.json() == b.json(), "the response distinguishes a real address"


def test_a_disabled_account_answers_the_same_way(client, db, user, sent):
    repo.set_active("trader", False)
    a = forgot(client, "t@example.com")
    b = forgot(client, "nobody-at-all@example.com")
    assert a.json() == b.json()
    assert sent == [], "a disabled account was sent a reset link"


def test_the_reply_never_echoes_the_address(client, db, user, sent):
    """Echoing it back is the other way this leaks -- into logs and referrers."""
    r = forgot(client, "t@example.com")
    assert "t@example.com" not in r.text


def test_the_send_is_queued_rather_than_awaited(client, db, user, sent,
                                                monkeypatch):
    """A hit must not answer more slowly than a miss.

    This is the leak that survives an identical response body. In production a
    hit makes an HTTPS call to Resend taking a few hundred milliseconds and a
    miss makes none, so an endpoint that sends INLINE answers measurably slower
    for an address that exists -- and anyone with a stopwatch can enumerate
    accounts regardless of what the body says. Handing the send to a
    BackgroundTask is what removes the difference.

    ASSERTED STRUCTURALLY, AND HERE IS WHY
    --------------------------------------
    The obvious test is a slow stub and a stopwatch. It cannot work: Starlette's
    TestClient runs background tasks as part of the same ASGI call, before
    client.post() returns, so a queued send blocks the test client exactly as an
    inline one does. That test was written first, failed against correct code,
    and would have been "fixed" by loosening the bound until it could never fail
    at all. So this asserts the mechanism instead -- the send must be handed to
    add_task, not called during the handler.
    """
    from starlette.background import BackgroundTasks

    queued = []
    real_add = BackgroundTasks.add_task

    def spy_add(self, func, *a, **kw):
        queued.append((func, a))
        return real_add(self, func, *a, **kw)

    monkeypatch.setattr(BackgroundTasks, "add_task", spy_add)

    forgot(client, "t@example.com")

    assert queued, "nothing was queued -- the send runs inline and leaks timing"
    # The `sent` fixture has already replaced send_reset, so the queued callable
    # is that stub rather than the real function. What matters is that it was
    # handed to add_task and that it did run -- which together mean the handler
    # returned without waiting for it.
    assert len(sent) == 1, "the queued task never sent anything"
    assert queued[0][1][:1] == (user.id,), f"queued the wrong call: {queued}"


def test_a_miss_queues_nothing(client, db, sent, monkeypatch):
    """The other half: an unknown address must not queue a send either.

    Not a timing property -- a correctness one. Queueing a send for an address
    with no account would mean mail going somewhere nobody asked for it.
    """
    from starlette.background import BackgroundTasks

    queued = []
    real_add = BackgroundTasks.add_task
    monkeypatch.setattr(BackgroundTasks, "add_task",
                        lambda self, f, *a, **k: (queued.append(f),
                                                  real_add(self, f, *a, **k))[1])

    forgot(client, "nobody-at-all@example.com")
    assert sent == []
    assert queued == []


def test_the_email_is_still_actually_sent(client, db, user, sent):
    """Backgrounding it must not turn into dropping it.

    TestClient runs background tasks on exit, so this asserts the task really
    ran rather than being queued and forgotten.
    """
    forgot(client, "t@example.com")
    assert len(sent) == 1, "the reset email was never sent"


# ── the token ────────────────────────────────────────────────────────────────


def test_a_reset_link_actually_works(client, db, user, sent):
    forgot(client, "t@example.com")
    assert len(sent) == 1

    r = client.post("/api/auth/reset-password",
                    json={"token": sent[0]["token"], "password": "Brand-New-Pass-42"})
    assert r.status_code == 200, r.text
    assert repo.get_user("trader") is not None
    assert auth.verify_password(repo.get_user("trader").password_hash,
                                "Brand-New-Pass-42")


def test_the_old_password_stops_working(client, db, user, sent):
    forgot(client, "t@example.com")
    client.post("/api/auth/reset-password",
                json={"token": sent[0]["token"], "password": "Brand-New-Pass-42"})
    assert not auth.verify_password(repo.get_user("trader").password_hash,
                                    "Correct-Horse-99")


def test_a_token_cannot_be_used_twice(client, db, user, sent):
    forgot(client, "t@example.com")
    token = sent[0]["token"]

    first = client.post("/api/auth/reset-password",
                        json={"token": token, "password": "Brand-New-Pass-42"})
    assert first.status_code == 200

    second = client.post("/api/auth/reset-password",
                         json={"token": token, "password": "Another-Pass-9876"})
    assert second.status_code == 400
    assert not auth.verify_password(repo.get_user("trader").password_hash,
                                    "Another-Pass-9876"), "the second reset took effect"


def test_an_expired_token_is_refused(client, db, user, sent, monkeypatch):
    from datetime import timedelta
    monkeypatch.setattr(verification, "RESET_TTL", timedelta(seconds=-1))
    forgot(client, "t@example.com")

    r = client.post("/api/auth/reset-password",
                    json={"token": sent[0]["token"], "password": "Brand-New-Pass-42"})
    assert r.status_code == 400
    assert auth.verify_password(repo.get_user("trader").password_hash,
                                "Correct-Horse-99"), "an expired link changed the password"


def test_a_forged_token_is_refused(client, db, user, sent):
    for guess in ("", "x", "a" * 43, "not-a-token", sent and "0" * 64 or "0" * 64):
        r = client.post("/api/auth/reset-password",
                        json={"token": guess or "x", "password": "Brand-New-Pass-42"})
        assert r.status_code in (400, 422), guess
    assert auth.verify_password(repo.get_user("trader").password_hash,
                                "Correct-Horse-99")


def test_the_token_is_stored_hashed(client, db, user, sent):
    """A leaked database must not hand over working reset links."""
    forgot(client, "t@example.com")
    conn = connection.connect()
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM email_tokens")]
    finally:
        conn.close()
    assert rows
    assert sent[0]["token"] not in str(rows), "the raw token was stored"


def test_a_verification_token_cannot_be_spent_as_a_reset(client, db, user):
    """Otherwise 'confirm your address' becomes 'let someone set a password'."""
    raw = verification.new_token(user.id)
    r = client.post("/api/auth/reset-password",
                    json={"token": raw, "password": "Brand-New-Pass-42"})
    assert r.status_code == 400
    assert auth.verify_password(repo.get_user("trader").password_hash,
                                "Correct-Horse-99")


def test_a_reset_token_cannot_be_spent_as_a_verification(client, db, user, sent):
    forgot(client, "t@example.com")
    r = client.get("/api/auth/verify-email",
                   params={"token": sent[0]["token"]}, follow_redirects=False)
    assert "reason=verify_failed" in r.headers["location"]
    assert repo.get_user("trader").email_verified is False


def test_asking_again_invalidates_the_first_link(client, db, user, sent):
    """A link forwarded to the wrong place must stop working once replaced."""
    forgot(client, "t@example.com")
    auth.signup_throttle.__init__()
    forgot(client, "t@example.com")
    assert len(sent) == 2

    stale = client.post("/api/auth/reset-password",
                        json={"token": sent[0]["token"], "password": "Brand-New-Pass-42"})
    assert stale.status_code == 400
    fresh = client.post("/api/auth/reset-password",
                        json={"token": sent[1]["token"], "password": "Brand-New-Pass-42"})
    assert fresh.status_code == 200


def test_a_verification_email_does_not_cancel_a_pending_reset(client, db, user, sent):
    """The whole reason email_tokens has a `purpose` column.

    Issuing a token clears the user's earlier ones. Unscoped, sending a
    verification would silently destroy a reset requested a minute earlier, and
    the link already in their inbox would fail for no visible reason.
    """
    forgot(client, "t@example.com")
    verification.new_token(user.id)          # a verification, afterwards

    r = client.post("/api/auth/reset-password",
                    json={"token": sent[0]["token"], "password": "Brand-New-Pass-42"})
    assert r.status_code == 200, "a verification email killed a pending reset"


# ── sessions ─────────────────────────────────────────────────────────────────


def test_resetting_revokes_every_existing_session(client, db, user, sent):
    """The point of the whole flow.

    People reset because they believe someone else has their password. If that
    person stays signed in, the reset changed nothing for them.
    """
    intruder = TestClient(app)
    with intruder:
        assert intruder.post("/api/auth/login", json={
            "username": "trader", "password": "Correct-Horse-99"}).status_code == 200
        assert intruder.get("/api/auth/me").status_code == 200

        forgot(client, "t@example.com")
        client.post("/api/auth/reset-password",
                    json={"token": sent[0]["token"], "password": "Brand-New-Pass-42"})

        assert intruder.get("/api/auth/me").status_code == 401, \
            "a session survived the password reset"


def test_the_person_resetting_ends_up_signed_in(client, db, user, sent):
    forgot(client, "t@example.com")
    client.post("/api/auth/reset-password",
                json={"token": sent[0]["token"], "password": "Brand-New-Pass-42"})
    assert client.get("/api/auth/me").json()["username"] == "trader"


# ── weak passwords ───────────────────────────────────────────────────────────


def test_reset_enforces_the_same_password_rules(client, db, user, sent):
    forgot(client, "t@example.com")
    r = client.post("/api/auth/reset-password",
                    json={"token": sent[0]["token"], "password": "short"})
    assert r.status_code == 400
    assert auth.verify_password(repo.get_user("trader").password_hash,
                                "Correct-Horse-99")


def test_a_rejected_password_does_not_burn_the_token(client, db, user, sent):
    """A typo must not cost the person their only way back in."""
    forgot(client, "t@example.com")
    client.post("/api/auth/reset-password",
                json={"token": sent[0]["token"], "password": "short"})
    good = client.post("/api/auth/reset-password",
                       json={"token": sent[0]["token"], "password": "Brand-New-Pass-42"})
    assert good.status_code == 200, "a weak-password attempt consumed the token"


# ── OAuth-only accounts ──────────────────────────────────────────────────────


def test_an_oauth_account_with_a_verified_address_may_reset(client, db, sent):
    """Google proved the address, so a password is a genuine lifeline."""
    uid = repo.create_oauth_user("googler", full_name="G", email="g@example.com",
                                 email_verified=True)
    forgot(client, "g@example.com")
    assert len(sent) == 1, "a verified OAuth account was refused a reset"

    r = client.post("/api/auth/reset-password",
                    json={"token": sent[0]["token"], "password": "Brand-New-Pass-42"})
    assert r.status_code == 200
    assert repo.get_user_by_id(uid).has_password is True


def test_an_oauth_account_with_an_unverified_address_may_not(client, db, sent):
    """The X case, and the reason this rule exists.

    An X sign-up types its own address and nobody checks it. Sending a reset
    there hands a NEW way into the account to whoever holds an unverified
    inbox, while the X link keeps working for the original person.
    """
    repo.create_oauth_user("xperson", full_name="X", email="x@example.com",
                           email_verified=False)
    forgot(client, "x@example.com")
    assert sent == [], "a reset was sent to an unverified address"


def test_that_refusal_is_indistinguishable_from_every_other_outcome(client, db, sent):
    """Otherwise the refusal itself reveals that the account is OAuth-only."""
    repo.create_oauth_user("xperson", full_name="X", email="x@example.com",
                           email_verified=False)
    refused = forgot(client, "x@example.com")
    missing = forgot(client, "nobody-at-all@example.com")
    assert refused.status_code == missing.status_code
    assert refused.json() == missing.json()


def test_a_password_account_is_marked_as_having_one(client, db, user):
    assert repo.get_user("trader").has_password is True


def test_an_oauth_account_is_marked_as_not_having_one(client, db):
    repo.create_oauth_user("googler", email="g@example.com", email_verified=True)
    assert repo.get_user("googler").has_password is False


# ── rate limiting ────────────────────────────────────────────────────────────


def test_forgot_password_is_rate_limited(client, db, user, sent):
    """It sends mail on demand to an address the caller picks.

    Unmetered, that is how a sending domain ends up blacklisted -- and how one
    address gets buried in reset emails by someone who simply dislikes them.
    """
    codes = [forgot(client, "t@example.com").status_code for _ in range(8)]
    assert 429 in codes, f"a reset flood was never throttled: {codes}"


def test_guessing_reset_tokens_is_throttled(client, db, user):
    codes = []
    for i in range(10):
        codes.append(client.post("/api/auth/reset-password", json={
            "token": f"guess-{i}" + "x" * 30, "password": "Brand-New-Pass-42"}).status_code)
    assert 429 in codes, f"token guessing was never throttled: {codes}"


# ── the link on the page ─────────────────────────────────────────────────────


def test_the_forgot_link_is_not_dead(db):
    """It pointed at href="#" -- a control that looks like it works."""
    from pathlib import Path
    page = (Path(__file__).resolve().parents[1] / "web" / "public"
            / "autotrader_signin.html")
    if not page.is_file():
        pytest.skip("the sign-in page is not in this checkout")
    html = page.read_text(encoding="utf-8")
    m = re.search(r'<a href="([^"]*)"[^>]*>Forgot password\?</a>', html)
    assert m, "the Forgot password link is gone"
    assert m.group(1) != "#", "the link is still dead"
    assert "forgot" in m.group(1)


# ── forgot username ──────────────────────────────────────────────────────────
#
# Sign-in is by USERNAME, so forgetting it locks a person out exactly as
# completely as forgetting the password -- and reset does not rescue them,
# because it asks for the address and never says what the username is.


@pytest.fixture
def sent_names(monkeypatch):
    out = []
    monkeypatch.setattr(verification, "send_username",
                        lambda email, username: (out.append((email, username)), True)[1])
    return out


def forgot_user(client, email):
    return client.post("/api/auth/forgot-username", json={"email": email})


def test_a_username_reminder_is_sent(client, db, user, sent_names):
    r = forgot_user(client, "t@example.com")
    assert r.status_code == 200
    assert sent_names == [("t@example.com", "trader")]


def test_it_does_not_reveal_whether_the_address_exists(client, db, user, sent_names):
    """Same rule as /forgot-password -- otherwise this is a membership oracle."""
    a = forgot_user(client, "t@example.com")
    b = forgot_user(client, "nobody-at-all@example.com")
    assert a.status_code == b.status_code == 200
    assert a.json() == b.json()


def test_the_reply_never_contains_the_username(client, db, user, sent_names):
    """It goes to the INBOX, not to whoever asked.

    Returning it in the response would hand any caller the username for any
    address they can guess -- which is most of what an attacker needs before
    they start on the password.
    """
    r = forgot_user(client, "t@example.com")
    assert "trader" not in r.text


def test_a_disabled_account_gets_nothing(client, db, user, sent_names):
    repo.set_active("trader", False)
    forgot_user(client, "t@example.com")
    assert sent_names == []


def test_the_send_is_queued_not_awaited(client, db, user, sent_names, monkeypatch):
    """Same timing rule as /forgot-password."""
    from starlette.background import BackgroundTasks

    queued = []
    real = BackgroundTasks.add_task
    monkeypatch.setattr(BackgroundTasks, "add_task",
                        lambda self, f, *a, **k: (queued.append(f), real(self, f, *a, **k))[1])
    forgot_user(client, "t@example.com")
    assert queued, "sent inline -- a hit is distinguishable from a miss by timing"


def test_a_username_miss_queues_nothing(client, db, sent_names, monkeypatch):
    from starlette.background import BackgroundTasks

    queued = []
    real = BackgroundTasks.add_task
    monkeypatch.setattr(BackgroundTasks, "add_task",
                        lambda self, f, *a, **k: (queued.append(f), real(self, f, *a, **k))[1])
    forgot_user(client, "nobody-at-all@example.com")
    assert queued == [] and sent_names == []


def test_it_is_rate_limited(client, db, user, sent_names):
    codes = [forgot_user(client, "t@example.com").status_code for _ in range(8)]
    assert 429 in codes, f"never throttled: {codes}"


def test_the_reminder_carries_no_token(client, db, user, monkeypatch):
    """A username is not a credential, so nothing spendable may travel with it.

    Bundling a reset token into a username reminder would mean every such email
    was also a password-changing link -- a far larger thing to leave in an inbox.
    """
    import inspect
    src = inspect.getsource(verification.send_username)
    # Assert on what it CALLS, not on the word "token" -- the docstring says
    # "No token and no link", so a naive text search matches its own promise.
    for minted in ("new_reset_token", "new_email_token", "new_verification_token"):
        assert minted not in src, f"send_username mints {minted}"

    # And nothing spendable reaches the message body.
    captured = {}
    monkeypatch.setattr(verification.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no network")))
    monkeypatch.setenv(verification.API_KEY_ENV, "re_test")
    monkeypatch.setenv(verification.FROM_ENV, "x@example.com")
    monkeypatch.setenv(verification.BASE_URL_ENV, "https://example.com")

    real_req = verification.urllib.request.Request

    def spy(url, data=None, headers=None):
        captured["body"] = (data or b"").decode()
        return real_req(url, data=data, headers=headers or {})

    monkeypatch.setattr(verification.urllib.request, "Request", spy)
    verification.send_username("t@example.com", "trader")

    body = captured.get("body", "")
    assert "trader" in body, "the username should be in the message"
    assert "verify-email" not in body and "?reset=" not in body,         "a spendable link reached a username reminder"
