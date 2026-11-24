"""Data export -- pick a symbol, date range, and data source, get back a
CSV/Excel/PDF/Word file of the bars with every study the chart draws, its swing
points and its Volume Profile levels. Independent of running a backtest; reuses
the same provider-selection logic as POST /api/backtests.

Every number comes from the function the chart's own number comes from
(api/serializers.py, src/analysis/*), and every column is named the way the
chart's Legend names it, so a value can be found on the chart by its name.
"""

from datetime import date, datetime, time as time_type, timedelta

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from api import serializers
from api.deps import SYMBOL_PATTERN, TIMEFRAME_PATTERN, ZONES, get_contract_spec
from api.export import formats
from api.export.data_workbook import ExportMeta, workbook_bytes
from api.routers.backtests import _build_provider
from src.analysis.indicators import calc_volume_avg, calc_volume_profile, calc_volume_split
from src.analysis.swing_count import swing_name
from src.data.resample import is_daily_or_longer

router = APIRouter(prefix="/data", tags=["data-export"])

_FORMATS = {"csv", "xlsx", "pdf", "docx"}

#: The VWAP band levels the chart offers (web/src/lib/vwapLevels.ts ALL_VWAP_LEVELS).
VWAP_LEVELS = (0.5, 1, 1.5, 2, 2.5, 3, 4, 5)


def band_name(side: str, level: float) -> str:
    """The chart Legend's name for a band: "VWAP Upper +2.0σ"."""
    return f"VWAP {side} {'+' if side == 'Upper' else '-'}{level:.1f}σ"


def _with_studies(df: pd.DataFrame, session_start: time_type | None,
                  dev_3: float, dev_10: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The bars plus every study the chart draws, and the chart's swing points (Eastern times)."""
    ind = serializers.price_data_to_response(df, session_start)["indicators"]
    s = {k: pd.Series([np.nan if v is None else v for v in vals], index=df.index, dtype=float)
         for k, vals in ind.items()}
    out = pd.DataFrame({"Open": df["open"], "High": df["high"], "Low": df["low"], "Close": df["close"]},
                       index=df.index)
    if "volume" in df:
        out["Volume"] = df["volume"]
        out["VolumeAvg (20)"] = calc_volume_avg(df["volume"], 20)
        pct, buyers, sellers = calc_volume_split(df["high"], df["low"], df["close"], df["volume"])
        out["Buyers %"], out["Buyers"], out["Sellers"] = pct * 100, buyers, sellers
    # EMA 21 is not here: it was taken off the chart on request (2026-10-28).
    out["EMA 9"], out["EMA 20"], out["EMA 50"], out["VWAP"] = s["ema9"], s["ema20"], s["ema50"], s["vwap"]
    # The chart rebuilds each band from VWAP and its 2-sigma band (CandlestickChart.tsx atDev).
    sigma = (s["vwap_upper"] - s["vwap"]) / 2
    for lv in VWAP_LEVELS:
        out[band_name("Upper", lv)] = s["vwap"] + lv * sigma
        out[band_name("Lower", lv)] = s["vwap"] - lv * sigma
    out["BB 20 2 basis"], out["BB Upper"], out["BB Lower"] = s["bb_middle"], s["bb_upper"], s["bb_lower"]
    out["RSI(2)"], out["FullK"], out["FullD"] = s["rsi2"], s["stochrsi_k"], s["stochrsi_d"]
    out["RSI(13)"], out["MFI"] = s["rsi13"], s["mfi"]
    out = out.round(2)

    zz = serializers.zigzag_to_records(df, dev_3=dev_3, dev_10=dev_10)
    rows = []
    for col in ("Swing", "10 Leg", "10 Leg Tag", "3 Leg", "3 Leg Tag"):
        out[col] = None
    for level, col in (("zigzag_10", "10 Leg"), ("zigzag_3", "3 Leg")):
        for p in zz[level]:
            ts = pd.Timestamp(p["t"])
            out.at[ts, col], out.at[ts, f"{col} Tag"] = p["label"], p["structure"]
            if level == "zigzag_10":
                out.at[ts, "Swing"] = swing_name(p["swing"])
            rows.append({"Time": ts, "Swing": swing_name(p["swing"]), "Level": col, "Number": p["label"],
                         "High/Low": "High" if p["type"] == "H" else "Low", "Price": p["price"],
                         "Tag": p["structure"]})
    swings = pd.DataFrame(rows, columns=["Time", "Swing", "Level", "Number", "High/Low", "Price", "Tag"])
    return out, swings.sort_values(["Time", "Level"]).reset_index(drop=True)


def _levels(df: pd.DataFrame) -> pd.DataFrame:
    """Volume Profile levels: the whole range (the chart's default profile) and each day.

    calc_volume_profile is the algorithm web/src/lib/volumeProfile.ts mirrors, 48 rows,
    70% value area -- the chart's defaults. Days are grouped by the bar's own date, as
    the chart's periodKey does.
    """
    cols = ["Profile", "From", "To", "POC", "VAHigh", "VALow", "ProfileHigh", "ProfileLow"]
    if "volume" not in df:
        return pd.DataFrame(columns=cols)
    groups = [("Whole range", df)] + [(f"Day {d:%a %d %b}", g) for d, g in df.groupby(df.index.date)]
    rows = []
    for name, g in groups:
        vp = calc_volume_profile(g["high"], g["low"], g["close"], g["volume"])
        if not vp.get("prices"):
            continue
        half = vp["bin_size"] / 2
        rows.append([name, g.index[0], g.index[-1], vp["poc"], vp["vah"], vp["val"],
                     vp["prices"][-1] + half, vp["prices"][0] - half])
    out = pd.DataFrame(rows, columns=cols)
    out[cols[3:]] = out[cols[3:]].round(2)
    return out


def _sections(table: pd.DataFrame, swings: pd.DataFrame, levels: pd.DataFrame,
              time_col: str) -> list[tuple[str, pd.DataFrame]]:
    """PDF and Word pages are too narrow for one 50-column table: one table per group."""
    bands = [band_name(side, lv) for lv in VWAP_LEVELS for side in ("Upper", "Lower")]
    groups = [("Price and Volume", ["Open", "High", "Low", "Close", "Volume", "VolumeAvg (20)",
                                    "Buyers %", "Buyers", "Sellers"]),
              ("EMAs and Bollinger Bands", ["EMA 9", "EMA 20", "EMA 50", "BB 20 2 basis", "BB Upper", "BB Lower"]),
              ("VWAP and bands 0.5 to 2", ["VWAP"] + bands[:8]),
              ("VWAP bands 2.5 to 5", bands[8:]),
              ("Oscillators", ["RSI(2)", "FullK", "FullD", "RSI(13)", "MFI"]),
              ("Swing count", ["Swing", "10 Leg", "10 Leg Tag", "3 Leg", "3 Leg Tag"])]
    t = table.rename_axis(time_col)
    out = [(name, t[[c for c in cols if c in t]]) for name, cols in groups]
    return out + [("Swing Points", swings.set_index("Time").rename_axis(time_col)),
                  ("Volume Profile levels", levels.set_index("Profile"))]


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
    # The chart's swing settings, as fractions (0.0005 = 0.05%); the defaults are the chart's.
    dev_3: float = Query(0.0005, gt=0, le=0.5),
    dev_10: float = Query(0.0010, gt=0, le=0.5),
    # The sidebar's "Times in" zone, minutes added to Eastern. Only the printed times move.
    tz_offset: int = Query(0),
):
    if format not in _FORMATS:
        raise HTTPException(400, f"format must be one of {sorted(_FORMATS)}")
    if tz_offset not in ZONES:
        raise HTTPException(400, f"tz_offset must be one of {sorted(ZONES)}")

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
    # Not for daily or weekly bars, which are whole sessions -- see
    # BacktestEngine.run().
    if not df.empty and (session_start or session_end) and not is_daily_or_longer(timeframe):
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

    table, swings = _with_studies(df, session_start, dev_3, dev_10)
    levels = _levels(df)
    # Everything is worked out on Eastern bars; only the printed clock moves to the chosen zone.
    zone, shift = ZONES[tz_offset], timedelta(minutes=tz_offset)
    time_col = f"Time ({zone})"
    table.index = (table.index + shift).rename(time_col)
    swings["Time"] = swings["Time"] + shift
    levels["From"], levels["To"] = levels["From"] + shift, levels["To"] + shift

    session = (f"{session_start:%H:%M}–{session_end:%H:%M} ET" if session_start and session_end
               else "24 hours")
    meta = ExportMeta(symbol=symbol, timeframe=timeframe, start=start, end=end, source=data_source,
                      zone=zone, session=session, dev_3=dev_3, dev_10=dev_10)
    title = f"{symbol} {timeframe} — {start:%d %b %Y} to {end:%d %b %Y}"
    subtitle = f"Source: {data_source} · Times in {zone} · Session {session}"
    filename = f"{symbol}_{timeframe}_{start}_{end}.{format}"

    if format == "csv":
        content = formats.csv_bytes(table)
    elif format == "xlsx":
        content = workbook_bytes(table, swings, levels, meta, VWAP_LEVELS)
    elif format == "pdf":
        content = formats.pdf_bytes(title, _sections(table, swings, levels, time_col), subtitle=subtitle)
    else:
        content = formats.docx_bytes(title, _sections(table, swings, levels, time_col), subtitle=subtitle)

    return Response(
        content=content, media_type=formats.media_type_for(format),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
