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

from fastapi import (APIRouter, BackgroundTasks, HTTPException, Request,
                     Response, status)
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from api import auth, captcha, verification
from db import backtests as backtest_blobs
from db import users as repo

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    #: Turnstile's result. Only demanded once this (ip, username) pair has
    #: already failed repeatedly -- see the challenge check in login().
    captcha_token: str = Field(default="", max_length=4096)
    #: The "Remember me" box. True keeps the cookie for SESSION_TTL; false
    #: makes it a session cookie the browser drops when it closes.
    #:
    #: Defaults to FALSE -- the safer of the two.
    #:
    #: It defaulted to True to protect anyone on a cached older page from being
    #: signed out by the deploy. That was the right worry and the wrong answer:
    #: it meant the common case, a caller who says nothing, got the week-long
    #: cookie. On a platform wired to a live brokerage, staying signed in is
    #: the choice that should be made deliberately, not the one that happens by
    #: omission. Anyone on the old page now closes their browser and signs in
    #: again, which is a mild inconvenience rather than a surprise.
    remember: bool = False


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
    #: Whether the address has been proved. The dashboard needs it to decide
    #: between rendering and showing the "confirm your address" screen, so it
    #: travels with the identity rather than needing a second round trip.
    #: Defaults to False so any construction that predates it stays valid.
    email_verified: bool = False
    #: Whether an unverified address actually blocks anything right now. False
    #: while mail is unconfigured -- see api/auth.py's verification gate. The
    #: page must not tell someone to check an inbox that will never receive
    #: anything.
    verification_required: bool = False
    #: Whether this person has already been shown the introduction. Travels
    #: with the identity for the same reason email_verified does -- the shell
    #: branches on it on first render.
    onboarded: bool = True


class RequestCodeRequest(BaseModel):
    email: str = Field(min_length=1, max_length=254)


class VerifyCodeRequest(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    code: str = Field(min_length=1, max_length=12)
    remember: bool = False


class DeleteAccountRequest(BaseModel):
    """What the Close Account form sends.

    `password` is a re-authentication, not an identifier: the session already
    says who this is. It is required for accounts that have a password, so a
    borrowed unlocked browser cannot close somebody's account in two clicks.

    `confirm` must be the account's own username, typed. An OAuth-only account
    has no password to re-enter, and this is what stands in its place.
    """

    password: str = Field(default="", max_length=256)
    confirm: str = Field(default="", max_length=64)


def _identity(user) -> Me:
    """The Me payload for a resolved account, in one place.

    Three routes returned this shape by hand and a fourth was about to; adding
    a field meant remembering all of them, and the one that got forgotten would
    have reported every account as unverified.
    """
    return Me(username=user.username, full_name=user.full_name,
              email=user.email, country=user.country,
              email_verified=bool(user.email_verified),
              verification_required=auth.verification_blocks(user),
              onboarded=repo.is_onboarded(user.id))


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

    # CAPTCHA fallback: demanded only after this pair has failed repeatedly.
    #
    # The throttle alone blocks a burst from one place; it does nothing about a
    # patient attacker who stays under the ceiling, or a botnet that spreads
    # attempts across addresses. A challenge after a few failures costs a real
    # person nothing -- they have already typed a wrong password and are about
    # to try again -- and costs an automated one the whole attack.
    #
    # It is NOT demanded on the first attempt. Putting a challenge in front of
    # every sign-in taxes everybody for the behaviour of nobody, and Turnstile
    # is dormant on a deployment that has not configured it, in which case
    # captcha.verify returns True and this is a no-op.
    if auth.throttle.failures_for(ip, body.username) >= auth.CAPTCHA_AFTER_FAILURES:
        if not captcha.verify(body.captcha_token, ip):
            auth.throttle.record_failure(ip, body.username)
            log.warning("login challenge failed for %r from %s", body.username, ip)
            # The SAME message as a wrong password. A distinct one would say
            # "this username has failed before", which is a membership signal.
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Invalid username or password.")

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
    auth.set_session_cookie(response, token, remember=body.remember)
    repo.touch_login(user.id)
    log.info("login: %s from %s (remember=%s)", user.username, ip, body.remember)
    return _identity(user)


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
    return _identity(user)


@router.delete("/me")
def close_account(body: DeleteAccountRequest, request: Request, response: Response):
    """Close the signed-in account and remove what belongs to it.

    Deliberately NOT behind `Depends(auth.require_user)`, and the reason is the
    same one that makes /me exempt: require_user now refuses an account whose
    address is unproved. Routing this through it would mean someone who
    registered with a typo'd address -- the person with the strongest reason to
    want the account gone -- could not close it. The session check is done here
    instead, identically.

    The identity comes from the session and nothing else. There is no username
    or id in the request body, so there is no parameter to tamper with and no
    way to aim this at another account; the audit's "attempt to delete another
    user" case is unrepresentable rather than merely rejected.
    """
    user = repo.resolve_session(request.cookies.get(auth.COOKIE, ""))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authentication required.")

    ip = auth.client_ip(request)
    wait = auth.throttle.retry_after(ip, user.username)
    if wait:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again shortly.",
            headers={"Retry-After": str(wait)},
        )

    # Typing the username is the deliberate act. It is what stands between a
    # misread dialog and an irreversible one, and it is the only confirmation
    # an OAuth-only account can give.
    if (body.confirm or "").strip().lower() != user.username.lower():
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Type {user.username} to confirm.")

    # Re-authentication, on the same throttle as the login route so this cannot
    # become a quieter way to guess a password.
    if user.has_password:
        if not auth.verify_password(user.password_hash, body.password or ""):
            auth.throttle.record_failure(ip, user.username)
            log.warning("failed close-account password for %s from %s",
                        user.username, ip)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                                "That password is not correct.")
        auth.throttle.record_success(ip, user.username)

    removed = repo.delete_account(user.id)
    if removed is None:
        # Two requests raced and the other one won. The account is gone, which
        # is what was asked for, so this is not an error.
        auth.clear_session_cookie(response)
        return {"ok": True, "backtests": 0, "trades": 0}

    # Sidecars last, and outside the transaction: the rows are already gone, so
    # a file that will not delete leaves orphaned bytes on disk rather than an
    # account the person was told was closed and was not.
    try:
        backtest_blobs.purge_blobs(removed["backtest_ids"])
    except Exception:
        log.exception("could not purge Parquet sidecars for %s", removed["username"])

    auth.clear_session_cookie(response)
    log.info("account closed by its owner: %s from %s", removed["username"], ip)
    return {"ok": True,
            "backtests": removed["backtests"],
            "trades": removed["trades"]}


@router.post("/request-code")
def request_code(body: RequestCodeRequest, request: Request,
                 background: BackgroundTasks):
    """Email a six-digit sign-in code.

    A second way in for someone who does not want to type a password, and the
    only one available to an account whose password is forgotten but whose
    inbox is not.

    ANSWERS IDENTICALLY whether or not the address has an account, for exactly
    the reason /forgot-password does: anything else is a membership oracle that
    needs no password to operate. Same body, same status, and the send goes to
    a BackgroundTask so a real send and a no-op cannot be told apart by how
    long the reply took.

    An account with no PASSWORD is still eligible -- this is a different
    credential, resting on the inbox rather than on something remembered. An
    account with an UNPROVED address is not: issuing a code to an address
    nobody has confirmed would hand a way in to whoever typed it, which is the
    same reasoning that governs reset for OAuth-only accounts.
    """
    ip = auth.client_ip(request)
    if wait := auth.recovery_throttle.retry_after(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a few minutes and try again.",
            headers={"Retry-After": str(wait)},
        )
    auth.recovery_throttle.record(ip)

    email = (body.email or "").strip()
    user = repo.get_user_by_email(email) if email else None
    if user and user.is_active and user.email_verified:
        code = verification.new_login_code(user.id)
        background.add_task(verification.send_login_code,
                            user.email, user.username, code)
        log.info("sign-in code issued for %s from %s", user.username, ip)
    else:
        log.info("sign-in code requested for an unusable address from %s", ip)

    return {"ok": True, "detail": ("If that address can sign in here, we have "
                                   "sent it a six-digit code. It expires in "
                                   "10 minutes.")}


@router.post("/verify-code", response_model=Me)
def verify_code(body: VerifyCodeRequest, request: Request, response: Response):
    """Trade a correct code for a session.

    Every failure -- no such address, wrong code, expired, already spent, too
    many guesses -- is the same 401 with the same sentence. Telling them apart
    would say "that address has an account and you got the code wrong", which
    is the oracle the request half was careful not to be.
    """
    ip = auth.client_ip(request)
    email = (body.email or "").strip()

    # On the login throttle, keyed on the address, so guessing codes spends the
    # same budget as guessing passwords rather than a separate untracked one.
    if wait := auth.throttle.retry_after(ip, f"code:{email}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again shortly.",
            headers={"Retry-After": str(wait)},
        )

    user = repo.get_user_by_email(email) if email else None
    ok = bool(
        user and user.is_active and user.email_verified
        and repo.take_login_code(user.id, (body.code or "").strip(),
                                 verification.LOGIN_CODE_MAX_ATTEMPTS)
    )
    if not ok:
        auth.throttle.record_failure(ip, f"code:{email}")
        log.warning("failed sign-in code from %s (address usable=%s)",
                    ip, bool(user))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="That code is not valid. It may have "
                                   "expired or already been used.")

    auth.throttle.record_success(ip, f"code:{email}")
    token = repo.new_session(user.id, ip=ip,
                             user_agent=request.headers.get("user-agent", ""))
    auth.set_session_cookie(response, token, remember=body.remember)
    log.info("code sign-in: %s from %s", user.username, ip)
    return _identity(user)


@router.get("/export")
def export_my_data(request: Request):
    """A copy of everything this account holds, as a JSON download.

    web/public/privacy.html §6 has offered "a copy of your data" since the
    policy was written, and nothing could produce one -- the operator would
    have had to hand-write SQL against production. This is that copy, and it is
    the reason the sentence is now true.

    Session-resolved rather than behind require_user, like the delete route:
    getting your own data out must not depend on having confirmed an address,
    least of all for someone who registered with an address they cannot reach.

    Credentials are excluded -- see repo.export_account. The password hash and
    the session/token hashes are keys, not facts about a person, and a data
    export is a file people forward to themselves.
    """
    user = repo.resolve_session(request.cookies.get(auth.COOKIE, ""))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authentication required.")

    data = repo.export_account(user.id)
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found.")

    stamp = data["exported_at"].replace(":", "").replace("-", "")
    filename = f"autotrader-{user.username}-{stamp}.json"
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/onboarded")
def finish_onboarding(request: Request):
    """Record that this person has seen the introduction.

    Server-side, not localStorage: in the browser the welcome screen reappears
    on every new machine and disappears for good the moment site data is
    cleared, and neither of those is what the flag means. Idempotent, so a
    double-click or a retry cannot rewrite the date.
    """
    user = repo.resolve_session(request.cookies.get(auth.COOKIE, ""))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authentication required.")
    repo.mark_onboarded(user.id)
    return {"ok": True, "onboarded": True}


@router.post("/register", response_model=Me, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, request: Request, response: Response,
             background: BackgroundTasks):
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

    # The password is hashed HERE, before either branch, and the digest is used
    # in only one of them. That is deliberate waste: argon2id at 64 MiB is by
    # far the most expensive thing this route does, and hashing only on the
    # success path would make a collision reply measurably sooner. Both paths
    # now pay the same cost whatever the answer.
    password_hash = auth.hash_password(body.password)

    # ── the confirm-first path ──────────────────────────────────────────────
    #
    # Registration used to answer 201 for a free address and 409 for a taken
    # one. That is a membership oracle: point it at a list of addresses with a
    # fresh username each time and it reports, precisely, which of those people
    # hold accounts here. The wording was already careful -- "that username OR
    # email" -- but the STATUS CODE gave it away regardless, and so did the
    # presence of a Set-Cookie header on one branch and not the other.
    #
    # So neither branch signs anyone in, and both return the identical body.
    # A free address gets an account plus a confirmation link; a taken one gets
    # no account at all and a note to the person who already owns it, telling
    # them somebody tried. Nothing an unauthenticated caller can observe --
    # status, body, headers, or timing -- differs between the two.
    #
    # This is also what makes ownership a precondition rather than a formality:
    # no session exists until the link in the mailbox is clicked, so an account
    # cannot be used by whoever merely typed the address.
    #
    # It requires mail that reaches strangers. Where that is not true the old
    # behaviour stands, because the alternative is a registration form nobody
    # can complete -- see the fallback below, and auth.verification_enforced().
    if auth.verification_enforced():
        existing = repo.get_user_by_email(email) or repo.get_user(username)
        if existing is None:
            user_id = repo.create_user(
                username, password_hash,
                full_name=(body.full_name or "").strip(),
                email=email, country=(body.country or "").strip(),
                phone=(body.phone or "").strip(),
                email_verified=False,
            )
            log.info("registered (unconfirmed): %s from %s", username, ip)
            background.add_task(verification.send_if_configured,
                                user_id, email, username)
        else:
            # No account, no hint. The person who owns the address is told, so
            # a real collision is still actionable by the only party entitled
            # to know about it.
            log.info("registration collision from %s for %r", ip, username)
            background.add_task(verification.send_registration_collision,
                                email, existing.username)
        # 202, not 201: nothing was necessarily created, and saying "created"
        # would be a lie on one of the two branches.
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"ok": True, "confirm_required": True,
                     "detail": ("Check your email. If that address can be used "
                                "here, we have sent a link to finish setting up "
                                "the account.")},
        )

    # ── fallback: mail cannot reach a stranger ──────────────────────────────
    #
    # Confirm-first is impossible without deliverable mail -- the link never
    # arrives and the account can never be finished. So this keeps the previous
    # behaviour, INCLUDING its enumeration exposure, which is a smaller harm
    # than a signup form that cannot be completed by anyone. Configuring a
    # sending domain or SMTP closes it automatically; nothing else has to be
    # remembered.
    try:
        user_id = repo.create_user(
            username, password_hash,
            full_name=(body.full_name or "").strip(),
            email=email, country=(body.country or "").strip(),
            phone=(body.phone or "").strip(),
            email_verified=False,
        )
    except sqlite3.IntegrityError:
        # Which of username or email collided is still not disclosed.
        log.info("registration collision from %s for %r", ip, username)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username or email is already registered.",
        )

    token = repo.new_session(user_id, ip=ip,
                             user_agent=request.headers.get("user-agent", ""))
    auth.set_session_cookie(response, token)
    repo.touch_login(user_id)
    log.info("registered: %s from %s", username, ip)

    verification.send_if_configured(user_id, email, username)

    # Read back rather than echoing the request, so the new account's
    # verification state comes from the row that was actually written. The page
    # branches on it immediately -- a hand-built optimistic answer here is how
    # a freshly registered person gets told they are verified when they are not.
    created = repo.get_user_by_id(user_id)
    if created is not None:
        return _identity(created)
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
        # Whether registration is on the confirm-first path: no session until a
        # link in the mailbox is clicked, and one identical answer whether or
        # not the address is already taken.
        #
        # Published because it was otherwise UNKNOWABLE from outside. It is set
        # by mail being deliverable AND by an operator escape-hatch env var, and
        # a deployment could sit with the gate quietly off -- enumeration live,
        # unconfirmed accounts usable -- with nothing anywhere to say so short of
        # shell access on the box. That is exactly the shape of a security
        # control that fails silently.
        #
        # Not a disclosure. It describes the DEPLOYMENT, never an account, so it
        # carries no membership signal; and anyone can observe the same fact by
        # registering once. The sign-up page uses it to say whether a
        # confirmation email is coming.
        "confirm_required": auth.verification_enforced(),
    }


@router.get("/verify-email")
def verify_email(request: Request, token: str = ""):
    """Spend a verification link.

    A GET because it is reached by clicking a link in an email, and a browser
    can only issue a GET that way. That normally argues for not changing state
    in a GET -- the exception holds here because the token is single-use,
    unguessable and short-lived, so a prefetch spending it costs the person a
    second click on "resend" rather than anything irreversible.

    Answers with a redirect to the sign-in page rather than JSON: whoever
    follows this link is a person looking at a browser, not a script.
    """
    # Rate-limited like every other token-consuming route. The token is 32
    # random bytes so guessing one is not a real threat, but an endpoint that
    # will hit the database as fast as it is asked is a free denial-of-service
    # lever, and this was the only auth route with no ceiling at all. Keyed on
    # IP alone -- there is no account to key on until the token resolves.
    ip = auth.client_ip(request)
    if wait := auth.verify_throttle.retry_after(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again shortly.",
            headers={"Retry-After": str(wait)},
        )
    auth.verify_throttle.record(ip)

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
    if wait := auth.verify_throttle.retry_after(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later.",
            headers={"Retry-After": str(wait)},
        )
    auth.verify_throttle.record(ip)

    if user.email_verified:
        return {"ok": True, "sent": False, "detail": "That address is already confirmed."}
    if not user.email:
        return {"ok": True, "sent": False, "detail": "This account has no email address."}
    if not verification.configured():
        return {"ok": True, "sent": False,
                "detail": "Email is not configured on this server."}

    sent = verification.send_if_configured(user.id, user.email, user.username)
    if sent:
        return {"ok": True, "sent": True, "detail": "Sent. Check your inbox and spam."}

    # The provider's own explanation, to the person whose address it is.
    #
    # Not a disclosure: this endpoint already requires a session, and the only
    # thing being revealed is why a message to the caller's OWN address did not
    # arrive. Without it the failure is a log line on a host reachable only over
    # SSH, which is how "the email did not come" becomes unanswerable.
    return {"ok": True, "sent": False,
            "detail": verification.last_error() or "The email could not be sent."}


class ForgotRequest(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    captcha_token: str = Field(default="", max_length=4096)


class ResetRequest(BaseModel):
    token: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=256)


#: The single answer /forgot-password gives, whatever actually happened.
_FORGOT_REPLY = {
    "ok": True,
    "detail": ("If that address has an account, a reset link is on its way. "
               "Check your inbox, and your spam folder."),
}


@router.post("/forgot-password")
def forgot_password(body: ForgotRequest, request: Request,
                    background: BackgroundTasks):
    """Start a password reset.

    ALWAYS returns the same body and the same status, whether or not the
    address has an account. Anything else turns this into a free membership
    oracle: point it at a list of addresses and it tells you which people have
    accounts here -- the same reason /register refuses without saying whether
    it was the username or the email that collided.

    That extends to TIMING, which is the part that is easy to get wrong. A real
    send makes an outbound HTTPS call to Resend taking a few hundred
    milliseconds; a miss makes none. Returning as soon as the answer is known
    would therefore let a miss reply measurably faster, and the identical body
    would leak anyway to anyone with a stopwatch.

    So the send is handed to a BackgroundTask and the response is returned
    immediately in BOTH branches. Nothing the caller can observe depends on
    whether an account was found -- and it also means a slow or hanging mail
    provider cannot hold the request open.

    OAUTH-ONLY ACCOUNTS
    -------------------
    An account whose only credential is a provider gets a reset link ONLY if
    its address was verified by that provider. For a password account, reset
    RESTORES a credential that existed. For an OAuth-only account it CREATES a
    new kind of credential that never existed -- so it must rest on an address
    somebody proved, not one that was typed. X sign-ups type their own address
    and nobody checks it; sending a reset there would hand a brand-new way in
    to whoever holds an unverified inbox, while the X link keeps working for
    the original person. Two people, one account, neither aware.
    """
    ip = auth.client_ip(request)

    # Rate-limited on the signup budget: this sends mail on demand to an
    # address the caller chooses, which is how a sending domain gets
    # blacklisted. The 429 is the one response that legitimately differs, and
    # it depends on the CALLER, not on whether the address exists.
    if wait := auth.recovery_throttle.retry_after(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a few minutes and try again.",
            headers={"Retry-After": str(wait)},
        )
    auth.recovery_throttle.record(ip)

    # NO CAPTCHA HERE, deliberately -- see the note on /forgot-username.
    user = repo.get_user_by_email(body.email.strip())

    if user is None or not user.is_active:
        log.info("password reset asked for an unknown or disabled address from %s", ip)
    elif _may_reset(user):
        # Queued, not awaited. See the note on timing above: doing it inline
        # makes a hit measurably slower than a miss and undoes every other
        # precaution in this function.
        background.add_task(verification.send_reset,
                            user.id, user.email, user.username)
    else:
        # OAuth-only on an unverified address. Refused, silently -- saying so
        # would reveal both that the account exists and how it signs in.
        log.warning("password reset refused for %r: no password and an "
                    "unverified address", user.username)

    return _FORGOT_REPLY


def _may_reset(user) -> bool:
    """Whether this account may set a password by email.

    True for anything that already has a usable password -- reset restores what
    was there. True for a passwordless account whose address a provider
    verified. False for a passwordless account whose address is merely claimed.
    """
    if user.email_verified:
        return True
    # A password account is identified by having a hash anyone can actually
    # verify against. OAuth-created accounts hold argon2 over random bytes, so
    # no password matches -- but the hash is well-formed, so it cannot be told
    # apart by inspection. `has_password` records the distinction at creation.
    return bool(getattr(user, "has_password", True))


@router.post("/reset-password", response_model=Me)
def reset_password(body: ResetRequest, request: Request, response: Response):
    """Finish a password reset.

    Signs the person in afterwards, because the alternative is bouncing someone
    who has just proved control of the account back to a login form to type the
    password they set four seconds ago.
    """
    ip = auth.client_ip(request)

    if wait := auth.throttle.retry_after(ip, "reset"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again shortly.",
            headers={"Retry-After": str(wait)},
        )

    if problem := auth.password_problem(body.password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)

    user_id = verification.consume_reset(body.token, auth.hash_password(body.password))
    if user_id is None:
        # Unknown, expired, already spent, or a verification token being
        # offered as a reset. One message for all four.
        auth.throttle.record_failure(ip, "reset")
        log.warning("a bad password-reset token was offered from %s", ip)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That reset link is invalid or has expired. Please ask for a new one.",
        )

    auth.throttle.record_success(ip, "reset")
    user = repo.get_user_by_id(user_id)
    log.info("password reset completed for %s from %s", user.username, ip)

    # take_reset_token revoked every session this account had, inside the same
    # transaction as the password change. Someone resets because they believe
    # another person has their password; leaving that person signed in would
    # make the reset change nothing for them. A fresh session is issued here,
    # so the reset does not sign the rightful owner out of the tab they are in.
    token_raw = repo.new_session(user_id, ip=ip,
                                 user_agent=request.headers.get("user-agent", ""))
    auth.set_session_cookie(response, token_raw)
    repo.touch_login(user_id)
    return _identity(user)


class ForgotUsernameRequest(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    captcha_token: str = Field(default="", max_length=4096)


#: The single answer /forgot-username gives, whatever actually happened.
_USERNAME_REPLY = {
    "ok": True,
    "detail": ("If that address has an account, we have emailed the username "
               "to it. Check your inbox, and your spam folder."),
}


@router.post("/forgot-username")
def forgot_username(body: ForgotUsernameRequest, request: Request,
                    background: BackgroundTasks):
    """Email someone their own username.

    Sign-in is by username, so forgetting it locks a person out exactly as
    completely as forgetting the password -- and password reset does not help,
    because it asks for the address and then never says what the username is.

    No token, no link. A username is half of a public pair and grants nothing
    on its own, so nothing here can be spent. That is what makes it safe to
    send on a bare request.

    Same disclosure rule as /forgot-password: one response for every outcome,
    and the send is queued rather than awaited so a hit cannot be told from a
    miss by timing.
    """
    ip = auth.client_ip(request)

    if wait := auth.username_throttle.retry_after(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a few minutes and try again.",
            headers={"Retry-After": str(wait)},
        )
    auth.username_throttle.record(ip)

    # NO CAPTCHA ON THE TWO RECOVERY ENDPOINTS.
    #
    # It was here, and it locked people out of the one flow that exists for
    # people already locked out. The widget is a third-party script from
    # challenges.cloudflare.com, and when an extension, a privacy setting or a
    # network blocks it, nothing renders -- so there is no token, the server
    # refuses, and the person sees a form that simply will not submit with no
    # way to fix it from their side. That happened here, to two people, on the
    # deployed site.
    #
    # What it was protecting against was mail-bombing an address. The per-IP
    # budget above already does that: five requests an hour, then a block. The
    # CAPTCHA was a second lock on a door the rate limiter had already bolted,
    # and it was the only one that could fail closed on a legitimate person.
    #
    # Registration KEEPS its CAPTCHA. That is where bot protection earns its
    # keep -- it creates accounts, the rate limit alone is a weaker answer, and
    # someone signing up can retry from another browser. Someone who has
    # forgotten their password cannot.
    user = repo.get_user_by_email(body.email.strip())
    if user is None or not user.is_active:
        log.info("username reminder asked for an unknown address from %s", ip)
    else:
        background.add_task(verification.send_username, user.email, user.username)

    return _USERNAME_REPLY
