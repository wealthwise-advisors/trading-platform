"""Schwab OAuth2 flow — thin wrapper around SchwabDataProvider's existing
auth methods (get_auth_url/complete_auth/is_authenticated/needs_reauth),
same three-step flow as ui/app.py's sidebar widget: authorize in browser,
paste the redirect URL back, submit.

Per project convention: this app never attempts to silently re-authenticate
on its own — token refresh within a session is handled by the schwabdev
Client's background thread, but a *new* 7-day login always requires the
user to click through Schwab's own login page, so the API can only ever
surface status and accept the user-submitted redirect URL.
"""

from fastapi import APIRouter, HTTPException

from api.schemas.schwab import SchwabStatus, SchwabAuthUrl, SchwabCompleteAuthRequest

router = APIRouter(prefix="/schwab", tags=["schwab"])


def _get_provider():
    from src.data.schwab_provider import SchwabDataProvider
    return SchwabDataProvider()


@router.get("/status", response_model=SchwabStatus)
def get_status():
    try:
        provider = _get_provider()
    except Exception as e:
        return SchwabStatus(available=False, authenticated=False, needs_reauth=False,
                             hours_remaining=0.0, error=str(e))
    return SchwabStatus(
        available=True,
        authenticated=provider.is_authenticated(),
        needs_reauth=provider.needs_reauth(),
        hours_remaining=provider.refresh_token_hours_remaining(),
    )


@router.get("/auth-url", response_model=SchwabAuthUrl)
def get_auth_url():
    try:
        provider = _get_provider()
    except Exception as e:
        raise HTTPException(400, str(e))
    return SchwabAuthUrl(auth_url=provider.get_auth_url())


@router.post("/complete-auth", response_model=SchwabStatus)
def complete_auth(req: SchwabCompleteAuthRequest):
    try:
        provider = _get_provider()
    except Exception as e:
        raise HTTPException(400, str(e))
    try:
        provider.complete_auth(req.redirect_url)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))
    return SchwabStatus(
        available=True,
        authenticated=provider.is_authenticated(),
        needs_reauth=provider.needs_reauth(),
        hours_remaining=provider.refresh_token_hours_remaining(),
    )
