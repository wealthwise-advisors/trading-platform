"""Who the app is running as, and the introduction flag.

Sign-in, registration, password reset, email and phone verification, OAuth
and account deletion were all removed on 2026-10-16 -- the app opens straight
from its link. Two routes remain because the dashboard still uses them:

    GET  /api/auth/me          the workspace account, for the header's
                               initials and the first-run introduction
    POST /api/auth/onboarded   record that the introduction was seen

The prefix stays /auth so the dashboard's existing calls keep working.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api import auth
from db import users as repo

router = APIRouter(prefix="/auth", tags=["auth"])


class Me(BaseModel):
    username: str
    full_name: str
    email: str
    country: str
    #: Whether this account has already been shown the introduction. The
    #: shell branches on it on first render, so it travels with the identity.
    onboarded: bool = True


@router.get("/me", response_model=Me)
def me(user=Depends(auth.require_user)):
    """The account every request runs as. Never 401: there is no sign-in."""
    return Me(username=user.username, full_name=user.full_name,
              email=user.email, country=user.country,
              onboarded=repo.is_onboarded(user.id))


@router.post("/onboarded")
def finish_onboarding(user=Depends(auth.require_user)):
    """Record that the introduction was seen.

    Server-side, not localStorage: in the browser the welcome screen would
    reappear on every new machine and vanish for good whenever site data is
    cleared. Idempotent, so a double-click or a retry cannot rewrite the date.
    """
    repo.mark_onboarded(user.id)
    return {"ok": True, "onboarded": True}
