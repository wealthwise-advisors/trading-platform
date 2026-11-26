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


#: Each timeframe's Volume Profile window on the Market Grid, in calendar days
#: (web/src/lib/chartSetup.ts SPECIFIED). A timeframe without one profiles everything loaded.
GRID_PROFILE_DAYS = {"1m": 2, "5m": 2, "10m": 3, "15m": 4, "20m": 5, "30m": 15, "45m": 20,
                     "1h": 25, "2h": 180, "4h": 180}


def _grid_profile(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """VAHigh / POC / VALow per candle, as the Market Grid's tape shows them: the profile
    of the candles up to and including this one, over the timeframe's own days
    (web/src/lib/profileWindow.ts), 48 rows, 70 % value area."""
    out = pd.DataFrame(index=df.index, columns=["VAHigh", "POC", "VALow"], dtype=float)
    if "volume" not in df or df.empty:
        return out
    days = GRID_PROFILE_DAYS.get(timeframe)
    dates = df.index.normalize()
    rows = []
    for i in range(len(df)):
        start = 0 if days is None else int(dates.searchsorted(dates[i] - pd.Timedelta(days=days - 1)))
        win = df.iloc[start:i + 1]
        vp = calc_volume_profile(win["high"], win["low"], win["close"], win["volume"]) if len(win) >= 2 else {}
        rows.append([vp.get("vah"), vp.get("poc"), vp.get("val")])
    out[:] = np.array(rows, dtype=float)
    return out


def _price_zone(close: float, vah: float, val: float, vwap: float) -> str | None:
    """web/src/lib/structureZones.ts priceZone: sir's four zones."""
    if any(pd.isna(x) for x in (close, vah, val, vwap)):
        return None
    if close >= vah:
        return "Buy / Reversal"
    if close <= val:
        return "Short / Reversal"
    return "Breakout" if close >= vwap else "No trade"


def _swing_levels(df: pd.DataFrame, zz10: list[dict]) -> dict[int, tuple[float, float, float, float]]:
    """Sir's swing levels for every 10 Leg swing (web/src/lib/swingStrength.ts
    swingBreakeven), over the same stretch the chart's swing box and the grid use
    (current_swing_stretch): first point to last point, or from the previous swing's
    last point when the swing has only one. Both end candles count.
    Returns swing -> (breakeven, equilibrium, buyer control, buyer control %)."""
    pct, _, _ = calc_volume_split(df["high"], df["low"], df["close"], df["volume"])
    out, prev_last = {}, None
    for swing in sorted({p["swing"] for p in zz10}):
        pts = [p for p in zz10 if p["swing"] == swing]
        start = pts[0]["t"] if len(pts) > 1 or prev_last is None else prev_last
        end = pts[-1]["t"] if len(pts) > 1 or prev_last is not None else df.index[-1]
        s = df.loc[pd.Timestamp(start):pd.Timestamp(end)]
        vol = s["volume"].fillna(0)
        if len(s) and vol.sum() > 0:
            buyers = float((vol * pct.loc[s.index]).sum())
            out[swing] = (float(((s["high"] + s["low"] + s["close"]) / 3 * vol).sum() / vol.sum()),
                          float((s["high"].max() + s["low"].min()) / 2), buyers, buyers / float(vol.sum()) * 100)
        prev_last = pts[-1]["t"]
    return out


def _with_studies(df: pd.DataFrame, session_start: time_type | None,
                  dev_3: float, dev_10: float, timeframe: str = "") -> tuple[pd.DataFrame, pd.DataFrame]:
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
    out["RSI(2)"], out["FullK"], out["FullD"] = s["rsi2"], s["stochrsi_k"], s["stochrsi_d"]
    out["RSI(13)"], out["MFI"] = s["rsi13"], s["mfi"]
    # Sir's order-flow studies (2026-11-26): the chart's Volume Delta and CVD rows.
    out["Volume Delta"], out["Delta %"], out["CVD"] = s["delta"], s["delta_pct"], s["cvd"]
    # The Market Grid's levels per candle (sir, 2026-11-26: "where is POC match, VAH, VAL").
    # A Match column is the level's whole number, which the grid groups and colours by.
    prof = _grid_profile(df, timeframe)
    out["Price Zone"] = [_price_zone(c, h, lo, w) for c, h, lo, w in
                         zip(df["close"], prof["VAHigh"], prof["VALow"], s["vwap"])]
    for col, match in (("VAHigh", "VAH Match"), ("POC", "POC Match"), ("VALow", "VAL Match")):
        out[col], out[match] = prof[col], np.trunc(prof[col])
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

    # Every candle belongs to a swing; each carries its swing's levels (Market Grid / swing box).
    swing_no = pd.Series(np.nan, index=out.index)
    for p in zz["zigzag_10"]:
        swing_no[pd.Timestamp(p["t"])] = p["swing"]
    swing_no = swing_no.ffill()
    out["Swing"] = [swing_name(int(n)) if pd.notna(n) else None for n in swing_no]
    levels = _swing_levels(df, zz["zigzag_10"]) if "volume" in df and zz["zigzag_10"] else {}
    cols = ["Volume Breakeven", "50% Equilibrium", "Buyer Control", "Buyer Control %"]
    vals = [levels.get(int(n)) if pd.notna(n) else None for n in swing_no]
    for k, col in enumerate(cols):
        out[col] = [round(v[k], 2) if v else None for v in vals]
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
              ("EMAs", ["EMA 9", "EMA 20", "EMA 50"]),
              ("VWAP and bands 0.5 to 2", ["VWAP"] + bands[:8]),
              ("VWAP bands 2.5 to 5", bands[8:]),
              ("Oscillators", ["RSI(2)", "FullK", "FullD", "RSI(13)", "MFI"]),
              ("Volume Delta and CVD", ["Volume Delta", "Delta %", "CVD"]),
              ("Price Zone, VAH, POC, VAL", ["Price Zone", "VAHigh", "VAH Match", "POC", "POC Match",
                                             "VALow", "VAL Match"]),
              ("Swing count", ["Swing", "10 Leg", "10 Leg Tag", "3 Leg", "3 Leg Tag"]),
              ("Swing levels", ["Swing", "Volume Breakeven", "50% Equilibrium", "Buyer Control",
                                "Buyer Control %"])]
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

    table, swings = _with_studies(df, session_start, dev_3, dev_10, timeframe)
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
