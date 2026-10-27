"""POST /api/poc-average -- POC Average at given moments, for the Chart page.

Sir's rule (2026-10-27): a swing is flagged when any selected timeframe's POC
has the same whole number as the POC Average of all of them at that moment.
The Chart page sends its swing points' moments; this answers from the SAME
bars a Market Grid session with these settings would hold -- Market Grid's own
loader, session filter and bar grid, not a copy of them -- so the two pages
cannot disagree. tests/test_poc_average_api.py checks that against a real
Market Grid session.
"""

from datetime import date, time
from typing import Optional

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from api.deps import SYMBOL_PATTERN, get_contract_spec
from api.routers.replay import _apply_session, _load_bars, _source_timeframe
from src.analysis.poc_average import poc_average_at
from src.data.resample import TF_MINUTES, bar_anchor, resample_ohlcv

router = APIRouter(tags=["poc-average"])

#: Market Grid's eleven, 1m to 1h -- what sir compares across.
DEFAULT_TIMEFRAMES = ["1m", "3m", "5m", "10m", "15m", "20m", "25m", "30m", "35m", "45m", "1h"]


class PocAverageRequest(BaseModel):
    symbol: str = Field(default="ES", pattern=SYMBOL_PATTERN)
    data_source: str = "synthetic"
    start_date: date
    end_date: date
    session_start: Optional[time] = time(9, 30)
    session_end: Optional[time] = time(16, 0)
    timeframes: list[str] = Field(default_factory=lambda: list(DEFAULT_TIMEFRAMES), max_length=15)
    #: Naive Eastern timestamps -- each swing point's bar CLOSE.
    moments: list[str] = Field(max_length=2000)
    bins: int = Field(default=48, ge=4, le=500)
    value_area: float = Field(default=0.70, gt=0, le=1)

    @field_validator("timeframes")
    @classmethod
    def _intraday_only(cls, tfs: list[str]) -> list[str]:
        bad = [tf for tf in tfs if tf not in TF_MINUTES]
        if bad:
            raise ValueError(f"unsupported timeframes {bad}; expected some of {list(TF_MINUTES)}")
        return sorted(dict.fromkeys(tfs), key=lambda tf: TF_MINUTES[tf])


@router.post("/poc-average")
def poc_average(req: PocAverageRequest):
    spec = get_contract_spec(req.symbol)
    df = _load_bars(req, _source_timeframe(req.timeframes), spec)
    df = _apply_session(df, req.session_start, req.session_end)
    anchor = bar_anchor(req.symbol)
    panes = {}
    for tf in req.timeframes:
        # The pane Market Grid would build -- see MultiReplaySession._build_pane.
        bars = resample_ohlcv(df, tf, anchor, with_vwap_price=True)
        panes[tf] = bars[["high", "low", "volume"]] if "volume" in bars else bars[["high", "low"]].assign(volume=0.0)
    moments = [pd.Timestamp(m) for m in req.moments]
    return {
        "timeframes": req.timeframes,
        "moments": poc_average_at(panes, moments, bins=req.bins, value_area=req.value_area),
    }
