"""Proving a phone number, and refusing to text one that has not been proved.

WHY THIS EXISTS
---------------
`users.phone` has been collected since sign-up and nothing has ever checked it.
It is a string somebody typed. That was harmless while it was only a profile
field; it stops being harmless the moment anything is DELIVERED to it, because
a mistyped digit at registration means the sign-in code goes to a stranger who
can then use it.

So `phone_verified` is the prerequisite for SMS, not a nicety, and most of this
file is about the refusals rather than the happy path.

Registered in tests/conftest.py's _SECURITY_SUITES -- it asserts refusals, and
under the session-wide require_user override they would pass without reaching
the guard.
"""

import pytest
from fastapi.testclient import TestClient

from api import auth, sms, verification
from api.main import app
from db import connection
from db import users as repo

PASSWORD = "Correct-Horse-99-Battery"


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "phone.db")
    for name in ("throttle", "signup_throttle", "recovery_throttle",
                 "username_throttle", "verify_throttle"):
        monkeypatch.setattr(auth, name, type(getattr(auth, name))())
    monkeypatch.setattr(auth, "_INSECURE", True)
    return tmp_path


@pytest.fixture
def texted(monkeypatch):
    """Every message the app tried to text, as (number, code)."""
    out = []
    monkeypatch.setattr(sms, "configured", lambda: True)
    monkeypatch.setattr(sms, "send_code",
                        lambda to, code, purpose="": out.append((to, code)) or True)
    return out


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        yield c


def sign_in(client, username="trader"):
    repo.create_user(username, auth.hash_password(PASSWORD),
                     email=f"{username}@example.com", email_verified=True,
                     country="91")
    r = client.post("/api/auth/login",
                    json={"username": username, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return repo.get_user(username)


# ── normalisation: four spellings of one number ──────────────────────────────

def test_indian_numbers_normalise_to_one_form():
    """+91 98765 43210, 09876543210 and 9876543210 are ONE number.

    A uniqueness check that cannot see that is not a uniqueness check, and a
    duplicate-detection that misses it lets two accounts both claim a number.
    """
    forms = ["+91 98765 43210", "09876543210", "9876543210", "00919876543210",
             "+91-98765-43210"]
    assert {sms.normalise(f, "91") for f in forms} == {"+919876543210"}


def test_nonsense_is_refused_rather_than_guessed():
    """A number this cannot confidently normalise must be rejected.

    Guessing would mean texting somebody else.
    """
    for junk in ("12345", "abc", "", "+", "0", "++919876543210"):
        assert sms.normalise(junk, "91") == ""


def test_a_local_number_without_a_country_code_is_refused():
    assert sms.normalise("9876543210", "") == ""


def test_a_number_is_redacted_in_logs():
    assert sms.redact("+919876543210") == "***10"
    assert "9876543" not in sms.redact("+919876543210")


# ── the transport is dormant until configured ────────────────────────────────

def test_sms_is_dormant_without_a_provider(monkeypatch):
    for var in (sms.PROVIDER_ENV, sms.TWILIO_SID_ENV, sms.TWILIO_TOKEN_ENV,
                sms.TWILIO_FROM_ENV, sms.MSG91_KEY_ENV):
        monkeypatch.delenv(var, raising=False)
    assert sms.configured() is False
    assert sms.send_code("+919876543210", "123456") is False
    assert "dormant" in sms.describe()


def test_a_half_configured_provider_is_still_dormant(monkeypatch):
    """Credentials that are present but incomplete must not read as ready."""
    monkeypatch.setenv(sms.PROVIDER_ENV, "twilio")
    monkeypatch.setenv(sms.TWILIO_SID_ENV, "AC123")
    monkeypatch.delenv(sms.TWILIO_TOKEN_ENV, raising=False)
    monkeypatch.delenv(sms.TWILIO_FROM_ENV, raising=False)
    assert sms.configured() is False
    assert "incomplete" in sms.describe()


# ── the routes ───────────────────────────────────────────────────────────────

def test_both_routes_refuse_an_anonymous_caller(client, db):
    """401, and NOT 422.

    A 422 would mean the body was validated before the guard ran, which tells
    an anonymous caller the endpoint exists and what it expects.
    """
    assert client.post("/api/auth/phone", json={}).status_code == 401
    assert client.post("/api/auth/phone/confirm", json={}).status_code == 401


def test_a_number_is_stored_unverified_and_then_proved(client, db, texted):
    user = sign_in(client)

    r = client.post("/api/auth/phone", json={"phone": "09876543210"})
    assert r.status_code == 200
    assert texted and texted[0][0] == "+919876543210"

    mid = repo.get_user_by_id(user.id)
    assert mid.phone == "+919876543210"
    assert mid.phone_verified is False        # stored, not yet proved

    code = texted[0][1]
    r = client.post("/api/auth/phone/confirm", json={"code": code})
    assert r.status_code == 200
    assert r.json()["phone_verified"] is True
    assert repo.get_user_by_id(user.id).phone_verified is True


def test_the_full_number_never_leaves_the_server(client, db, texted):
    sign_in(client)
    client.post("/api/auth/phone", json={"phone": "09876543210"})
    body = client.post("/api/auth/phone/confirm", json={"code": texted[0][1]}).json()
    assert body["phone"] == "***10"
    assert "9876543" not in str(body)


def test_a_wrong_code_does_not_prove_the_number(client, db, texted):
    user = sign_in(client)
    client.post("/api/auth/phone", json={"phone": "09876543210"})

    r = client.post("/api/auth/phone/confirm", json={"code": "000000"})

    assert r.status_code == 401
    assert repo.get_user_by_id(user.id).phone_verified is False


def test_the_code_dies_after_five_wrong_guesses(client, db, texted):
    sign_in(client)
    client.post("/api/auth/phone", json={"phone": "09876543210"})
    real = texted[0][1]
    wrong = "000000" if real != "000000" else "111111"

    for _ in range(verification.LOGIN_CODE_MAX_ATTEMPTS):
        client.post("/api/auth/phone/confirm", json={"code": wrong})

    assert client.post("/api/auth/phone/confirm",
                       json={"code": real}).status_code == 401


def test_changing_the_number_clears_the_proof(client, db, texted):
    """Verification belongs to a NUMBER, not to an account."""
    user = sign_in(client)
    client.post("/api/auth/phone", json={"phone": "09876543210"})
    client.post("/api/auth/phone/confirm", json={"code": texted[0][1]})
    assert repo.get_user_by_id(user.id).phone_verified is True

    auth.verify_throttle.__init__()
    client.post("/api/auth/phone", json={"phone": "09999988888"})

    assert repo.get_user_by_id(user.id).phone_verified is False


def test_a_number_proved_by_someone_else_cannot_be_claimed(client, db, texted):
    other = sign_in(client, "other")
    client.post("/api/auth/phone", json={"phone": "09876543210"})
    client.post("/api/auth/phone/confirm", json={"code": texted[0][1]})
    assert repo.get_user_by_id(other.id).phone_verified is True
    client.post("/api/auth/logout")

    auth.verify_throttle.__init__()
    sign_in(client, "thief")
    r = client.post("/api/auth/phone", json={"phone": "09876543210"})

    assert r.status_code == 409


def test_an_unproved_duplicate_is_allowed(client, db, texted):
    """Two people can TYPE the same number; at most one can prove it.

    Blocking on an unverified duplicate would let anyone reserve a number they
    do not hold, simply by typing it first.
    """
    sign_in(client, "first")
    client.post("/api/auth/phone", json={"phone": "09876543210"})
    client.post("/api/auth/logout")

    auth.verify_throttle.__init__()
    sign_in(client, "second")
    r = client.post("/api/auth/phone", json={"phone": "09876543210"})

    assert r.status_code == 200


def test_nothing_is_saved_when_sms_is_dormant(client, db, monkeypatch):
    """An honest 503 beats a stored number that can never be proved."""
    monkeypatch.setattr(sms, "configured", lambda: False)
    user = sign_in(client)

    r = client.post("/api/auth/phone", json={"phone": "09876543210"})

    assert r.status_code == 503
    assert repo.get_user_by_id(user.id).phone == ""


def test_an_unusable_number_is_refused_before_anything_is_stored(client, db, texted):
    user = sign_in(client)

    r = client.post("/api/auth/phone", json={"phone": "not a number"})

    assert r.status_code == 400
    assert repo.get_user_by_id(user.id).phone == ""
    assert texted == []


def test_requesting_codes_is_throttled(client, db, texted):
    sign_in(client)
    last = None
    for _ in range(auth.RecoveryThrottle.MAX_PER_WINDOW + 2):
        last = client.post("/api/auth/phone", json={"phone": "09876543210"})
    assert last.status_code == 429


def test_a_phone_code_does_not_destroy_a_sign_in_code(client, db, texted):
    """Separate purposes, so one flow cannot cancel the other mid-way."""
    user = sign_in(client)
    login_code = verification.new_login_code(user.id)
    client.post("/api/auth/phone", json={"phone": "09876543210"})

    assert repo.take_login_code(user.id, login_code,
                                verification.LOGIN_CODE_MAX_ATTEMPTS) is True
