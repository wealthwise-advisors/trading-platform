"""POST /api/scan -- the futures scanner (upgrade plan, Feature 7). See src/analysis/scanner.py.

One data request per symbol, at most MAX_SYMBOLS a scan: within Schwab's request limits
by construction rather than by counting. A symbol that cannot be loaded comes back as a
row with its reason, so one bad symbol never fails the scan. Matches are listed first.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Annotated, Literal, Union

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.auth import PROTECTED
from api.deps import SYMBOL_PATTERN, TIMEFRAME_PATTERN, get_contract_spec
from src.analysis import scanner
from src.data.resample import is_daily_or_longer

router = APIRouter(prefix="/scan", tags=["scan"])
MAX_SYMBOLS = 25


class Indicator(BaseModel):
    kind: Literal["indicator"]
    name: Literal["rsi2", "rsi13", "stochrsi", "mfi"]
    op: Literal["above", "below", "crosses_above", "crosses_below"]
    value: float


class ChangePct(BaseModel):
    kind: Literal["change_pct"]
    bars: int = Field(ge=1, le=500)
    op: Literal["above", "below"]
    value: float


class VolumeVsAvg(BaseModel):
    kind: Literal["volume_vs_avg"]
    op: Literal["above", "below"]
    value: float = Field(gt=0)


class Breakout(BaseModel):
    kind: Literal["breakout"]
    bars: int = Field(ge=2, le=500)
    direction: Literal["high", "low"]


class Vwap(BaseModel):
    kind: Literal["vwap"]
    position: Literal["above_upper", "above_vwap", "below_vwap", "below_lower"]


Condition = Annotated[Union[Indicator, ChangePct, VolumeVsAvg, Breakout, Vwap], Field(discriminator="kind")]


class ScanRequest(BaseModel):
    data_source: str = "schwab"
    timeframe: str = Field(default="5m", pattern=TIMEFRAME_PATTERN)
    symbols: list[Annotated[str, Field(pattern=SYMBOL_PATTERN)]] = Field(min_length=1, max_length=MAX_SYMBOLS)
    conditions: list[Condition] = Field(default_factory=list, max_length=10)
    combine: Literal["all", "any"] = "all"
    session_start: time | None = None
    session_end: time | None = None
    #: The last day to scan; today by default.
    end_date: date | None = None


def _bars(req: ScanRequest, symbol: str):
    from api.routers import backtests
    from api.routers.replay import _apply_session
    end = req.end_date or date.today()
    start = end - timedelta(days=400 if is_daily_or_longer(req.timeframe) else 5)
    provider = backtests._build_provider(req.data_source, symbol, req.timeframe, start, end,
                                         get_contract_spec(symbol), session_start=req.session_start)
    df = provider.load(symbol, datetime.combine(start, time(0, 0)), datetime.combine(end, time(23, 59)), req.timeframe)
    if req.session_start and req.session_end:
        df = _apply_session(df, req.session_start, req.session_end)
    if df is None or df.empty:
        raise ValueError("no bars in the last few days")
    return df


@router.post("")
def run_scan(req: ScanRequest, user=PROTECTED):
    conds = [c.model_dump() for c in req.conditions]
    rows = []
    for sym in dict.fromkeys(s.upper() for s in req.symbols):
        try:
            df = _bars(req, sym)
            r = scanner.evaluate(df, conds, req.combine, req.session_start)
            rows.append({"symbol": sym, "matched": r["matched"], "values": r["values"], "error": None,
                         "last": float(df["close"].iloc[-1]), "bar_time": df.index[-1].isoformat()})
        except Exception as exc:                    # this symbol only; the scan goes on
            rows.append({"symbol": sym, "matched": False, "values": [], "error": str(exc).splitlines()[0][:200],
                         "last": None, "bar_time": None})
    rows.sort(key=lambda x: (not x["matched"], x["error"] is not None, x["symbol"]))
    return {"timeframe": req.timeframe, "combine": req.combine, "rows": rows,
            "scanned_at": datetime.now().isoformat(timespec="seconds")}
