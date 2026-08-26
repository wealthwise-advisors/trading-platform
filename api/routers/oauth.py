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
    """Find the local account this provider identity signs in as.

    Returns None -- refusal -- rather than creating anything. That is the whole
    rule: OAuth is a second door into an existing account, never a way to make
    one. Every refusal is logged, because a stream of them is what an attempted
    takeover looks like.
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

    # 2. First time. X has no email to offer, so it can never get here -- it
    #    must be linked by an administrator first.
    if not provider.provides_email:
        log.warning("oauth: unlinked %s identity %s refused (no email from this "
                    "provider; link it with manage_users.py)",
                    provider.key, who.subject[:12])
        auth.throttle.record_failure(ip, f"oauth:{provider.key}")
        return None

    if not who.email or not who.email_verified:
        log.warning("oauth: %s gave an %s email; refused", provider.key,
                    "unverified" if who.email else "absent")
        auth.throttle.record_failure(ip, f"oauth:{provider.key}")
        return None

    candidate = _user_by_email(who.email)
    if candidate is None or not candidate.is_active:
        # No account, or a disabled one. Identical handling and one message, so
        # this cannot be used to test which addresses have accounts here.
        log.warning("oauth: no active account for a verified %s address from %s",
                    provider.key, ip)
        auth.throttle.record_failure(ip, f"oauth:{provider.key}")
        return None

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
