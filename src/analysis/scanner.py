"""The futures scanner (upgrade plan, Feature 7): conditions on each symbol's newest bar.

Values come from the same calls the chart makes (api/serializers.price_data_to_response),
so a scan's RSI is the chart's RSI on the same bar. Conditions:

  indicator      rsi2 / rsi13 / stochrsi (K) / mfi  above | below | crosses_above | crosses_below  value
  change_pct     % change of the close over the last N bars, above | below value
  volume_vs_avg  the bar's volume / Volume Avg (20), above | below value
  breakout       the close beyond the high (or low) of the N bars before it; value = that level
  vwap           the close above_upper | above_vwap | below_vwap | below_lower (session VWAP, 2 sigma)

They combine with "all" or "any". A condition that cannot be judged (too few bars, no
volume) is not met and says so with a null value, rather than counting as a match.
The newest bar is used as the data source serves it: during market hours that bar is
still forming, as on any live scanner.
"""
from __future__ import annotations

from datetime import time

import numpy as np
import pandas as pd

from src.analysis.indicators import calc_mfi, calc_rsi, calc_stochrsi, calc_volume_avg, calc_vwap_bands

INDICATORS = ("rsi2", "rsi13", "stochrsi", "mfi")


def series_for(df: pd.DataFrame, session_start: time | None = None) -> dict[str, pd.Series]:
    vol = df["volume"] if "volume" in df else None
    vwap, up, lo = calc_vwap_bands(df["high"], df["low"], df["close"], vol, session_start=session_start)
    return {
        "rsi2": calc_rsi(df["close"], 2), "rsi13": calc_rsi(df["close"], 13),
        "stochrsi": calc_stochrsi(df["close"])[0], "mfi": calc_mfi(df["high"], df["low"], df["close"], vol),
        "vwap": vwap, "vwap_upper": up, "vwap_lower": lo,
        "volume_avg": calc_volume_avg(vol, 20) if vol is not None else pd.Series(np.nan, index=df.index),
    }


def _num(x) -> float | None:
    return None if x is None or pd.isna(x) else float(x)


def _cmp(v: float | None, op: str, level: float) -> bool:
    return bool(v is not None and (v > level if op == "above" else v < level))


def _one(df: pd.DataFrame, s: dict, c: dict) -> dict:
    kind, close = c["kind"], df["close"]
    if kind == "indicator":
        cur = _num(s[c["name"]].iloc[-1])
        prev = _num(s[c["name"]].iloc[-2]) if len(df) > 1 else None
        op, lv = c["op"], c["value"]
        if op == "crosses_above":
            met = cur is not None and prev is not None and prev <= lv < cur
        elif op == "crosses_below":
            met = cur is not None and prev is not None and prev >= lv > cur
        else:
            met = _cmp(cur, op, lv)
        return {"label": f"{c['name'].upper()} {op.replace('_', ' ')} {lv:g}", "value": cur, "met": bool(met)}
    if kind == "change_pct":
        n = c["bars"]
        v = _num((close.iloc[-1] / close.iloc[-1 - n] - 1) * 100) if len(df) > n else None
        return {"label": f"Change over {n} bars {c['op']} {c['value']:g}%", "value": v, "met": _cmp(v, c["op"], c["value"])}
    if kind == "volume_vs_avg":
        avg = _num(s["volume_avg"].iloc[-1])
        v = _num(df["volume"].iloc[-1] / avg) if avg else None
        return {"label": f"Volume / Volume Avg {c['op']} {c['value']:g}x", "value": v, "met": _cmp(v, c["op"], c["value"])}
    if kind == "breakout":
        n, high = c["bars"], c["direction"] == "high"
        if len(df) <= n:
            return {"label": f"Breakout of the {n}-bar {c['direction']}", "value": None, "met": False}
        ref = df["high"].iloc[-1 - n:-1].max() if high else df["low"].iloc[-1 - n:-1].min()
        last = float(close.iloc[-1])
        # The value is the level being broken; the row's Last column already shows the close.
        return {"label": f"Close {'above' if high else 'below'} the {n}-bar {c['direction']}",
                "value": float(ref), "met": bool(last > ref if high else last < ref)}
    if kind == "vwap":
        last = float(close.iloc[-1])
        lv = {"above_upper": s["vwap_upper"], "above_vwap": s["vwap"],
              "below_vwap": s["vwap"], "below_lower": s["vwap_lower"]}[c["position"]].iloc[-1]
        level = _num(lv)
        met = bool(level is not None and (last > level if c["position"].startswith("above") else last < level))
        return {"label": f"Close {c['position'].replace('_', ' ')}", "value": level, "met": met}
    raise ValueError(f"unknown condition kind {kind!r}")


def evaluate(df: pd.DataFrame, conditions: list[dict], combine: str = "all",
             session_start: time | None = None) -> dict:
    s = series_for(df, session_start)
    values = [_one(df, s, c) for c in conditions]
    met = [v["met"] for v in values]
    return {"matched": bool(met) and (all(met) if combine == "all" else any(met)), "values": values}
