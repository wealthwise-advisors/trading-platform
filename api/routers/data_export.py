"""Raw OHLC data export -- pick a symbol, date range, and data source, get
back a CSV/Excel/PDF/Word file. Independent of running a backtest; reuses
the same provider-selection logic as POST /api/backtests."""

from datetime import date, datetime, time as time_type

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from api.deps import SYMBOL_PATTERN, TIMEFRAME_PATTERN, get_contract_spec
from api.export import formats
from api.routers.backtests import _build_provider

router = APIRouter(prefix="/data", tags=["data-export"])

_FORMATS = {"csv", "xlsx", "pdf", "docx"}


@router.get("/export")
def export_data(
    # Both become part of a filename on disk and of the download's
    # Content-Disposition; see api/deps.py's SYMBOL_PATTERN.
    symbol: str = Query(..., pattern=SYMBOL_PATTERN),
    timeframe: str = Query("1h", pattern=TIMEFRAME_PATTERN),
    start: date = Query(...),
    end: date = Query(...),
    data_source: str = Query("synthetic"),
    format: str = Query("csv", pattern=r"^(csv|xlsx|pdf|docx)$"),
    session_start: time_type | None = Query(None),
    session_end: time_type | None = Query(None),
):
    if format not in _FORMATS:
        raise HTTPException(400, f"format must be one of {sorted(_FORMATS)}")

    spec = get_contract_spec(symbol)
    # The session has to reach the provider, not just the filter below: bars are
    # AGGREGATED on the session grid, so exporting 45m without it returns bars
    # on a midnight grid that no other page in the app agrees with.
    provider = _build_provider(data_source, symbol, timeframe, start, end, spec,
                               session_start=session_start)

    start_dt = datetime.combine(start, time_type(0, 0))
    end_dt = datetime.combine(end, time_type(23, 59))
    try:
        df = provider.load(symbol, start_dt, end_dt, timeframe=timeframe)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc))

    # Same overnight-aware session filter as BacktestEngine.run() -- an
    # overnight window (session_end < session_start, e.g. 16:00-15:00 for a
    # near-24h futures session) wraps past midnight, so the valid window is
    # time >= start OR time <= end there, not AND.
    if not df.empty and (session_start or session_end):
        bar_times = df.index.time
        if session_start and session_end:
            if session_start <= session_end:
                mask = (bar_times >= session_start) & (bar_times <= session_end)
            else:
                mask = (bar_times >= session_start) | (bar_times <= session_end)
        elif session_start:
            mask = bar_times >= session_start
        else:
            mask = bar_times <= session_end
        df = df[mask]

    if df.empty:
        raise HTTPException(400, f"No {symbol} data returned for {start} → {end} "
                                 f"from the {data_source} source.")

    title = f"{symbol} {timeframe} OHLC — {start} to {end}"
    subtitle = f"Source: {data_source}"
    filename = f"{symbol}_{timeframe}_{start}_{end}.{format}"

    if format == "csv":
        content = formats.csv_bytes(df)
    elif format == "xlsx":
        content = formats.excel_bytes({f"{symbol} {timeframe}": df})
    elif format == "pdf":
        content = formats.pdf_bytes(title, [("OHLC Data", df)], subtitle=subtitle)
    else:
        content = formats.docx_bytes(title, [("OHLC Data", df)], subtitle=subtitle)

    return Response(
        content=content, media_type=formats.media_type_for(format),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
