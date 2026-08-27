"""Sign in, sign up, sign out, and who-am-I.

These are the only routes in the application that an unauthenticated caller may
reach, alongside /api/health and /api/version.

Registration is open. What it does not open is the broker: there is exactly one
Schwab connection and it belongs to the operator, so `users.is_owner` defaults
to 0 and is settable only from scripts/manage_users.py, which needs shell
access on the server. A new account gets the analysis app and nothing else.
"""

import logging
import sqlite3

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from api import auth, captcha, verification
from db import users as repo

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class RegisterRequest(BaseModel):
    """What the Create Account page sends.

    The field caps are the first line of defence and cost nothing: without
    them, an unauthenticated caller can hand the server a megabyte of full_name
    and make it argon2-hash and store it.
    """

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    email: str = Field(default="", max_length=254)
    full_name: str = Field(default="", max_length=120)
    country: str = Field(default="", max_length=80)
    phone: str = Field(default="", max_length=40)
    date_of_birth: str = Field(default="", max_length=32)
    accept_terms: bool = False
    #: Cloudflare Turnstile's result. Ignored while Turnstile is unconfigured;
    #: required once it is. See api/captcha.py.
    captcha_token: str = Field(default="", max_length=4096)


class Me(BaseModel):
    username: str
    full_name: str
    email: str
    country: str


@router.post("/login", response_model=Me)
def login(body: LoginRequest, request: Request, response: Response):
    ip = auth.client_ip(request)

    wait = auth.throttle.retry_after(ip, body.username)
    if wait:
        # 429 with Retry-After, not 401: the caller is being slowed, and saying
        # so is not a disclosure -- it is true of a wrong username as well.
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again shortly.",
            headers={"Retry-After": str(wait)},
        )

    user = repo.get_user(body.username)

    # Verify even when the user does not exist, against a throwaway hash, so a
    # missing username and a wrong password cost the same time. Without this,
    # response timing enumerates valid usernames.
    stored = user.password_hash if user else auth.hash_password("no-such-user")
    ok = auth.verify_password(stored, body.password)

    if not user or not ok or not user.is_active:
        auth.throttle.record_failure(ip, body.username)
        log.warning("failed login for %r from %s (exists=%s active=%s)",
                    body.username, ip, bool(user), bool(user and user.is_active))
        # One message for every cause. Never "no such user".
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid username or password.")

    if auth.needs_rehash(user.password_hash):
        repo.set_password(user.username, auth.hash_password(body.password))

    auth.throttle.record_success(ip, body.username)
    token = repo.new_session(user.id, ip=ip,
                             user_agent=request.headers.get("user-agent", ""))
    auth.set_session_cookie(response, token)
    repo.touch_login(user.id)
    log.info("login: %s from %s", user.username, ip)
    return Me(username=user.username, full_name=user.full_name,
              email=user.email, country=user.country)


@router.post("/logout")
def logout(request: Request, response: Response):
    raw = request.cookies.get(auth.COOKIE, "")
    if raw:
        repo.revoke_session(raw)          # server-side, not just the cookie
    auth.clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=Me)
def me(request: Request):
    """Who the caller is. The dashboard uses this to decide whether to render
    or bounce to the sign-in page."""
    user = repo.resolve_session(request.cookies.get(auth.COOKIE, ""))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authentication required.")
    return Me(username=user.username, full_name=user.full_name,
              email=user.email, country=user.country)


@router.post("/register", response_model=Me, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, request: Request, response: Response):
    """Create an account, and sign the new person in.

    Open to anyone. What that does NOT grant is the broker: `is_owner` is not a
    parameter of repo.create_user and defaults to 0 in the schema, so no route
    here -- present or future -- can hand out the operator's single Schwab
    connection. Every new account gets the analysis app and nothing else.

    The address starts unverified. Anyone can type anyone's email, so an
    address is a claim until a link sent to it comes back, and only a verified
    address is allowed to match an OAuth identity to this account.

    ORDER OF CHECKS
    ---------------
    Rate limit, then CAPTCHA, then validation, then the write. The limit is a
    dictionary lookup and the CAPTCHA is a network round-trip to Cloudflare, so
    checking the limit second would let a flood of signups become a flood of
    outbound requests -- turning a rate-limit into an amplifier.
    """
    ip = auth.client_ip(request)

    wait = auth.signup_throttle.retry_after(ip)
    if wait:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many accounts created from here. Try again later.",
            headers={"Retry-After": str(wait)},
        )
    # Counted on ATTEMPT, not on success. Counting successes would leave the
    # cheapest abuse -- hammering the endpoint with taken usernames to probe
    # which exist -- entirely unmetered.
    auth.signup_throttle.record(ip)

    if not captcha.verify(body.captcha_token, ip):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not confirm you are human. Please try again.",
        )

    username = (body.username or "").strip()
    email = (body.email or "").strip()

    if problem := auth.username_problem(username):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
    if problem := auth.email_problem(email):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
    if problem := auth.password_problem(body.password, username=username, email=email):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
    if not body.accept_terms:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Please accept the Terms of Service and Privacy Policy.")

    try:
        user_id = repo.create_user(
            username, auth.hash_password(body.password),
            full_name=(body.full_name or "").strip(),
            email=email, country=(body.country or "").strip(),
            phone=(body.phone or "").strip(),
            email_verified=False,
        )
    except sqlite3.IntegrityError:
        # UNIQUE on username, and from v5 on a non-empty email. Which of the
        # two collided is not disclosed: saying "that email is taken" tells an
        # unauthenticated caller who already has an account here.
        log.info("registration collision from %s for %r", ip, username)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username or email is already registered.",
        )

    # Signed in immediately. The alternative -- make them verify first -- puts
    # a wall in front of a product they cannot see yet, and it depends on mail
    # delivery that may not be configured. Verification gates what needs
    # verifying; it does not gate the front door.
    token = repo.new_session(user_id, ip=ip,
                             user_agent=request.headers.get("user-agent", ""))
    auth.set_session_cookie(response, token)
    repo.touch_login(user_id)
    log.info("registered: %s from %s", username, ip)

    verification.send_if_configured(user_id, email, username)

    return Me(username=username, full_name=(body.full_name or "").strip(),
              email=email, country=(body.country or "").strip())


@router.get("/signup-config")
def signup_config():
    """What the Create Account page needs to know before it renders.

    The Turnstile SITE key is public by design -- it identifies the widget and
    is rendered into the page. The SECRET key is never sent here and never
    leaves the server. Serving the site key from the API rather than baking it
    into the HTML means the page does not have to be rebuilt to turn the
    CAPTCHA on.
    """
    return {
        "captcha": {"provider": "turnstile", "site_key": captcha.site_key()},
        "email_verification": verification.configured(),
        "min_password_length": auth.MIN_PASSWORD_LENGTH,
    }


@router.get("/verify-email")
def verify_email(token: str = ""):
    """Spend a verification link.

    A GET because it is reached by clicking a link in an email, and a browser
    can only issue a GET that way. That normally argues for not changing state
    in a GET -- the exception holds here because the token is single-use,
    unguessable and short-lived, so a prefetch spending it costs the person a
    second click on "resend" rather than anything irreversible.

    Answers with a redirect to the sign-in page rather than JSON: whoever
    follows this link is a person looking at a browser, not a script.
    """
    user_id = verification.consume(token)
    reason = "verified" if user_id else "verify_failed"
    if user_id:
        log.info("email verified for user id %s", user_id)
    return RedirectResponse(f"/autotrader_signin.html?reason={reason}",
                            status_code=status.HTTP_303_SEE_OTHER)


@router.post("/resend-verification")
def resend_verification(request: Request):
    """Send another verification link to the signed-in account's address.

    Rate-limited on the same signup budget: this sends mail on demand to an
    address chosen by the caller, which is exactly the shape of an abuse that
    gets a sending domain blacklisted.

    Always reports success. Whether an address is deliverable is not something
    an authenticated caller needs told, and the failure modes -- already
    verified, no address, provider down -- are all things that would otherwise
    leak from the response.
    """
    user = repo.resolve_session(request.cookies.get(auth.COOKIE, ""))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required.")

    ip = auth.client_ip(request)
    if wait := auth.signup_throttle.retry_after(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later.",
            headers={"Retry-After": str(wait)},
        )
    auth.signup_throttle.record(ip)

    if not user.email_verified and user.email:
        verification.send_if_configured(user.id, user.email, user.username)
    return {"ok": True}
