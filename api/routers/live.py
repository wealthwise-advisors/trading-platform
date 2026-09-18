"""Paper trading sessions: start one, stop it, ask how it is doing.

THE ONE THING TO KNOW ABOUT THIS FILE. It is the only place that decides which
broker a live session trades through, and it constructs a PaperBroker. Nothing
downstream -- not PaperSession, not the strategy, not the guard -- can reach a
real account, because none of them build a broker. Pointing this at a live
broker is a deliberate edit here, in one visible place, made by someone who
meant to.

Sessions are per user and in memory. That is a real limitation and it is
stated rather than hidden: restarting the API ends every session, and a second
API process would not see the first one's. For a single-desk tool running one
container that is the honest trade against standing up a job store; when this
grows a second replica it needs one.
"""

from __future__ import annotations

import threading

from dataclasses import dataclass
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from api import auth
from api.schemas.live import LiveBar, LiveStartRequest, LiveStatus
from api.strategy_registry import build_strategy
from src.broker.order_guard import OrderGuard
from src.broker.paper_broker import PaperBroker
from src.live.paper_session import PaperSession, default_limits

router = APIRouter(prefix="/live", tags=["live"])

#: user_id -> session. One session each: a second would trade the same account
#: from two places, and whichever filled first would leave the other acting on
#: a position it did not know had changed.
_SESSIONS: dict[int, PaperSession] = {}
_LOCK = threading.RLock()

#: How long a session may hear nothing from the dashboard before it is
#: stopped. The browser drives the bars, so silence means the tab is gone --
#: closed, crashed, asleep or offline. Generous enough to survive a slow
#: reload, short enough that an abandoned session does not sit open for long.
STALE_AFTER_SECONDS = 90.0


@dataclass
class _IncomingBar:
    """What PaperSession.on_bar expects, built from the wire shape."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


def _reap_if_stale(session: PaperSession | None) -> PaperSession | None:
    """Stop a session whose dashboard has gone quiet.

    Done on read rather than on a timer: there is no scheduler in this process
    and a background thread for one dict would be more machinery than the job
    needs. Every status poll and every bar push runs it, which is often enough
    for a session nobody is watching to be closed within the timeout.
    """
    if session is not None and session.running and session.is_stale(STALE_AFTER_SECONDS):
        session.stop("dashboard disconnected -- no contact for "
                     f"{int(STALE_AFTER_SECONDS)}s")
    return session


def _session_for(user_id: int) -> PaperSession | None:
    with _LOCK:
        return _SESSIONS.get(user_id)


@router.post("/start", response_model=LiveStatus)
def start(req: LiveStartRequest, user=Depends(auth.require_user)):
    """Begin a paper session. Refuses if one is already running."""
    with _LOCK:
        existing = _SESSIONS.get(user.id)
        if existing is not None and existing.running:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A session is already running. Stop it before starting another.",
            )

        try:
            strategy = build_strategy(req.strategy_id, req.params)
        except (KeyError, TypeError, ValueError) as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown strategy: {e}")

        # PAPER. The broker is chosen here and nowhere else -- see the note at
        # the top of this file.
        broker = PaperBroker(
            initial_capital=req.initial_capital,
            commission_per_contract=req.commission,
        )
        session = PaperSession(
            strategy=strategy,
            broker=broker,
            symbol=req.symbol,
            contracts=req.contracts,
            guard=OrderGuard(limits=default_limits(req.symbol, req.contracts)),
        )
        _SESSIONS[user.id] = session
        return session.status()


@router.post("/bar", response_model=LiveStatus)
def push_bar(bar: LiveBar, user=Depends(auth.require_user)):
    """Feed one CLOSED bar.

    Only closed bars belong here. A bar still forming would let the strategy
    see a high before the bar has made it, which is reading the future by one
    tick and would make the paper result flatter than the real one.

    Idempotent by bar timestamp: re-sending a bar the session has already
    decided about is ignored and counted. That is what makes a reload safe --
    a dashboard coming back can re-send its recent bars without re-opening the
    trades they caused.
    """
    session = _reap_if_stale(_session_for(user.id))
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No session is running.")
    if not session.running:
        # Not an error: the dashboard may not have noticed yet. It gets the
        # status back and can stop pushing.
        return session.status()
    try:
        ts = datetime.fromisoformat(bar.t)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unparseable bar time {bar.t!r}")
    session.on_bar(_IncomingBar(ts, bar.o, bar.h, bar.l, bar.c, bar.v))
    return session.status()


@router.post("/heartbeat", response_model=LiveStatus)
def heartbeat(user=Depends(auth.require_user)):
    """The dashboard saying it is still open, between bars.

    Bars can be minutes apart; without this a session on any timeframe above a
    minute would look abandoned for most of its life.
    """
    session = _reap_if_stale(_session_for(user.id))
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No session is running.")
    if session.running:
        session.heartbeat()
    return session.status()


@router.post("/stop", response_model=LiveStatus)
def stop(user=Depends(auth.require_user)):
    session = _session_for(user.id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No session to stop.")
    session.stop()
    return session.status()


@router.get("/status", response_model=LiveStatus)
def get_status(user=Depends(auth.require_user)):
    """The session's state, or an idle one when there is none.

    Idle rather than 404: the dashboard polls this on every load, and a 404 on
    the ordinary case would fill the console with errors that mean nothing.
    """
    session = _reap_if_stale(_session_for(user.id))
    if session is None:
        return LiveStatus(running=False, mode="paper", strategy="", symbol="",
                          contracts=0, started_at=None, stopped_at=None,
                          bars_seen=0, position=0, cash=0.0, fills=0,
                          orders_sent=0, orders_remaining=0, halted=False,
                          halt_reason=None, events=[])
    return session.status()
