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
  * The account must already exist. The callback can attach a session to an
    existing user; it has no code path that creates one.
"""

import logging
import secrets
import sqlite3
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from api import auth, verification, oauth
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


#: Returned by _resolve_account when the identity is genuine but there is not
#: enough information to make an account. Deliberately a unique object rather
#: than None or False: those already mean "refused", and conflating "we will
#: not let you in" with "we need one more thing from you" is how a working
#: sign-up becomes an unexplained rejection.
NEEDS_DETAILS = object()

#: Short. This is an unauthenticated handle sitting in a URL; it needs to
#: outlive filling in a two-field form and nothing more.
PENDING_TTL = timedelta(minutes=20)


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

    user = _resolve_account(provider, who, ip)

    if user is NEEDS_DETAILS:
        # Park the identity and send them to finish signing up. The handle
        # below is NOT a session and grants nothing -- it only proves this
        # browser just completed an OAuth round-trip for that subject.
        if wait := auth.signup_throttle.retry_after(ip):
            log.warning("oauth: signup throttled for %ss from %s", wait, ip)
            return _refuse("oauth_no_account", provider.key, pending.next_path)

        handle = secrets.token_urlsafe(32)
        repo.new_pending_oauth(
            repo.hash_token(handle), provider.key, who.subject,
            suggested=(who.full_name or ""), next_path=pending.next_path,
            expires_at=(datetime.now() + PENDING_TTL).isoformat(timespec="seconds"),
        )
        return RedirectResponse(
            f"/autotrader_signup.html?complete={handle}&provider={provider.key}",
            status_code=status.HTTP_303_SEE_OTHER)

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
    # X returns no email at any scope, so there is nothing to match an account
    # by and nothing to create one from. It is not a refusal though -- the
    # person has proved they control that X account. They are asked for a
    # username and an address, and NEEDS_DETAILS says so.
    if not provider.provides_email:
        log.info("oauth: %s identity %s has no address; asking for details",
                 provider.key, who.subject[:12])
        return NEEDS_DETAILS

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
        #
        # Rate-limited on the SIGNUP budget, not the login throttle: this is a
        # registration path, and it is the one that does not pass through
        # /api/auth/register or its CAPTCHA. Leaving it unmetered would make
        # OAuth the cheap way to mass-create accounts.
        if wait := auth.signup_throttle.retry_after(ip):
            log.warning("oauth: signup throttled for %ss from %s", wait, ip)
            return None
        auth.signup_throttle.record(ip)

        username = repo.username_from(who.email or who.full_name)
        try:
            user_id = repo.create_oauth_user(
                username, full_name=who.full_name or "", email=who.email,
                # The provider stated it verified this address, and we reached
                # that claim over our own server-to-server exchange -- so it is
                # verified here too, and no confirmation email is needed.
                email_verified=True,
            )
        except sqlite3.IntegrityError:
            # Lost a race with a concurrent sign-in for the same address.
            log.warning("oauth: collision creating an account for a %s identity",
                        provider.key)
            return _user_by_email(who.email)
        candidate = repo.get_user_by_id(user_id)
        log.info("oauth: created %s from a verified %s address",
                 username, provider.key)

    if not repo.link_identity(candidate.id, provider.key, who.subject,
                              email=who.email):
        # Lost a race, or that subject is already bound elsewhere. Never
        # re-point an existing link.
        log.warning("oauth: could not link %s to %s", provider.key, candidate.username)
        return None

    log.info("oauth: linked %s to %s's account on first sign-in",
             provider.key, candidate.username)
    return candidate


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


class CompleteRequest(BaseModel):
    """Finishing a sign-up that started at a provider with no email."""

    handle: str = Field(min_length=1, max_length=128)
    username: str = Field(min_length=1, max_length=64)
    email: str = Field(min_length=1, max_length=254)
    full_name: str = Field(default="", max_length=120)
    accept_terms: bool = False


@router.post("/complete", status_code=status.HTTP_201_CREATED)
def complete(body: CompleteRequest, request: Request, response: Response):
    """Turn a parked provider identity into a real account.

    Reached only by someone holding a handle minted by the callback, which is
    itself only issued after a completed OAuth round-trip. So this cannot be
    used to create an account out of nothing: no handle, no account.

    The address is NOT verified here. Unlike Google, X never told us anything
    about it -- the person typed it in a moment ago, which makes it a claim.
    It is stored unverified and a confirmation is sent if mail is configured.
    That matters beyond tidiness: an address that could be marked verified by
    typing it would let an X user claim someone else's Google identity later.
    """
    ip = auth.client_ip(request)

    if wait := auth.signup_throttle.retry_after(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many accounts created from here. Try again later.",
            headers={"Retry-After": str(wait)},
        )

    parked = repo.take_pending_oauth(repo.hash_token(body.handle))
    if parked is None:
        # Unknown, expired or already spent -- one message for all three.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That sign-up link has expired. Please start again.",
        )

    username = body.username.strip()
    email = body.email.strip()
    if problem := auth.username_problem(username):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
    if problem := auth.email_problem(email):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
    if not body.accept_terms:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Please accept the Terms of Service and Privacy Policy.")

    auth.signup_throttle.record(ip)

    try:
        user_id = repo.create_oauth_user(
            username, full_name=body.full_name.strip(), email=email,
            email_verified=False,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username or email is already registered.",
        )

    if not repo.link_identity(user_id, parked["provider"], parked["subject"],
                              email=email):
        # The subject was bound to someone else between the callback and now.
        # The account just created has no identity attached and no password, so
        # it would be unreachable -- remove it rather than leave a ghost.
        log.warning("oauth: could not link %s after completion; rolling back",
                    parked["provider"])
        repo.delete_user(username)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That account is already linked. Try signing in instead.",
        )

    token_raw = repo.new_session(user_id, ip=ip,
                                 user_agent=request.headers.get("user-agent", ""))
    auth.set_session_cookie(response, token_raw)
    repo.touch_login(user_id)
    log.info("oauth: completed %s sign-up as %s", parked["provider"], username)

    verification.send_if_configured(user_id, email, username)
    return {"username": username, "next": parked.get("next_path") or "/"}
