"""OAuth sign-in: it must let the right person in and nobody else.

The dangerous failure for a "sign in with Google" button is not that it breaks
-- that is obvious the moment you press it. It is that it lets in someone it
should not, quietly, while looking like it works. So most of what is below is
about refusal: replayed state, forged state, an unverified email, an email
belonging to nobody, a disabled account, a provider identity already spoken for.

The network is never touched. `_post_token` and `_fetch_userinfo` are the two
seams in api/oauth.py, monkeypatched here exactly as
tests/test_schwab_redirect_parsing.py stubs the Schwab exchange -- what is under
test is the decision logic, not requests.

This module is named so that conftest.py's _SECURITY_SUITES includes it. Without
that, `require_user` is overridden for the whole session and the refusal
assertions would pass without the guard ever running.
"""

import pytest
from fastapi.testclient import TestClient

from api import auth, oauth
from api.main import app
from db import connection
from db import users as repo

GOOGLE_SUB = "108120915361234567890"
TWITTER_SUB = "1465235834"


# ── fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture
def db(tmp_path, monkeypatch):
    """A scratch database, a fresh throttle, and cookies that work over http."""
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "oauth.db")
    monkeypatch.setattr(auth, "throttle", auth.Throttle())
    # Reset the signup budget too. It is module-level and counts
    # SUCCESSES, so without this an early test that registers
    # accounts spends the allowance and later tests collect 429
    # where they expected a validation error.
    monkeypatch.setattr(auth, "signup_throttle", auth.SignupThrottle())
    monkeypatch.setattr(auth, "_INSECURE", True)   # TestClient speaks http://
    return tmp_path


@pytest.fixture
def configured(monkeypatch):
    """Credentials for every provider. Fake values -- nothing here dials out."""
    monkeypatch.setenv("AUTOTRADER_PUBLIC_BASE_URL", "https://trade.example.com")
    # Every provider in the registry, so adding one does not silently leave it
    # unconfigured here and quietly skip whatever asserts against it.
    for key in oauth.PROVIDERS:
        monkeypatch.setenv(f"AUTOTRADER_{key.upper()}_CLIENT_ID", f"{key}-id")
        monkeypatch.setenv(f"AUTOTRADER_{key.upper()}_CLIENT_SECRET", f"{key}-secret")


@pytest.fixture
def user(db):
    repo.create_user("trader", auth.hash_password("Correct-Horse-99"),
                     full_name="A Trader", email="trader@example.com", country="IN")
    return repo.get_user("trader")


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        yield c


def stub(monkeypatch, info, *, token=None, on_token=None):
    """Answer as a provider would, without a network."""
    def fake_token(provider, code, verifier):
        if on_token:
            on_token(provider, code, verifier)
        return token if token is not None else {"access_token": "at-123"}

    def fake_userinfo(provider, access_token):
        return info

    monkeypatch.setattr(oauth, "_post_token", fake_token)
    monkeypatch.setattr(oauth, "_fetch_userinfo", fake_userinfo)


def google_info(sub=GOOGLE_SUB, email="trader@example.com", verified=True):
    return {"sub": sub, "email": email, "email_verified": verified, "name": "A Trader"}


def begin(client, provider="google", next_path="/"):
    """Run /start and return the state the server minted."""
    r = client.get(f"/api/auth/oauth/{provider}/start",
                   params={"next": next_path}, follow_redirects=False)
    assert r.status_code == 303, r.text
    location = r.headers["location"]
    assert "state=" in location, location
    return location.split("state=")[1].split("&")[0]


def finish(client, state, code="auth-code", provider="google"):
    return client.get(f"/api/auth/oauth/{provider}/callback",
                      params={"code": code, "state": state}, follow_redirects=False)


# ── configuration is reported honestly ───────────────────────────────────────
def test_providers_report_unconfigured_when_no_credentials(client, db, monkeypatch):
    """Derived from the registry, not a hand-written list.

    A literal set here means every provider added later fails this test for no
    reason except that it exists -- which trains whoever adds one to edit the
    assertion rather than read it.
    """
    for key in oauth.PROVIDERS:
        monkeypatch.delenv(f"AUTOTRADER_{key.upper()}_CLIENT_ID", raising=False)
        monkeypatch.delenv(f"AUTOTRADER_{key.upper()}_CLIENT_SECRET", raising=False)
    body = client.get("/api/auth/oauth/providers").json()
    assert {p["key"] for p in body["providers"]} == set(oauth.PROVIDERS)
    assert all(p["configured"] is False for p in body["providers"])


def test_providers_report_configured_once_credentials_exist(client, db, configured):
    body = client.get("/api/auth/oauth/providers").json()
    assert all(p["configured"] is True for p in body["providers"])


def test_start_without_credentials_explains_itself(client, db, monkeypatch):
    """Requirement: a missing credential must say so, not fail silently."""
    monkeypatch.delenv("AUTOTRADER_GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("AUTOTRADER_GOOGLE_CLIENT_SECRET", raising=False)
    r = client.get("/api/auth/oauth/google/start", follow_redirects=False)
    assert r.status_code == 303
    assert "reason=oauth_unconfigured" in r.headers["location"]
    assert "provider=google" in r.headers["location"]


def test_unconfigured_start_never_500s(client, db, monkeypatch):
    monkeypatch.delenv("AUTOTRADER_LINKEDIN_CLIENT_ID", raising=False)
    r = client.get("/api/auth/oauth/linkedin/start", follow_redirects=False)
    assert r.status_code < 500


def test_unknown_provider_is_404(client, db, configured):
    assert client.get("/api/auth/oauth/facebook/start",
                      follow_redirects=False).status_code == 404


# ── the authorization redirect ───────────────────────────────────────────────
def test_start_sends_the_browser_to_the_provider(client, db, configured):
    r = client.get("/api/auth/oauth/google/start", follow_redirects=False)
    loc = r.headers["location"]
    assert loc.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=google-id" in loc
    assert "response_type=code" in loc
    # The redirect_uri must be absolute and must match what was registered.
    assert ("redirect_uri=https%3A%2F%2Ftrade.example.com%2Fapi%2Fauth%2Foauth"
            "%2Fgoogle%2Fcallback") in loc


def test_pkce_challenge_is_sent_and_the_verifier_is_not(client, db, configured):
    loc = client.get("/api/auth/oauth/google/start",
                     follow_redirects=False).headers["location"]
    assert "code_challenge=" in loc
    assert "code_challenge_method=S256" in loc
    assert "code_verifier" not in loc, "the verifier must never leave the server"


def test_twitter_uses_pkce_and_linkedin_does_not(client, db, configured):
    tw = client.get("/api/auth/oauth/twitter/start",
                    follow_redirects=False).headers["location"]
    li = client.get("/api/auth/oauth/linkedin/start",
                    follow_redirects=False).headers["location"]
    assert "code_challenge=" in tw, "X requires PKCE"
    assert "code_challenge=" not in li, "LinkedIn's OIDC rejects the parameters"


def test_challenge_matches_the_verifier():
    v = oauth.new_verifier()
    assert 43 <= len(v) <= 128, "RFC 7636 length"
    assert oauth.challenge_for(v) == oauth.challenge_for(v)
    assert oauth.challenge_for(v) != oauth.challenge_for(oauth.new_verifier())
    assert "=" not in oauth.challenge_for(v), "must be unpadded base64url"


def test_start_records_exactly_one_state(client, db, configured):
    state = begin(client)
    pending = repo.take_oauth_state(state)
    assert pending is not None and pending.provider == "google"


# ── state: the thing that stops a forged callback ────────────────────────────
def test_a_replayed_callback_is_refused(client, db, configured, user, monkeypatch):
    stub(monkeypatch, google_info())
    state = begin(client)

    first = finish(client, state)
    assert first.status_code == 303 and first.headers["location"] == "/"

    client.cookies.clear()
    second = finish(client, state)            # same state, a second time
    assert "reason=oauth_expired" in second.headers["location"]
    assert auth.COOKIE not in second.headers.get("set-cookie", "")


def test_a_state_we_never_issued_is_refused(client, db, configured, user, monkeypatch):
    stub(monkeypatch, google_info())
    r = finish(client, "not-a-state-this-server-minted")
    assert "reason=oauth_expired" in r.headers["location"]
    assert auth.COOKIE not in r.headers.get("set-cookie", "")


def test_an_expired_state_is_refused(client, db, configured, user, monkeypatch):
    from datetime import timedelta
    monkeypatch.setattr(repo, "OAUTH_STATE_TTL", timedelta(seconds=-1))
    stub(monkeypatch, google_info())
    state = begin(client)
    r = finish(client, state)
    assert "reason=oauth_expired" in r.headers["location"]


def test_a_state_cannot_be_used_on_a_different_provider(client, db, configured,
                                                        user, monkeypatch):
    stub(monkeypatch, google_info())
    state = begin(client, "google")
    r = finish(client, state, provider="linkedin")
    assert "reason=oauth_expired" in r.headers["location"]


def test_a_cancelled_sign_in_returns_quietly(client, db, configured):
    state = begin(client)
    r = client.get("/api/auth/oauth/google/callback",
                   params={"error": "access_denied", "state": state},
                   follow_redirects=False)
    assert r.status_code == 303
    assert "reason=oauth_cancelled" in r.headers["location"]


def test_an_error_callback_still_burns_the_state(client, db, configured):
    state = begin(client)
    client.get("/api/auth/oauth/google/callback",
               params={"error": "access_denied", "state": state},
               follow_redirects=False)
    assert repo.take_oauth_state(state) is None, "an errored state must not survive"


# ── who gets in ──────────────────────────────────────────────────────────────
def test_a_verified_email_signs_the_matching_account_in(client, db, configured,
                                                        user, monkeypatch):
    stub(monkeypatch, google_info())
    r = finish(client, begin(client))
    assert r.status_code == 303
    raw = r.headers.get("set-cookie", "")
    assert auth.COOKIE in raw
    assert "HttpOnly" in raw, "an OAuth session must be as protected as a password one"
    assert "samesite=lax" in raw.lower()
    assert client.get("/api/auth/me").json()["username"] == "trader"


def test_first_sign_in_pins_the_subject(client, db, configured, user, monkeypatch):
    stub(monkeypatch, google_info())
    finish(client, begin(client))
    links = repo.list_identities(user.id)
    assert [(i.provider, i.subject) for i in links] == [("google", GOOGLE_SUB)]


def test_the_second_sign_in_matches_on_subject_not_email(client, db, configured,
                                                         user, monkeypatch):
    """The person changes their Google email. They must still get in."""
    stub(monkeypatch, google_info())
    finish(client, begin(client))
    client.cookies.clear()

    stub(monkeypatch, google_info(email="brand-new@elsewhere.com"))
    r = finish(client, begin(client))
    assert r.status_code == 303
    assert client.get("/api/auth/me").json()["username"] == "trader"
    assert len(repo.list_identities(user.id)) == 1, "no duplicate link"


def test_the_destination_survives_the_round_trip(client, db, configured,
                                                 user, monkeypatch):
    stub(monkeypatch, google_info())
    r = finish(client, begin(client, next_path="/replay?symbol=ES"))
    assert r.headers["location"] == "/replay?symbol=ES"


# ── who does not get in ──────────────────────────────────────────────────────
def test_an_unverified_email_is_refused(client, db, configured, user, monkeypatch):
    """The whole reason matching is on a VERIFIED address: anyone can type
    someone else's email at a provider that does not check it."""
    stub(monkeypatch, google_info(verified=False))
    r = finish(client, begin(client))
    assert "reason=oauth_no_account" in r.headers["location"]
    assert auth.COOKIE not in r.headers.get("set-cookie", "")
    assert repo.list_identities(user.id) == []


def test_an_unknown_verified_email_creates_an_account(client, db, configured,
                                                     monkeypatch):
    """Registration is open, so this now provisions instead of refusing.

    Inverted deliberately. It previously asserted OAuth must never create an
    account, which was right while accounts came from a CLI. What has NOT
    changed is the condition it rests on -- the address must be one the
    PROVIDER states it verified. The test below is the half that still refuses.
    """
    stub(monkeypatch, google_info(email="a-stranger@example.com"))
    r = finish(client, begin(client))

    assert r.status_code == 303
    assert "reason=" not in r.headers["location"]
    created = repo.get_user_by_email("a-stranger@example.com")
    assert created is not None
    assert client.get("/api/auth/me").json()["username"] == created.username


def test_an_auto_created_account_is_verified_but_not_an_owner(
        client, db, configured, monkeypatch):
    """Verified because Google said so. Never an owner, because nobody says so."""
    stub(monkeypatch, google_info(email="a-stranger@example.com"))
    finish(client, begin(client))

    created = repo.get_user_by_email("a-stranger@example.com")
    assert created.email_verified is True, "the provider verified this address"
    assert created.is_owner is False, "the broker is never granted by signing in"


def test_an_auto_created_account_has_no_usable_password(
        client, db, configured, monkeypatch):
    """password_hash is NOT NULL, so something is stored. Nothing may match it.

    A placeholder like an empty string would make every OAuth account reachable
    by anyone who guessed the placeholder, turning a passwordless account into
    a password account with a known password.
    """
    stub(monkeypatch, google_info(email="a-stranger@example.com"))
    finish(client, begin(client))
    created = repo.get_user_by_email("a-stranger@example.com")

    for guess in ("", "oauth", "password", "a-stranger@example.com",
                  created.username, "!", "x" * 32):
        assert not auth.verify_password(created.password_hash, guess), guess


def test_an_unverified_email_still_creates_nothing(client, db, configured,
                                                   monkeypatch):
    """The condition auto-provisioning rests on.

    An unverified address is a claim by whoever is signing in. Honouring it
    would let someone assert another person's address and be handed an account
    carrying it -- or be matched onto the account that already owns it.
    """
    stub(monkeypatch, google_info(email="a-stranger@example.com", verified=False))
    r = finish(client, begin(client))
    assert "reason=oauth_no_account" in r.headers["location"]
    assert repo.get_user_by_email("a-stranger@example.com") is None


def test_a_disabled_account_is_refused(client, db, configured, user, monkeypatch):
    repo.set_active("trader", False)
    stub(monkeypatch, google_info())
    r = finish(client, begin(client))
    assert "reason=oauth_no_account" in r.headers["location"]
    assert auth.COOKIE not in r.headers.get("set-cookie", "")


def test_disabling_an_account_locks_out_an_already_linked_identity(
        client, db, configured, user, monkeypatch):
    stub(monkeypatch, google_info())
    finish(client, begin(client))          # link it first
    client.cookies.clear()
    repo.set_active("trader", False)

    r = finish(client, begin(client))
    assert "reason=oauth_no_account" in r.headers["location"]
    assert auth.COOKIE not in r.headers.get("set-cookie", "")


def test_an_existing_link_wins_over_a_matching_email(client, db, configured,
                                                     user, monkeypatch):
    """That Google account is already somebody else's door.

    `trader` shares the email address, so the email path would have picked
    them -- but the subject is already bound to `rival`, and a link is never
    re-pointed. The person who controls that Google account gets `rival`, which
    is whose account it actually is, and never `trader`.
    """
    # From schema v5 the rival cannot share the address -- a non-empty email is
    # unique. The precedence being tested is unaffected: what matters is that a
    # subject already bound to `rival` wins over an email that matches
    # `trader`, and the provider still reports trader@example.com.
    rival_id = repo.create_user("rival", auth.hash_password("Correct-Horse-99"),
                                email="rival@example.com")
    repo.link_identity(rival_id, "google", GOOGLE_SUB, email="trader@example.com")

    stub(monkeypatch, google_info())
    r = finish(client, begin(client))

    assert r.status_code == 303
    assert client.get("/api/auth/me").json()["username"] == "rival"
    assert repo.identity_user("google", GOOGLE_SUB).username == "rival"
    assert repo.list_identities(user.id) == [], "trader must gain no link"


def test_two_accounts_cannot_share_an_email_at_all(db, user):
    """The ambiguity OAuth used to defend against is now unreachable.

    This was a test that two matching accounts made the email path refuse,
    because with two matches there is no way to know which person is signing
    in. From schema v5 a non-empty address is UNIQUE, so the ambiguous state
    cannot be created in the first place -- which is the stronger guarantee,
    and the one open signup needs: registration is what would otherwise let
    anyone manufacture that collision on purpose.

    The refusal in api/routers/oauth.py is kept as defence in depth; this
    asserts the condition it guards against can no longer arise.
    """
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_user("twin", auth.hash_password("Correct-Horse-99"),
                         email="trader@example.com")

    # And the original account is untouched by the attempt.
    assert repo.get_user("trader") is not None
    assert repo.get_user("twin") is None


def test_a_callback_with_no_code_is_refused(client, db, configured, user):
    state = begin(client)
    r = client.get("/api/auth/oauth/google/callback",
                   params={"state": state}, follow_redirects=False)
    assert "reason=oauth_failed" in r.headers["location"]


# ── Twitter/X cannot self-serve ──────────────────────────────────────────────
def twitter_info(sub=TWITTER_SUB):
    return {"data": {"id": sub, "name": "A Trader", "username": "atrader"}}


def test_twitter_reports_no_email(client, db, configured):
    who = oauth.normalise(oauth.PROVIDERS["twitter"], twitter_info())
    assert who.subject == TWITTER_SUB
    assert who.email == "" and who.email_verified is False


def _handle_from(response) -> str:
    """The pending handle the callback put in the redirect URL."""
    return response.headers["location"].split("complete=")[1].split("&")[0]


def test_twitter_without_a_prelink_asks_for_details(client, db, configured,
                                                    user, monkeypatch):
    """X has no address to offer, so it asks rather than refusing.

    This was a flat refusal while an administrator had to pre-link every
    identity. The person HAS proved they control that X account -- there is
    simply nothing to build an account from, so they are asked.
    """
    stub(monkeypatch, twitter_info())
    r = finish(client, begin(client, "twitter"), provider="twitter")

    loc = r.headers["location"]
    assert "autotrader_signup.html" in loc and "complete=" in loc
    assert "reason=" not in loc
    # Crucially: no account and no session yet.
    assert repo.list_identities(user.id) == []
    assert client.get("/api/auth/me").status_code == 401


def test_the_pending_handle_is_not_a_session(client, db, configured, user,
                                             monkeypatch):
    """Holding it proves an OAuth round-trip happened. It grants nothing."""
    stub(monkeypatch, twitter_info())
    handle = _handle_from(finish(client, begin(client, "twitter"),
                                 provider="twitter"))

    assert client.get("/api/auth/me").status_code == 401
    assert len(handle) >= 32, "must not be guessable"

    from db.connection import connect
    conn = connect()
    try:
        rows = [dict(x) for x in conn.execute("SELECT * FROM oauth_pending")]
    finally:
        conn.close()
    assert rows, "nothing was parked"
    assert handle not in str(rows), "the raw handle was stored, not its hash"


def test_completing_a_twitter_signup_creates_and_links(client, db, configured,
                                                       monkeypatch):
    stub(monkeypatch, twitter_info())
    handle = _handle_from(finish(client, begin(client, "twitter"),
                                 provider="twitter"))

    done = client.post("/api/auth/oauth/complete", json={
        "handle": handle, "username": "xperson",
        "email": "xperson@example.com", "accept_terms": True})
    assert done.status_code == 201, done.text

    assert repo.get_user("xperson") is not None
    assert repo.identity_user("twitter", TWITTER_SUB).username == "xperson"
    assert client.get("/api/auth/me").json()["username"] == "xperson"


def test_a_typed_address_is_never_marked_verified(client, db, configured,
                                                  monkeypatch):
    """X told us nothing about this address; the person typed it a moment ago.

    Marking it verified would let an X user claim someone else's Google
    identity later, because the email path trusts a verified address.
    """
    stub(monkeypatch, twitter_info())
    handle = _handle_from(finish(client, begin(client, "twitter"),
                                 provider="twitter"))
    client.post("/api/auth/oauth/complete", json={
        "handle": handle, "username": "xperson",
        "email": "xperson@example.com", "accept_terms": True})

    assert repo.get_user("xperson").email_verified is False


def test_a_pending_handle_is_single_use(client, db, configured, monkeypatch):
    stub(monkeypatch, twitter_info())
    handle = _handle_from(finish(client, begin(client, "twitter"),
                                 provider="twitter"))
    body = {"handle": handle, "username": "xperson",
            "email": "xperson@example.com", "accept_terms": True}

    assert client.post("/api/auth/oauth/complete", json=body).status_code == 201
    again = client.post("/api/auth/oauth/complete", json=dict(
        body, username="xperson2", email="xperson2@example.com"))
    assert again.status_code == 400
    assert repo.get_user("xperson2") is None


def test_completion_refuses_a_forged_handle(client, db, configured):
    r = client.post("/api/auth/oauth/complete", json={
        "handle": "not-a-real-handle-at-all-0123456789",
        "username": "intruder", "email": "intruder@example.com",
        "accept_terms": True})
    assert r.status_code == 400
    assert repo.get_user("intruder") is None, "an account was created from nothing"


def test_completion_requires_the_terms(client, db, configured, monkeypatch):
    stub(monkeypatch, twitter_info())
    handle = _handle_from(finish(client, begin(client, "twitter"),
                                 provider="twitter"))

    done = client.post("/api/auth/oauth/complete", json={
        "handle": handle, "username": "xperson",
        "email": "xperson@example.com", "accept_terms": False})
    assert done.status_code == 400
    assert repo.get_user("xperson") is None


def test_twitter_with_a_prelink_signs_in(client, db, configured, user, monkeypatch):
    assert repo.link_identity(user.id, "twitter", TWITTER_SUB) is True
    stub(monkeypatch, twitter_info())
    r = finish(client, begin(client, "twitter"), provider="twitter")
    assert r.status_code == 303
    assert client.get("/api/auth/me").json()["username"] == "trader"


def test_a_provider_account_links_to_exactly_one_user(db, user):
    other = repo.create_user("second", auth.hash_password("Correct-Horse-99"))
    assert repo.link_identity(user.id, "twitter", TWITTER_SUB) is True
    assert repo.link_identity(other, "twitter", TWITTER_SUB) is False


# ── a broken provider is not a broken app ────────────────────────────────────
def test_a_provider_failure_does_not_500(client, db, configured, user, monkeypatch):
    def boom(provider, code, verifier):
        raise oauth.OAuthError("Google rejected the sign-in.")
    monkeypatch.setattr(oauth, "_post_token", boom)

    r = finish(client, begin(client))
    assert r.status_code == 303, "a provider outage must not become a 500"
    assert "reason=oauth_failed" in r.headers["location"]


def test_an_unexpected_exception_does_not_leak(client, db, configured,
                                               user, monkeypatch):
    def boom(provider, code, verifier):
        raise ConnectionError("dns is down; /etc/secret/path in the message")
    monkeypatch.setattr(oauth, "_post_token", boom)

    r = finish(client, begin(client))
    assert r.status_code == 303
    assert "/etc/secret/path" not in r.headers["location"]


def test_a_token_response_with_no_access_token_is_refused(client, db, configured,
                                                          user, monkeypatch):
    stub(monkeypatch, google_info(), token={"error": "invalid_grant"})
    r = finish(client, begin(client))
    assert "reason=oauth_failed" in r.headers["location"]


def test_a_profile_with_no_subject_is_refused(client, db, configured,
                                              user, monkeypatch):
    stub(monkeypatch, {"email": "trader@example.com", "email_verified": True})
    r = finish(client, begin(client))
    assert "reason=oauth_failed" in r.headers["location"]


def test_the_code_and_verifier_reach_the_exchange(client, db, configured,
                                                  user, monkeypatch):
    seen = {}
    stub(monkeypatch, google_info(),
         on_token=lambda p, c, v: seen.update(code=c, verifier=v, provider=p.key))
    finish(client, begin(client), code="the-real-code")
    assert seen["code"] == "the-real-code"
    assert seen["provider"] == "google"
    assert len(seen["verifier"]) >= 43, "the stored PKCE verifier must be replayed"


# ── the destination cannot be turned into an open redirect ───────────────────
@pytest.mark.parametrize("hostile", [
    "https://evil.example/steal",     # absolute
    "//evil.example/steal",           # protocol-relative
    "/autotrader_signin.html",        # a loop back to the form
])
def test_a_hostile_next_is_ignored(client, db, configured, user, monkeypatch, hostile):
    stub(monkeypatch, google_info())
    r = finish(client, begin(client, next_path=hostile))
    assert r.headers["location"] == "/", f"{hostile!r} must not survive"


def test_safe_next_accepts_ordinary_paths():
    assert oauth.safe_next("/replay") == "/replay"
    assert oauth.safe_next("/a?b=c&d=e") == "/a?b=c&d=e"
    assert oauth.safe_next(None) == "/"
    assert oauth.safe_next("") == "/"
    assert oauth.safe_next("relative") == "/"


# ── GitHub ───────────────────────────────────────────────────────────────────
GITHUB_SUB = "58231907"


def github_info(sub=GITHUB_SUB, emails=None):
    """GitHub's shape: /user has no address, /user/emails carries it."""
    return {"id": int(sub), "login": "atrader", "name": "A Trader",
            "emails": emails if emails is not None else
            [{"email": "trader@example.com", "primary": True, "verified": True}]}


def test_github_reads_the_address_from_the_emails_endpoint(db):
    """/user omits `email` unless it is public, which for most people it is not.

    Without the second call GitHub behaves exactly like X -- an identity with
    no address, refused on every first sign-in -- and nothing says why.
    """
    who = oauth.normalise(oauth.PROVIDERS["github"], github_info())
    assert who.subject == GITHUB_SUB
    assert who.email == "trader@example.com"
    assert who.email_verified is True
    assert who.full_name == "A Trader"


def test_github_ignores_an_unverified_address(db):
    """GitHub lets an address be ADDED before it is confirmed.

    Honouring an unverified entry would let someone attach another person's
    email to their own GitHub account and be handed the local account that
    owns it -- the exact takeover the verified rule exists to stop.
    """
    who = oauth.normalise(oauth.PROVIDERS["github"], github_info(
        emails=[{"email": "victim@example.com", "primary": True, "verified": False}]))
    assert who.email == ""
    assert who.email_verified is False


def test_github_prefers_the_primary_verified_address(db):
    who = oauth.normalise(oauth.PROVIDERS["github"], github_info(emails=[
        {"email": "old@example.com", "primary": False, "verified": True},
        {"email": "main@example.com", "primary": True, "verified": True},
    ]))
    assert who.email == "main@example.com"


def test_github_falls_back_to_a_verified_non_primary(db):
    """Better than refusing: a verified address is a verified address."""
    who = oauth.normalise(oauth.PROVIDERS["github"], github_info(emails=[
        {"email": "unverified@example.com", "primary": True, "verified": False},
        {"email": "works@example.com", "primary": False, "verified": True},
    ]))
    assert who.email == "works@example.com"


def test_github_with_no_addresses_at_all_is_empty(db):
    who = oauth.normalise(oauth.PROVIDERS["github"], github_info(emails=[]))
    assert who.email == "" and who.email_verified is False


def test_github_asks_for_the_scope_that_makes_emails_readable(db):
    """user:email is what makes /user/emails return anything.

    Drop it and the call 403s, the address is empty, and GitHub silently
    degrades into a provider that can never sign anyone in.
    """
    assert "user:email" in oauth.PROVIDERS["github"].scope


def test_github_is_offered_and_can_self_serve(db):
    p = oauth.PROVIDERS["github"]
    assert p.provides_email is True, "GitHub can find an account by itself"
    assert p.emails_url, "the second call is what makes that true"
