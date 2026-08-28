"""The three OAuth routes: which providers work, start, and come back.

These are public by necessity -- somebody signing in has no session yet, and
the provider redirects the browser back here with no cookie of ours attached.
They are listed in tests/test_auth.py's PUBLIC set for that reason, and the
route-guard sweep would fail if they were not.

What keeps them safe instead of a session:

  * `state` is a 32-byte value we minted, stored server-side, and destroyed on
    first use. A callback we did not start, or one replayed a second time,
    finds nothing and is refused.
  * PKCE ties the code to the verifier that never left this process.
  * An account IS created when the identity is new -- registration is open --
    but only ever a fresh one. An existing account is matched on the provider's
    permanent subject, or on an address the provider positively says it
    verified, and on nothing else. An unverified address is a claim by whoever
    is signing in; honouring it would hand them the account that owns it.
"""

import logging
import sqlite3

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from api import auth, oauth
from db import users as repo

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/oauth", tags=["auth"])


class ProviderInfo(BaseModel):
    key: str
    label: str
    configured: bool


class ProvidersResponse(BaseModel):
    providers: list[ProviderInfo]


@router.get("/providers", response_model=ProvidersResponse)
def providers():
    """Which buttons can actually do something.

    The sign-in page asks this on load so an unconfigured provider explains
    itself in place instead of bouncing the person through a redirect that was
    never going to work.
    """
    return ProvidersResponse(providers=[
        ProviderInfo(key=p.key, label=p.label, configured=oauth.is_configured(p.key))
        for p in oauth.PROVIDERS.values()
    ])


def _provider_or_404(name: str) -> oauth.Provider:
    provider = oauth.PROVIDERS.get(name.lower())
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Unknown sign-in provider.")
    return provider


@router.get("/{name}/start")
def start(name: str, request: Request, next: str = "/"):
    """Begin a sign-in: record the state, then hand the browser to the provider."""
    provider = _provider_or_404(name)
    destination = oauth.safe_next(next)

    if not oauth.is_configured(provider.key):
        # A missing credential is a deployment fact, not a user error, and the
        # person can still sign in with a password -- so this returns them to
        # the form with an explanation rather than raising.
        log.warning("oauth start refused: %s is not configured", provider.key)
        return RedirectResponse(
            oauth.sign_in_redirect("oauth_unconfigured", provider=provider.key,
                                   next_path=destination),
            status_code=status.HTTP_303_SEE_OTHER)

    verifier = oauth.new_verifier()
    state = repo.new_oauth_state(provider.key, verifier, destination)
    log.info("oauth start: %s from %s", provider.key, auth.client_ip(request))
    return RedirectResponse(oauth.authorization_url(provider, state, verifier),
                            status_code=status.HTTP_303_SEE_OTHER)


def _refuse(reason: str, provider_key: str, next_path: str = "/") -> RedirectResponse:
    """Back to the sign-in page. Never a 500, never a stack trace, never a hint
    about which account does or does not exist."""
    return RedirectResponse(
        oauth.sign_in_redirect(reason, provider=provider_key, next_path=next_path),
        status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{name}/callback")
def callback(name: str, request: Request, response: Response,
             code: str = "", state: str = "", error: str = ""):
    """The provider sends the browser back here. Everything is verified again."""
    provider = _provider_or_404(name)
    ip = auth.client_ip(request)

    # The state is consumed FIRST and unconditionally, before anything else is
    # looked at, so an error callback cannot leave a usable row behind.
    pending = repo.take_oauth_state(state)

    if error:
        # The person pressed Cancel, or the provider refused. Not our failure.
        log.info("oauth %s returned error=%r", provider.key, error[:80])
        return _refuse("oauth_cancelled", provider.key,
                       pending.next_path if pending else "/")

    if pending is None or pending.provider != provider.key:
        # Unknown, expired, replayed, or aimed at a different provider.
        log.warning("oauth callback with an unusable state for %s from %s",
                    provider.key, ip)
        return _refuse("oauth_expired", provider.key)

    if not code:
        return _refuse("oauth_failed", provider.key, pending.next_path)

    if auth.throttle.retry_after(ip, f"oauth:{provider.key}"):
        return _refuse("oauth_throttled", provider.key, pending.next_path)

    try:
        token = oauth._post_token(provider, code, pending.code_verifier)
        access = str(token.get("access_token") or "")
        if not access:
            raise oauth.OAuthError("no access token")
        info = oauth._fetch_userinfo(provider, access)
    except oauth.OAuthError as exc:
        log.warning("oauth %s exchange failed: %s", provider.key, exc)
        return _refuse("oauth_failed", provider.key, pending.next_path)
    except Exception:
        # A provider being unreachable is not a defect in this app; it must not
        # surface as a 500 to somebody who was only trying to log in.
        log.exception("oauth %s: unexpected failure", provider.key)
        return _refuse("oauth_failed", provider.key, pending.next_path)

    who = oauth.normalise(provider, info)
    if not who.subject:
        return _refuse("oauth_failed", provider.key, pending.next_path)

    # Every provider lands in the same place now, signed in. X used to be sent
    # to a form for a username and an address instead; see _resolve_account for
    # why that step was removed rather than polished.
    user = _resolve_account(provider, who, ip)

    if user is None:
        return _refuse("oauth_no_account", provider.key, pending.next_path)

    auth.throttle.record_success(ip, f"oauth:{provider.key}")
    repo.touch_identity(provider.key, who.subject)
    token_raw = repo.new_session(user.id, ip=ip,
                                 user_agent=request.headers.get("user-agent", ""))
    repo.touch_login(user.id)
    log.info("oauth login: %s via %s from %s", user.username, provider.key, ip)

    redirect = RedirectResponse(pending.next_path, status_code=status.HTTP_303_SEE_OTHER)
    auth.set_session_cookie(redirect, token_raw)
    return redirect


def _resolve_account(provider: oauth.Provider, who: oauth.ProviderUser,
                     ip: str):
    """Find, or create, the local account this provider identity signs in as.

    Registration is open, so OAuth creates accounts too -- but only on an
    address the provider positively states it has VERIFIED. That distinction is
    the whole security of this function: an unverified address is a claim by
    whoever is signing in, and honouring it would let someone assert another
    person's email and be handed a new account carrying it -- or, worse, be
    matched onto the existing account that already owns it.

    Order matters and is not negotiable:
      1. an existing LINK, matched on the provider's permanent subject
      2. an existing ACCOUNT, matched on a verified address
      3. a NEW account
    Subject beats email because an address can be released and re-issued by a
    mail provider; a subject cannot. Checking email first would hand a recycled
    address the account of whoever held it before.

    Every refusal is logged: a stream of them is what a takeover attempt looks
    like from here.
    """
    # 1. Already linked. Matched on the provider's permanent subject, so this
    #    keeps working after the person changes their email there.
    user = repo.identity_user(provider.key, who.subject)
    if user is not None:
        if not user.is_active:
            log.warning("oauth: %s is disabled, refused via %s",
                        user.username, provider.key)
            return None
        return user

    # 2. First time on a provider that cannot tell us an address.
    #
    # X returns no email at any scope. That used to send the person to a form
    # asking for a username and an address -- and it was the wrong call. The
    # rule that matters is "never MATCH an existing account on an address the
    # provider did not verify", and creating a brand new account with NO
    # address does not touch it: there is nothing to match, nothing to collide
    # with, and the identity is the pinned X subject either way.
    #
    # So the form was not buying security. It was buying a recovery address,
    # and charging a whole extra step for it -- to someone who had already
    # proved they control the account they are signing in with, and who signs
    # in by pressing that button rather than by typing a username.
    #
    # An empty email is a first-class state here, not a workaround: the column
    # is NOT NULL DEFAULT '' and the unique index is PARTIAL, `WHERE email !=
    # ''`. The schema was already built to allow exactly this.
    #
    # What is genuinely given up: this account cannot be recovered by email.
    # It does not need to be -- it has no password to reset, and its recovery
    # is X itself. If the person wants an address on file they can add one.
    if not provider.provides_email:
        candidate = _create_from(provider, who, ip, email="", verified=False)
        if candidate is None:
            return None
        # Falls THROUGH to link_identity below. Returning here would leave the
        # new account with no identity attached, so the next sign-in would find
        # no link and build another one, for ever.
        return _link(provider, who, candidate, email="")

    if not who.email or not who.email_verified:
        log.warning("oauth: %s gave an %s email; refused", provider.key,
                    "unverified" if who.email else "absent")
        auth.throttle.record_failure(ip, f"oauth:{provider.key}")
        return None

    candidate = _user_by_email(who.email)

    if candidate is not None and not candidate.is_active:
        # A DISABLED account is a refusal, never a reason to create a second
        # one. Auto-provisioning past it would hand back exactly the access
        # that was deliberately withdrawn -- with a fresh username and none of
        # the old account's data, so it would not even look like a bypass.
        log.warning("oauth: %s is disabled, refused via %s",
                    candidate.username, provider.key)
        auth.throttle.record_failure(ip, f"oauth:{provider.key}")
        return None

    if candidate is None:
        # 3. Nobody has this address. Make an account for them.
        candidate = _create_from(provider, who, ip, email=who.email,
                                 verified=True)
        if candidate is None:
            return None

    return _link(provider, who, candidate, email=who.email)


def _link(provider: oauth.Provider, who: oauth.ProviderUser, candidate,
          *, email: str):
    """Pin this provider's permanent subject to the account, once."""
    if not repo.link_identity(candidate.id, provider.key, who.subject,
                              email=email):
        # Lost a race, or that subject is already bound elsewhere. Never
        # re-point an existing link.
        log.warning("oauth: could not link %s to %s", provider.key, candidate.username)
        return None

    log.info("oauth: linked %s to %s's account on first sign-in",
             provider.key, candidate.username)
    return candidate


def _create_from(provider: oauth.Provider, who: oauth.ProviderUser, ip: str,
                 *, email: str, verified: bool):
    """Make a new account for a provider identity nobody here holds yet.

    Rate-limited on the SIGNUP budget rather than the login throttle: this is a
    registration path, and it is the one that does not pass through
    /api/auth/register or its CAPTCHA. Leaving it unmetered would make OAuth
    the cheap way to mass-create accounts.

    `verified` is the provider's word, not ours, and it is only ever True when
    the provider positively said so over our own server-to-server exchange.
    """
    if wait := auth.signup_throttle.retry_after(ip):
        log.warning("oauth: signup throttled for %ss from %s", wait, ip)
        return None
    auth.signup_throttle.record(ip)

    # For X there is no address, so the display name is the only seed. It is a
    # suggestion either way -- username_from appends a number until it is free.
    username = repo.username_from(email or who.full_name or provider.key)
    try:
        user_id = repo.create_oauth_user(
            username, full_name=who.full_name or "", email=email,
            email_verified=verified,
        )
    except sqlite3.IntegrityError:
        # Lost a race with a concurrent sign-in for the same address.
        log.warning("oauth: collision creating an account for a %s identity",
                    provider.key)
        return _user_by_email(email) if email else None

    log.info("oauth: created %s from a %s identity (email: %s)", username,
             provider.key, "verified" if verified else "none")
    return repo.get_user_by_id(user_id)


def _user_by_email(email: str):
    """The single active account with this address, or None.

    Deliberately refuses when more than one account shares an address: with two
    matches there is no way to tell which person is signing in, and picking
    either would be a guess about who someone is.
    """
    wanted = email.strip().lower()
    if not wanted:
        return None
    matches = [u for u in repo.list_users()
               if str(u.get("email") or "").strip().lower() == wanted]
    if len(matches) != 1:
        if len(matches) > 1:
            log.error("oauth: %d accounts share one email address; refusing to "
                      "guess between them", len(matches))
        return None
    return repo.get_user_by_id(int(matches[0]["id"]))
