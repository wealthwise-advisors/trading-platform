"""Response models for the live-quote endpoint."""

from typing import Optional

from pydantic import BaseModel


class Quote(BaseModel):
    symbol: str
    last: float
    change: float
    change_pct: float
    #: The contract a futures root resolved to — "/ESZ26" for ES. Without this
    #: field declared, FastAPI silently drops it from the response and the
    #: watchlist cannot say which contract it is quoting.
    contract: Optional[str] = None


class QuotesResponse(BaseModel):
    #: False when Schwab has no valid tokens, or the upstream call failed.
    #: The caller shows `reason` instead of prices -- never a zero, which on a
    #: price panel reads as a real number.
    connected: bool
    quotes: list[Quote]
    reason: Optional[str] = None
