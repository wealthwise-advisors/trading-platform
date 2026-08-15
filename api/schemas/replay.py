"""Request/response models for the live-replay endpoints."""

from datetime import date, time
from typing import Optional

from pydantic import BaseModel, model_validator


class ReplayCreateRequest(BaseModel):
    symbol: str = "ES"
    #: Legacy single-timeframe field. Kept so existing callers keep working;
    #: when `timeframes` is omitted the session runs this one alone.
    timeframe: str = "5m"
    #: Multi-timeframe grid. The finest entry becomes the clock's base.
    timeframes: Optional[list[str]] = None
    #: "synthetic" | "external_csv" | "schwab" | "rithmic" -- same set the
    #: backtest endpoint accepts. Replay used to be synthetic-only.
    data_source: str = "synthetic"
    strategy_id: str
    params: dict = {}
    initial_capital: float = 100_000.0
    contracts_per_trade: int = 1
    commission_per_contract: float = 2.50
    start_date: date
    end_date: date
    #: Session window, matching the backtest form. Both None means 24 hours.
    #: session_start also anchors the VWAP daily reset (see calc_vwap_bands) --
    #: an overnight window like 18:00-17:00 must not reset at midnight.
    session_start: Optional[time] = time(9, 30)
    session_end: Optional[time] = time(16, 0)

    @model_validator(mode="after")
    def _default_timeframes(self):
        if not self.timeframes:
            self.timeframes = [self.timeframe]
        return self


class ReplayCreateResponse(BaseModel):
    replay_id: str
    #: Ticks of the shared clock -- one per bar of the finest timeframe.
    total_bars: int
    symbol: str
    strategy_name: str
    initial_capital: float
    #: Ordered fine -> coarse; the grid renders one pane per entry.
    timeframes: list[str] = []
    base_timeframe: str = ""
    #: Resolution the source frame was loaded at. Timeframes FINER than this
    #: cannot be added mid-session -- resampling down would invent bars -- so
    #: the client uses it to decide what needs a fresh session.
    data_timeframe: str = ""
    #: Bars available per timeframe, for per-pane progress display.
    bar_counts: dict[str, int] = {}
    data_source: str = "synthetic"
    #: Set when an overnight session made the fetch reach back a day earlier
    #: than requested, so its first session is whole. None when unchanged.
    fetch_start_date: Optional[date] = None
