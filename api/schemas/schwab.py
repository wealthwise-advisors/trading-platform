"""Request/response models for the Schwab OAuth endpoints."""

from typing import Optional

from pydantic import BaseModel


class SchwabStatus(BaseModel):
    available: bool          # SchwabDataProvider importable + credentials.yaml present
    authenticated: bool
    needs_reauth: bool
    hours_remaining: float
    error: Optional[str] = None


class SchwabAuthUrl(BaseModel):
    auth_url: str


class SchwabCompleteAuthRequest(BaseModel):
    redirect_url: str
