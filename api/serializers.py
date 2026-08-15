"""
Plain functions converting BacktestResults / pandas objects into the JSON-
ready shapes defined in api/schemas/backtest.py. src/backtesting/results.py
is not touched -- all conversion logic lives here.
"""

import math
import numpy as np
from datetime import time as time_type
import pandas as pd

from src.backtesting.results import BacktestResults, Trade
from src.backtesting.replay_engine import FrameState
from src.analysis.indicators import (
    calc_rsi, calc_stoch, calc_vwap_bands, calc_volume_profile,
)
from src.analysis.zigzag import calc_zigzag, assign_swing_labels, calc_nested_zigzag


def _safe(x):
    """NaN/inf -> None so it survives JSON serialization.

    Also narrows numpy scalars to Python types. ExternalCSVProvider reads
    price columns as float32 to keep large archives in memory, and FastAPI's
    jsonable_encoder cannot serialize numpy.float32 -- so every /price-data
    and /candlestick-patterns call for a CSV-backed backtest returned 500
    with "'numpy.float32' object is not iterable".

    Synthetic data never hit this because numpy.float64 subclasses float and
    encodes fine; float32 does not subclass it, so it also slipped past the
    isnan/isinf check below and NaNs would have leaked through as well.
    """
    if x is None:
        return None
    if isinstance(x, np.generic):
        x = x.item()
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return x


def results_to_summary(backtest_id: str, results: BacktestResults, data_source: str,
                       session_start, session_end) -> dict:
    r = results
    return {
        "backtest_id": backtest_id,
        "symbol": r.symbol,
        "strategy_name": r.strategy_name,
        "timeframe": r.timeframe,
        "start_date": r.start_date.date(),
        "end_date": r.end_date.date(),
        "session_start": session_start,
        "session_end": session_end,
        "data_source": data_source,
        "initial_capital": r.initial_capital,
        "final_capital": r.final_capital,
        "total_pnl": r.total_pnl,
        "total_return_pct": r.total_return_pct,
        "sharpe_ratio": _safe(r.sharpe_ratio) or 0.0,
        "sortino_ratio": _safe(r.sortino_ratio) or 0.0,
        "max_drawdown_pct": r.max_drawdown_pct,
        "win_rate": r.win_rate,
        "profit_factor": _safe(r.profit_factor) or 0.0,
        "avg_win": r.avg_win,
        "avg_loss": r.avg_loss,
        "total_trades": r.total_trades,
        "winning_trades": r.winning_trades,
        "losing_trades": r.losing_trades,
        "avg_trade_duration_min": r.avg_trade_duration_min,
        "data_points": len(r.price_data),
    }


def trades_to_records(results: BacktestResults, quality_by_index: dict | None = None) -> list[dict]:
    quality_by_index = quality_by_index or {}
    out = []
    for i, t in enumerate(results.trades):
        q = quality_by_index.get(i)
        out.append({
            "entry_time": t.entry_time.isoformat(),
            "exit_time": t.exit_time.isoformat() if t.exit_time else None,
            "symbol": t.symbol,
            "direction": t.direction,
            "qty": t.quantity,
            "entry_price": _safe(t.entry_price),
            "exit_price": _safe(t.exit_price),
            "pnl": _safe(t.pnl),
            "commission": _safe(t.commission),
            "duration_min": _safe(t.duration_minutes),
            "strategy": t.strategy,
            "quality_score": _safe(q.score) if q else None,
            "quality_grade": q.grade if q else None,
        })
    return out


def price_data_to_response(df: pd.DataFrame, session_start: time_type | None = None) -> dict:
    bars = [
        {
            "t": ts.isoformat(),
            "o": _safe(row["open"]), "h": _safe(row["high"]),
            "l": _safe(row["low"]), "c": _safe(row["close"]),
            "v": _safe(row.get("volume")),
        }
        for ts, row in df.iterrows()
    ]

    ema9 = df["close"].ewm(span=9, adjust=False).mean()
    ema21 = df["close"].ewm(span=21, adjust=False).mean()
    rsi2 = calc_rsi(df["close"], 2)
    rsi13 = calc_rsi(df["close"], 13)
    stoch_k, stoch_d = calc_stoch(df["high"], df["low"], df["close"])
    # Session VWAP ±2σ. Comes back all-NaN when the dataset carries no volume
    # column, which serialises to nulls -- the chart then simply has nothing to
    # draw rather than plotting a fake line.
    # session_start anchors the daily reset. Without it an overnight session
    # (18:00-17:00) resets at midnight, i.e. mid-session -- see calc_vwap_bands.
    vwap, vwap_u, vwap_l = calc_vwap_bands(
        df["high"], df["low"], df["close"], df["volume"] if "volume" in df else None,
        session_start=session_start,
    )

    def series_to_list(s: pd.Series) -> list:
        return [_safe(float(v)) if pd.notna(v) else None for v in s]

    indicators = {
        "ema9": series_to_list(ema9),
        "ema21": series_to_list(ema21),
        "rsi2": series_to_list(rsi2),
        "rsi13": series_to_list(rsi13),
        "stoch_k": series_to_list(stoch_k),
        "stoch_d": series_to_list(stoch_d),
        "vwap": series_to_list(vwap),
        "vwap_upper": series_to_list(vwap_u),
        "vwap_lower": series_to_list(vwap_l),
    }
    # Volume Profile is price-indexed, not bar-indexed, so it travels beside
    # the per-bar series rather than inside them.
    volume_profile = calc_volume_profile(
        df["high"], df["low"], df["close"], df["volume"] if "volume" in df else None,
    )
    return {"bars": bars, "indicators": indicators, "volume_profile": volume_profile}


def equity_curve_to_records(results: BacktestResults) -> list[dict]:
    eq = results.equity_curve
    if eq.empty:
        return []
    drawdown = (eq - eq.cummax()) / eq.cummax() * 100
    return [
        {"t": ts.isoformat(), "equity": float(v), "drawdown_pct": _safe(float(drawdown[ts])) or 0.0}
        for ts, v in eq.items()
    ]


def zigzag_to_records(df: pd.DataFrame, dev_3: float, dev_10: float) -> dict:
    """10-leg (major) and 3-leg (minor) zigzags. The 10-leg zigzag is grouped
    into swings via assign_swing_labels()'s fixed-channel procedure (decimal
    labels: 1.0, 1.1, 2.0...). The 3-leg zigzag is NOT computed independently
    over the whole series -- calc_nested_zigzag() runs it separately within
    each 10-leg swing's own bar window, so every minor pivot's `swing` field
    is its true parent major swing, and its `label` (a letter: A, B, C...)
    always resets at the start of a new parent swing. This makes containment
    a property of the data itself, not a client-side rendering heuristic."""
    zz10 = calc_zigzag(df["high"], df["low"], df["close"], deviation=dev_10, legs=10)
    zz10 = assign_swing_labels(zz10) if not zz10.empty else zz10
    zz3 = calc_nested_zigzag(df["high"], df["low"], df["close"], zz10, deviation=dev_3, legs=3)

    def to_records(zz: pd.DataFrame) -> list[dict]:
        if zz.empty:
            return []
        return [
            {
                "t": ts.isoformat(), "price": float(row["price"]), "type": row["type"],
                "swing": int(row["swing"]), "sub": int(row["sub"]), "label": row["label"],
            }
            for ts, row in zz.iterrows()
        ]

    return {"zigzag_10": to_records(zz10), "zigzag_3": to_records(zz3)}


def elliott_wave_to_records(
    df: pd.DataFrame,
    theta_base: float,
    ratio: float,
    scales: int,
) -> dict:
    """Run the Elliott Wave engine and flatten it for the API.

    Deliberately faithful to what the engine reports, including its gaps:

    * every wave carries its lifecycle ``state`` and ``blocked_by``, so a
      client can distinguish a confirmed structure from one whose acceptance
      depends on an unresolved Open Question (FE-3.1);
    * ``blocked_rules`` and ``notes`` are passed through verbatim, so a partial
      analysis can never be rendered as if it were complete (FE-3.2);
    * no confidence/score field is produced or derivable (FR-7.4).
    """
    from src.analysis.elliott_wave import EngineConfig, run_analysis

    cfg = EngineConfig(theta_base=theta_base, ratio=ratio, scales=scales)
    res = run_analysis(df, cfg)

    pivots = [
        {
            "index": p.index,
            "confirm_index": p.confirm_index,
            "t": p.timestamp.isoformat() if hasattr(p.timestamp, "isoformat") else str(p.timestamp),
            "price": _safe(p.price),
            "kind": p.kind.value,
            "scale": p.scale,
        }
        for p in res.pivots
    ]

    waves = [
        {
            "id": w.id,
            "scale": w.scale,
            "state": w.state.value,
            "label": w.label,
            "structure_type": w.structure_type.value if w.structure_type else None,
            "direction": w.direction.value if w.direction else None,
            "start_t": w.start_pivot.timestamp.isoformat()
            if hasattr(w.start_pivot.timestamp, "isoformat") else str(w.start_pivot.timestamp),
            "start_price": _safe(w.start_pivot.price),
            "end_t": w.end_pivot.timestamp.isoformat()
            if hasattr(w.end_pivot.timestamp, "isoformat") else str(w.end_pivot.timestamp),
            "end_price": _safe(w.end_pivot.price),
            "parent_id": w.parent_id,
            "child_ids": list(w.child_ids),
            "measurements": {k: _safe(v) for k, v in w.measurements.items()},
            "blocked_by": list(w.blocked_by),
        }
        for w in res.waves
    ]

    structures = [w for w in waves if w["structure_type"] is not None]
    by_type: dict[str, int] = {}
    by_state: dict[str, int] = {}
    for w in structures:
        by_type[w["structure_type"]] = by_type.get(w["structure_type"], 0) + 1
        by_state[w["state"]] = by_state.get(w["state"], 0) + 1

    return {
        "engine_version": res.engine_version,
        "config": res.config,
        "pivots": pivots,
        "waves": waves,
        "blocked_rules": res.blocked_rules,
        "notes": res.notes,
        "counts": {
            "pivots": len(pivots),
            "waves": len(waves),
            "structures": len(structures),
            "structures_by_type": by_type,
            "structures_by_state": by_state,
            "blocked_rule_ids": sum(len(e["rules"]) for e in res.blocked_rules),
        },
    }


def win_loss(results: BacktestResults) -> dict:
    return {
        "wins": results.winning_trades,
        "losses": results.losing_trades,
        "win_rate": results.win_rate,
    }


def monthly_returns(results: BacktestResults) -> dict:
    """Year x month grid of % return, matching ui/components/charts.py's
    monthly_returns_heatmap() calculation (resample equity to month-end,
    pct_change)."""
    eq = results.equity_curve
    if eq.empty:
        return {"years": [], "months": [], "values": []}

    monthly_eq = eq.resample("ME").last()
    monthly_ret = monthly_eq.pct_change() * 100
    monthly_ret.index = monthly_ret.index.to_period("M")

    years = sorted(set(p.year for p in monthly_ret.index))
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    values = []
    for year in years:
        row = []
        for m in range(1, 13):
            period = pd.Period(year=year, month=m, freq="M")
            val = monthly_ret.get(period, None)
            if val is None or pd.isna(val):
                row.append(None)
            else:
                row.append(round(float(val), 2))
        values.append(row)

    return {"years": [str(y) for y in years], "months": month_names, "values": values}


def _trade_to_dict(t: Trade) -> dict:
    return {
        "direction": t.direction,
        "qty": t.quantity,
        "entry_time": t.entry_time.isoformat(),
        "entry_price": t.entry_price,
        "exit_time": t.exit_time.isoformat() if t.exit_time else None,
        "exit_price": t.exit_price,
        "pnl": _safe(t.pnl) or 0.0,
        "commission": t.commission,
        "duration_min": t.duration_minutes,
    }


def frame_to_dict(frame: FrameState) -> dict:
    """One WebSocket message per replayed bar — mirrors ui/live_app.py's
    FrameState rendering (bar, signal, running trade/equity state)."""
    b = frame.bar
    last_equity = frame.equity[-1] if frame.equity else None
    return {
        "bar": {
            "t": b.timestamp.isoformat(), "o": b.open, "h": b.high,
            "l": b.low, "c": b.close, "v": _safe(b.volume),
        },
        "signal": {
            "type": frame.signal.signal_type.value,
            "reason": frame.signal.reason,
        } if frame.signal else None,
        "position": frame.position,
        "portfolio_value": _safe(frame.portfolio_value) or 0.0,
        "equity_point": {"t": last_equity[0].isoformat(), "equity": _safe(last_equity[1]) or 0.0}
        if last_equity else None,
        "completed_trades": [_trade_to_dict(t) for t in frame.completed_trades],
        "open_trade": _trade_to_dict(frame.open_trade) if frame.open_trade else None,
        "bars_processed": frame.bars_processed,
        "total_bars": frame.total_bars,
        # Session VWAP at 2 sigma. The client recovers sigma as
        # (upper - vwap) / 2 and re-scales to whatever deviation the user picks,
        # so changing the setting needs no round trip.
        "vwap": _safe(frame.vwap),
        "vwap_upper": _safe(frame.vwap_upper),
        "vwap_lower": _safe(frame.vwap_lower),
    }
