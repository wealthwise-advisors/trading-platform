"""Live quotes for the watchlist and the market summary.

WHY THIS CAN RETURN NOTHING, AND SAYS SO.
Quotes come from Schwab, and Schwab needs a 7-day login the user performs
themselves. With no tokens there is no price -- so the response carries
`connected: false` and an empty list rather than zeros. A watchlist showing
0.00 is indistinguishable from a market that has crashed to zero, and a
watchlist showing invented numbers is worse than one showing none.

The caller renders the disconnected state as "connect Schwab", which is the
truth: the panel works, the data source is not linked yet.
"""

from fastapi import APIRouter, Query

from api.schemas.quotes import QuotesResponse

router = APIRouter(prefix="/quotes", tags=["quotes"])

#: What the watchlist asks for when the caller names nothing. Futures roots,
#: because that is what this platform trades; the provider maps them to
#: Schwab's "/ES" form.
DEFAULT_SYMBOLS = ["ES", "NQ", "YM", "RTY", "CL", "GC"]

#: The index symbols behind the Market Summary tab. Schwab prefixes an index
#: with "$" and these are passed through untouched by the symbol mapper.
INDEX_SYMBOLS = ["$SPX", "$NDX", "$DJI", "$VIX"]


@router.get("", response_model=QuotesResponse)
def get_quotes(symbols: str = Query("", description="Comma-separated symbols")) -> QuotesResponse:
    wanted = [s.strip() for s in symbols.split(",") if s.strip()] or DEFAULT_SYMBOLS

    try:
        from src.data.schwab_provider import SchwabDataProvider
        provider = SchwabDataProvider()
    except Exception as e:
        return QuotesResponse(connected=False, quotes=[], reason=str(e))

    if not provider.is_authenticated():
        return QuotesResponse(
            connected=False, quotes=[],
            reason="Schwab is not connected. Sign in to Schwab to see live quotes.")

    try:
        rows = provider.quotes(wanted)
    except Exception as e:
        # A dead upstream is not a server fault: the panel stays, and says why
        # it is empty, instead of the whole results page failing with a 500.
        return QuotesResponse(connected=False, quotes=[], reason=f"Schwab quote request failed: {e}")

    return QuotesResponse(connected=True, quotes=rows, reason=None)
