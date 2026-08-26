"""Sign in, sign out, and who-am-I.

These are the only routes in the application that an unauthenticated caller may
reach, alongside /api/health and /api/version.
"""

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from api import auth
from db import users as repo

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


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


@router.post("/register", status_code=status.HTTP_403_FORBIDDEN)
def register():
    """Registration is closed, and closed HERE rather than by hiding a button.

    The Create Account screen exists in the frontend, so something has to
    answer it. This is the enforcement point: a private instance provisions
    accounts with scripts/manage_users.py, not over the internet.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Registration is not open. Ask an administrator for an account.",
    )
