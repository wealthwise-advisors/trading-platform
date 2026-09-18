"""Shapes for the paper-trading endpoints."""

from typing import Optional

from pydantic import BaseModel, Field

from api.deps import SYMBOL_PATTERN


class LiveStartRequest(BaseModel):
    strategy_id: str
    symbol: str = Field(pattern=SYMBOL_PATTERN)
    params: dict = Field(default_factory=dict)
    # Bounded at the boundary as well as in the guard. The guard is the rail
    # that matters, but a request asking for 10,000 contracts should be
    # refused before anything constructs a session out of it.
    contracts: int = Field(default=1, ge=1, le=10)
    initial_capital: float = Field(default=100_000.0, gt=0, le=10_000_000)
    commission: float = Field(default=2.5, ge=0, le=100)


class LiveBar(BaseModel):
    """One CLOSED bar, pushed by the dashboard.

    `t` is the bar's own open time, and it is what deduplication keys on --
    not arrival order, which a retry or a second tab would get wrong.
    """

    t: str
    o: float
    h: float
    l: float
    c: float
    v: float = 0.0


class LiveEvent(BaseModel):
    at: str
    kind: str
    text: str


class LiveStatus(BaseModel):
    running: bool
    #: "paper" today. A live mode would be a different value here, and the
    #: dashboard keys its warning banner off it rather than off a guess.
    mode: str
    strategy: str
    symbol: str
    contracts: int
    started_at: Optional[str]
    stopped_at: Optional[str]
    bars_seen: int
    position: int
    cash: float
    fills: int
    orders_sent: int
    orders_remaining: int
    halted: bool
    halt_reason: Optional[str]
    #: Bars the session refused because it had already decided about them.
    #: Surfaced so a feed that is re-sending is visible rather than silent.
    duplicates_ignored: int = 0
    last_bar_at: Optional[str] = None
    events: list[LiveEvent]
