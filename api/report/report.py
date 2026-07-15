"""
Generate a self-contained HTML backtest report.

The output file:
  - Loads Plotly JS from CDN (works in any browser with internet; ~3 MB saved vs bundled)
  - Contains all charts, metrics, and the full trade log
  - Is a single file you can share via email, Slack, Google Drive
  - Opens in any modern browser — no Python or server required
  - Full zoom/pan support: scroll to zoom, drag to pan, range buttons to jump
"""

from datetime import datetime
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

from src.backtesting.results import BacktestResults
from api.report.charts import (
    _calc_zigzag, _assign_swing_labels, _SWING_COLORS,
    _calc_rsi, _calc_stoch, _swing_letter,
)
from src.analysis.candlestick_patterns import detect_candlestick_patterns
from src.analysis.chart_patterns import find_chart_patterns
from src.analysis.wave_analysis import analyze_degrees, WaveAnalysis
from src.analysis.swing_identification import identify_swings, atr as _wave_atr

import numpy as np

# Same degree configs analyze_degrees() uses internally by default -- kept in
# sync with api/routers/elliott_wave.py's _DEGREES, since WaveAnalysis itself
# doesn't expose the full swings list (only n_swings).
_WAVE_DEGREES = [
    {"name": "primary", "left": 4, "right": 4, "mm_mult": 2.0},
    {"name": "minor", "left": 2, "right": 2, "mm_mult": 1.0},
]

_G      = "#3fb950"
_R      = "#f85149"
_B      = "#58a6ff"
_BG     = "#0d1117"
_GRID   = "#21262d"
_SURFACE = "#161b22"
_TEXT   = "#e6edf3"
_MUTED  = "#8b949e"
_MARKER_BG = "#1e1e2e"  # solid fill so boundary lines don't bleed through circles

# Plotly JS config injected into every chart div.
# scrollZoom is the key setting — without it mouse-wheel does nothing.
_CHART_CFG = {
    "scrollZoom": True,
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
    "toImageButtonOptions": {
        "format": "png",
        "filename": "autotrader_chart",
        "height": 900,
        "width": 1800,
        "scale": 2,
    },
}

# Quick-jump buttons rendered above each time-series chart.
_RANGE_SELECTOR = dict(
    buttons=[
        dict(count=1,  label="1D",  step="day",   stepmode="backward"),
        dict(count=5,  label="5D",  step="day",   stepmode="backward"),
        dict(count=1,  label="1M",  step="month", stepmode="backward"),
        dict(count=3,  label="3M",  step="month", stepmode="backward"),
        dict(count=6,  label="6M",  step="month", stepmode="backward"),
        dict(step="all", label="All"),
    ],
    bgcolor=_BG,
    activecolor="#3d3d5c",
    font=dict(color=_TEXT, size=11),
    x=0, y=1.02, xanchor="left",
)

# Crosshair spike lines shown on hover.
_SPIKE = dict(
    showspikes=True,
    spikemode="across",
    spikesnap="cursor",
    spikethickness=1,
    spikedash="dot",
    spikecolor="#6b6b8a",
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared layout base
# ─────────────────────────────────────────────────────────────────────────────

def _layout(title: str = "", height: int = 500, dragmode: str = "pan",
            hovermode: str = "x unified") -> dict:
    return dict(
        title=dict(text=title, font=dict(size=14, color=_TEXT)) if title else {},
        paper_bgcolor=_BG,
        plot_bgcolor=_BG,
        font=dict(color=_TEXT, size=12),
        dragmode=dragmode,       # "pan" for time-series, "zoom" for histograms/heatmaps
        hovermode=hovermode,
        legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0),
        modebar=dict(
            bgcolor="rgba(0,0,0,0)",
            color=_MUTED,
            activecolor=_TEXT,
            orientation="v",
        ),
        margin=dict(l=65, r=30, t=55, b=45),
        height=height,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Chart builders
# ─────────────────────────────────────────────────────────────────────────────

def _candlestick_chart(results: BacktestResults, zz_deviation: float = 0.015,
                        zz_deviation_3: float = 0.003) -> go.Figure:
    df = results.price_data
    trades = results.trades
    ts_set = set(df.index)

    # ── 4-panel layout: Price / RSI(2) / Stoch / RSI(13) ────────────────────
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        row_heights=[0.55, 0.15, 0.15, 0.15],
        vertical_spacing=0.035,
    )

    # Row 1 — Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color=_G, decreasing_line_color=_R,
        name="Price", showlegend=False,
    ), row=1, col=1)

    for span, color in [(9, "#ffa657"), (21, "#79c0ff")]:
        ema = df["close"].ewm(span=span, adjust=False).mean()
        fig.add_trace(go.Scatter(
            x=df.index, y=ema, line=dict(color=color, width=1.2),
            name=f"EMA{span}",
        ), row=1, col=1)

    longs  = [t for t in trades if t.direction == "LONG"  and t.entry_time in ts_set]
    shorts = [t for t in trades if t.direction == "SHORT" and t.entry_time in ts_set]
    exits  = [t for t in trades if t.exit_time is not None and t.exit_time in ts_set]

    if longs:
        fig.add_trace(go.Scatter(
            x=[t.entry_time for t in longs],
            y=[t.entry_price * 0.9985 for t in longs],
            mode="markers",
            marker=dict(symbol="triangle-up", size=13, color=_G,
                        line=dict(color="white", width=1)),
            name="Long Entry",
            hovertemplate="<b>LONG ENTRY</b><br>%{x}<br>@ %{y:.2f}<extra></extra>",
        ), row=1, col=1)

    if shorts:
        fig.add_trace(go.Scatter(
            x=[t.entry_time for t in shorts],
            y=[t.entry_price * 1.0015 for t in shorts],
            mode="markers",
            marker=dict(symbol="triangle-down", size=13, color=_R,
                        line=dict(color="white", width=1)),
            name="Short Entry",
            hovertemplate="<b>SHORT ENTRY</b><br>%{x}<br>@ %{y:.2f}<extra></extra>",
        ), row=1, col=1)

    if exits:
        ec = [_G if t.pnl >= 0 else _R for t in exits]
        fig.add_trace(go.Scatter(
            x=[t.exit_time for t in exits],
            y=[t.exit_price for t in exits],
            mode="markers",
            marker=dict(symbol="x-thin", size=12, color=ec,
                        line=dict(color=ec, width=2)),
            name="Exit",
            customdata=[(f"${t.pnl:+,.0f}", t.direction) for t in exits],
            hovertemplate="<b>EXIT %{customdata[1]}</b><br>%{x}<br>@ %{y:.2f}<br>P&L %{customdata[0]}<extra></extra>",
        ), row=1, col=1)

    for t in trades:
        if t.exit_time is None or t.entry_time not in ts_set or t.exit_time not in ts_set:
            continue
        color = _G if t.pnl >= 0 else _R
        fig.add_trace(go.Scatter(
            x=[t.entry_time, t.exit_time], y=[t.entry_price, t.exit_price],
            mode="lines", line=dict(color=color, width=1, dash="dot"),
            showlegend=False, hoverinfo="skip",
        ), row=1, col=1)

    # Row 2 — RSI(2)
    rsi2 = _calc_rsi(df["close"], 2)
    fig.add_trace(go.Scatter(
        x=df.index, y=rsi2, line=dict(color="#bb86fc", width=1.2),
        name="RSI(2)", showlegend=True,
    ), row=2, col=1)
    fig.add_hline(y=94, line=dict(color=_R, width=0.8, dash="dash"), row=2, col=1)
    fig.add_hline(y=2,  line=dict(color=_G, width=0.8, dash="dash"), row=2, col=1)

    # Row 3 — Stochastic
    stoch_k, stoch_d = _calc_stoch(df["high"], df["low"], df["close"])
    fig.add_trace(go.Scatter(
        x=df.index, y=stoch_k, line=dict(color="#42a5f5", width=1.2),
        name="%K", showlegend=True,
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=stoch_d, line=dict(color="#ef9a9a", width=1.0, dash="dash"),
        name="%D", showlegend=True,
    ), row=3, col=1)
    fig.add_hline(y=80, line=dict(color=_R, width=0.8, dash="dash"), row=3, col=1)
    fig.add_hline(y=20, line=dict(color=_G, width=0.8, dash="dash"), row=3, col=1)

    # Row 4 — RSI(13)
    rsi13 = _calc_rsi(df["close"], 13)
    fig.add_trace(go.Scatter(
        x=df.index, y=rsi13, line=dict(color="#ffb74d", width=1.2),
        name="RSI(13)", showlegend=True,
    ), row=4, col=1)
    fig.add_hline(y=70, line=dict(color=_R, width=0.8, dash="dash"), row=4, col=1)
    fig.add_hline(y=30, line=dict(color=_G, width=0.8, dash="dash"), row=4, col=1)

    # ── ZigZag swing overlay ──────────────────────────────────────────────────
    has_headers = False
    try:
        zz = _calc_zigzag(df["high"], df["low"], df["close"], deviation=zz_deviation)
        if not zz.empty:
            zz = _assign_swing_labels(zz)
            has_headers = True

            # ── 3-Leg ZigZag: short-term overlay, letter-labeled (A, B, C...)
            # region-by-region against the 10-leg swing boundaries above --
            # ported from CandlestickChart.tsx's swingLetter()/zz3LabelByTime
            # logic, keep in sync. Points that coincide with a 10-leg pivot
            # are excluded (already marked by the 10-leg's own circle).
            zz3 = _calc_zigzag(df["high"], df["low"], df["close"], deviation=zz_deviation_3, legs=3)
            region_letters_by_swingnum: dict = {}
            if not zz3.empty:
                swing_groups_3 = list(zz.groupby("swing"))
                swing_boundaries_3 = []
                for i, (_sn, grp) in enumerate(swing_groups_3):
                    x0 = pd.Timestamp.min if i == 0 else grp.index.min()
                    x1 = (swing_groups_3[i + 1][1].index.min() if i + 1 < len(swing_groups_3)
                          else (df.index.max() if len(df.index) else pd.Timestamp.max))
                    swing_boundaries_3.append((x0, x1))

                zz10_time_set = set(zz.index)
                zz3_labelable = zz3[~zz3.index.isin(zz10_time_set)].sort_index()
                zz3_label_by_time = {}
                # Per 10-leg region (keyed by swing_num), the ordered list of
                # 3-leg letters inside it -- lets the swing header show
                # "3 Leg Dev (A to H)" alongside the existing "(1.1 to 1.5)"
                # range. Ported from CandlestickChart.tsx, keep in sync.
                region_letters_by_swingnum.update({sn: [] for sn, _ in swing_groups_3})
                region_idx, counter = -2, 0
                for ts in zz3_labelable.index:
                    idx = next((k for k, (x0, x1) in enumerate(swing_boundaries_3) if x0 <= ts < x1), -1)
                    if idx != region_idx:
                        region_idx = idx
                        counter = 0
                    label = _swing_letter(counter + 1)
                    zz3_label_by_time[ts] = label
                    if idx >= 0:
                        region_letters_by_swingnum[swing_groups_3[idx][0]].append(label)
                    counter += 1

                fig.add_trace(go.Scatter(
                    x=zz3.index, y=zz3["price"], mode="lines",
                    line=dict(color="#f0c040", width=1.0, dash="dot"),
                    name="ZigZag (3L)", showlegend=True, hoverinfo="skip",
                ), row=1, col=1)

                for ptype, color in (("H", "#ff6b6b"), ("L", "#69f0ae")):
                    pts = zz3_labelable[zz3_labelable["type"] == ptype]
                    if not pts.empty:
                        fig.add_trace(go.Scatter(
                            x=pts.index, y=pts["price"], mode="markers+text",
                            marker=dict(symbol="circle", size=23, color=_MARKER_BG,
                                        line=dict(color=color, width=1.6)),
                            text=[zz3_label_by_time.get(ts, "") for ts in pts.index],
                            textposition="middle center",
                            textfont=dict(color="white", size=10, family="Arial"),
                            showlegend=False,
                            hovertemplate=f"<b>{'High' if ptype=='H' else 'Low'} (3L) %{{text}}</b><br>%{{x}}<br>@ %{{y:.2f}}<extra></extra>",
                        ), row=1, col=1)

            color_map = {s: _SWING_COLORS[i % len(_SWING_COLORS)]
                         for i, s in enumerate(sorted(zz["swing"].unique()))}
            border_colors = [color_map[s] for s in zz["swing"]]

            # ZigZag dotted gold line on price panel (10-leg / long-term)
            fig.add_trace(go.Scatter(
                x=zz.index, y=zz["price"], mode="lines",
                line=dict(color="#2196f3", width=1.5, dash="dot"),
                name="ZigZag (10L)", showlegend=True,
            ), row=1, col=1)

            # Swing circles on price panel
            fig.add_trace(go.Scatter(
                x=zz.index, y=zz["price"], mode="markers+text",
                marker=dict(symbol="circle", size=30, color=_MARKER_BG,
                            line=dict(color=border_colors, width=1.8)),
                text=zz["label"], textposition="middle center",
                textfont=dict(color="white", size=9, family="Arial"),
                showlegend=False,
                hovertemplate="<b>Swing %{text}</b><br>%{x}<br>@ %{y:.2f}<extra></extra>",
            ), row=1, col=1)

            # Swing circles on RSI(2), Stoch, RSI(13) panels
            for row_n, row_y in [(2, rsi2), (3, stoch_k), (4, rsi13)]:
                vals = row_y.reindex(zz.index)
                fig.add_trace(go.Scatter(
                    x=zz.index, y=vals, mode="markers+text",
                    marker=dict(size=22, color=_MARKER_BG,
                                line=dict(color=border_colors, width=1.8)),
                    text=zz["label"], textposition="middle center",
                    textfont=dict(size=8, color="white", family="Arial"),
                    showlegend=False,
                    hovertemplate="<b>Swing %{text}</b><br>%{y:.1f}<extra></extra>",
                ), row=row_n, col=1)

            # Swing region boundaries + headers
            for swing_num, grp in zz.groupby("swing"):
                color = _SWING_COLORS[(swing_num - 1) % len(_SWING_COLORS)]
                x0 = grp.index[0]
                x1 = grp.index[-1]
                x_mid = grp.index[len(grp) // 2]
                first_label = grp["label"].iloc[0]
                last_label  = grp["label"].iloc[-1]

                fig.add_shape(
                    type="rect", xref="x", yref="paper",
                    x0=x0, x1=x1, y0=0, y1=1,
                    fillcolor="rgba(0,0,0,0)",
                    line=dict(color=color, width=1.5, dash="dot"),
                    layer="below",
                )
                letters = region_letters_by_swingnum.get(swing_num, [])
                leg_part = f" | 3 Leg Dev ({letters[0]} to {letters[-1]})" if letters else ""
                fig.add_annotation(
                    x=x_mid, y=1.005, xref="x", yref="paper", yanchor="bottom",
                    text=f"<b>Swing {swing_num}</b><br>({first_label} to {last_label}){leg_part}",
                    showarrow=False, font=dict(color=color, size=11),
                    align="center",
                )
    except Exception:
        has_headers = False

    _t = 145 if has_headers else 55
    _rs_y = 1.15 if has_headers else 1.02
    _ylabel = dict(font=dict(size=9, color=_MUTED), standoff=4)
    _base = _layout(f"{results.symbol} — {results.strategy_name}", height=920)
    _base["margin"] = dict(l=60, r=12, t=_t, b=8)
    fig.update_layout(
        **_base,
        xaxis=dict(
            gridcolor=_GRID, rangeslider_visible=False,
            rangeselector={**_RANGE_SELECTOR, "y": _rs_y},
            **_SPIKE,
        ),
        xaxis2=dict(gridcolor=_GRID, **_SPIKE),
        xaxis3=dict(gridcolor=_GRID, **_SPIKE),
        xaxis4=dict(gridcolor=_GRID, **_SPIKE),
        yaxis =dict(gridcolor=_GRID, title=dict(text="Price",   **_ylabel), fixedrange=False),
        yaxis2=dict(gridcolor=_GRID, title=dict(text="RSI(2)",  **_ylabel), fixedrange=True, range=[-5, 105]),
        yaxis3=dict(gridcolor=_GRID, title=dict(text="Stoch",   **_ylabel), fixedrange=True, range=[-5, 105]),
        yaxis4=dict(gridcolor=_GRID, title=dict(text="RSI(13)", **_ylabel), fixedrange=True, range=[-5, 105]),
    )
    return fig


def _equity_chart(results: BacktestResults) -> go.Figure:
    eq = results.equity_curve
    dd = (eq - eq.cummax()) / eq.cummax() * 100

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.65, 0.35], vertical_spacing=0.04,
    )

    fig.add_trace(go.Scatter(
        x=eq.index, y=eq.values, name="Portfolio",
        line=dict(color=_B, width=2),
        fill="tozeroy", fillcolor="rgba(88,166,255,0.1)",
    ), row=1, col=1)
    fig.add_hline(y=results.initial_capital,
                  line=dict(color=_MUTED, dash="dash", width=1), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=dd.index, y=dd.values, name="Drawdown %",
        line=dict(color=_R, width=1.5),
        fill="tozeroy", fillcolor="rgba(248,81,73,0.15)",
    ), row=2, col=1)

    fig.update_layout(
        **_layout("Equity Curve & Drawdown", height=430),
        xaxis=dict(
            gridcolor=_GRID,
            rangeselector=_RANGE_SELECTOR,
            **_SPIKE,
        ),
        xaxis2=dict(gridcolor=_GRID, **_SPIKE),
        yaxis=dict(gridcolor=_GRID, title="Value ($)",    fixedrange=False),
        yaxis2=dict(gridcolor=_GRID, title="Drawdown (%)", fixedrange=False),
    )
    return fig


def _pnl_hist(results: BacktestResults) -> go.Figure:
    if not results.trades:
        return go.Figure()
    pnls = [t.pnl for t in results.trades]
    fig = go.Figure(go.Histogram(
        x=pnls, nbinsx=25,
        marker_color=[_G if p >= 0 else _R for p in pnls],
        hovertemplate="P&L: $%{x:.0f}<br>Count: %{y}<extra></extra>",
    ))
    fig.add_vline(x=0, line=dict(color="white", dash="dash", width=1))
    fig.update_layout(
        **_layout("P&L Distribution", height=310, dragmode="zoom", hovermode="closest"),
        xaxis=dict(gridcolor=_GRID, title="P&L ($)", fixedrange=False),
        yaxis=dict(gridcolor=_GRID, title="Count",   fixedrange=False),
    )
    return fig


def _monthly_heatmap(results: BacktestResults) -> go.Figure:
    if results.equity_curve.empty:
        return go.Figure()
    eq = results.equity_curve.resample("ME").last()
    monthly = eq.pct_change() * 100
    monthly.index = monthly.index.to_period("M")
    years = sorted({p.year for p in monthly.index})
    month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]
    z, text = [], []
    for y in years:
        row, rt = [], []
        for m in range(1, 13):
            p = pd.Period(year=y, month=m, freq="M")
            v = monthly.get(p)
            row.append(float(v) if v is not None else None)
            rt.append(f"{v:.1f}%" if v is not None else "")
        z.append(row)
        text.append(rt)

    fig = go.Figure(go.Heatmap(
        z=z, x=month_names, y=[str(y) for y in years],
        text=text, texttemplate="%{text}",
        colorscale=[[0, _R], [0.5, "#21262d"], [1, _G]], zmid=0,
        hovertemplate="%{y} %{x}: <b>%{z:.1f}%</b><extra></extra>",
    ))
    fig.update_layout(
        **_layout("Monthly Returns (%)", height=max(200, 65 * len(years) + 100),
                  dragmode="zoom", hovermode="closest"),
        xaxis=dict(gridcolor=_GRID, fixedrange=False),
        yaxis=dict(gridcolor=_GRID, fixedrange=False),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Pattern tables (candlestick / chart patterns) -- mirrors
# CandlestickPatternsTable.tsx / ChartPatternsTable.tsx in the live app.
# ─────────────────────────────────────────────────────────────────────────────

_CANDLE_PATTERN_LABELS = {
    "doji": "Doji", "hammer": "Hammer",
    "bullish_engulfing": "Bullish Engulfing", "bearish_engulfing": "Bearish Engulfing",
    "morning_star": "Morning Star", "evening_star": "Evening Star",
}
_CHART_PATTERN_LABELS = {
    "double_top": "Double Top", "double_bottom": "Double Bottom",
    "head_and_shoulders": "Head & Shoulders",
    "inverse_head_and_shoulders": "Inverse Head & Shoulders", "triangle": "Triangle",
}


def _direction_color(direction: str) -> str:
    if direction == "bullish":
        return _G
    if direction == "bearish":
        return _R
    return _TEXT


def _candlestick_patterns_table(results: BacktestResults, min_confidence: float = 70.0) -> str:
    patterns = [p for p in detect_candlestick_patterns(results.price_data) if p.confidence >= min_confidence]
    patterns.sort(key=lambda p: p.confidence, reverse=True)
    if not patterns:
        return '<p style="color:#8b949e;padding:12px">No candlestick patterns at this confidence threshold.</p>'
    rows = []
    for p in patterns:
        color = _direction_color(p.direction)
        rows.append(
            f"<tr><td>{p.timestamp.strftime('%Y-%m-%d %H:%M')}</td>"
            f"<td>{_CANDLE_PATTERN_LABELS.get(p.pattern, p.pattern)}</td>"
            f"<td style='color:{color}'>{p.direction}</td>"
            f"<td style='text-align:right'>{p.confidence:.0f}%</td></tr>"
        )
    return (
        '<div style="max-height:480px;overflow-y:auto">'
        '<table><thead><tr><th>Time</th><th>Pattern</th><th>Direction</th>'
        '<th style="text-align:right">Confidence</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
        f'<p style="color:#8b949e;font-size:0.78rem;padding:8px 12px">'
        f'{len(patterns)} patterns at ≥{min_confidence:.0f}% confidence — rule-based candle geometry, no ML.</p>'
    )


def _chart_patterns_table(results: BacktestResults) -> str:
    df = results.price_data
    patterns = find_chart_patterns(df, left=2, right=2, min_move=0.0)
    if not patterns:
        return '<p style="color:#8b949e;padding:12px">No chart patterns detected in this period.</p>'
    rows = []
    for p in patterns:
        color = _direction_color(p.direction)
        metrics = " · ".join(f"{k}: {v:.2f}" if isinstance(v, float) else f"{k}: {v}" for k, v in p.metrics.items())
        rows.append(
            f"<tr><td>{_CHART_PATTERN_LABELS.get(p.pattern, p.pattern)}</td>"
            f"<td style='color:{color}'>{p.direction}</td>"
            f"<td>{df.index[p.start_index].strftime('%Y-%m-%d %H:%M')}</td>"
            f"<td>{df.index[p.end_index].strftime('%Y-%m-%d %H:%M')}</td>"
            f"<td style='text-align:right'>{p.neckline:.2f}</td>"
            f"<td style='color:#8b949e;font-size:0.8rem'>{metrics}</td></tr>"
        )
    return (
        '<div style="max-height:480px;overflow-y:auto">'
        '<table><thead><tr><th>Pattern</th><th>Direction</th><th>Start</th><th>End</th>'
        '<th style="text-align:right">Neckline</th><th>Metrics</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# Elliott Wave charts -- Python/Plotly equivalents of ElliottWaveChart.tsx /
# WavePivotChart.tsx / FibonacciZonesChart.tsx in the live app. Same source
# data (wave_analysis.py's analyze_degrees()), same labeling conventions.
# ─────────────────────────────────────────────────────────────────────────────

_IMPULSE_COLOR = "#2196f3"
_CORRECTION_COLOR = "#f0c040"
_INVALIDATION_COLOR = "#F97316"
_CYAN = "#14E0D4"

_ROMAN_DIGITS = [
    (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"),
    (100, "c"), (90, "xc"), (50, "l"), (40, "xl"),
    (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"),
]


def _to_roman(n: int) -> str:
    """Open-ended roman numeral generator -- keeps counting (viii, ix, x...)
    past a fixed 7-entry list instead of falling back to a bare number.
    Ported from ElliottWaveChart.tsx's toRoman(), keep in sync."""
    out = []
    for value, symbol in _ROMAN_DIGITS:
        while n >= value:
            out.append(symbol)
            n -= value
    return "".join(out)


def _to_letters(n: int, upper: bool = False) -> str:
    """Open-ended letter generator (a, b, c... z, aa, ab...) -- ported from
    ElliottWaveChart.tsx's toLetters() / CorrectiveWavesPanel.tsx's
    pivotLetter(), keep in sync."""
    base = 65 if upper else 97
    letters = ""
    x = n
    while x > 0:
        x, rem = divmod(x - 1, 26)
        letters = chr(base + rem) + letters
    return letters


def _wrap(label: str, nested: bool) -> str:
    return f"({label})" if nested else label


def _pivot_labels(pivots: list, kind: str, nested: bool) -> list[str]:
    """kind: 'roman', 'letters' (lowercase a/b/c -- combined Wave Analysis
    chart's correction leg), or 'letters_upper' (A/B/C -- standalone
    Corrective Waves chart, matches CorrectiveWavesPanel.tsx)."""
    if kind == "roman":
        gen = _to_roman
    elif kind == "letters_upper":
        gen = lambda i: _to_letters(i, upper=True)
    else:
        gen = lambda i: _to_letters(i)
    return ["" if i == 0 else _wrap(gen(i), nested) for i in range(len(pivots))]


def _base_candles(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        increasing_line_color=_G, decreasing_line_color=_R, name="Price", showlegend=False,
    ))
    return fig


def _wave_pivot_chart(df: pd.DataFrame, pivots: list, labels: list[str], color: str,
                       series_name: str, title: str, dash: bool = False) -> go.Figure:
    fig = _base_candles(df)
    if pivots:
        xs = [p.timestamp if hasattr(p, "timestamp") else df.index[p.index] for p in pivots]
        ys = [p.price for p in pivots]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines+markers",
            line=dict(color=color, width=1.5, dash="dot" if dash else "solid"),
            marker=dict(size=6, color=color), name=series_name, showlegend=True,
            text=labels, hovertemplate="%{text}<br>%{x}<br>@ %{y:.2f}<extra></extra>",
        ))
        for x, y, label, p in zip(xs, ys, labels, pivots):
            if not label:
                continue
            up = getattr(p, "kind", None)
            up = (up.value if hasattr(up, "value") else up) == "high" if up is not None else True
            fig.add_annotation(x=x, y=y, text=f"<b>{label}</b>", showarrow=False,
                                font=dict(color=color, size=11), yshift=16 if up else -16)
    fig.update_layout(
        **_layout(title, height=420),
        xaxis=dict(gridcolor=_GRID, rangeslider_visible=False, **_SPIKE),
        yaxis=dict(gridcolor=_GRID, title="Price", fixedrange=False),
    )
    return fig


def _fibonacci_zones_chart(df: pd.DataFrame, zones: list, title: str) -> go.Figure:
    fig = _base_candles(df)
    max_strength = max([z.strength for z in zones] + [1])
    for z in zones:
        opacity = 0.12 + 0.28 * (z.strength / max_strength)
        fig.add_shape(
            type="rect", xref="paper", yref="y", x0=0, x1=1, y0=z.low, y1=z.high,
            fillcolor=f"rgba(20,224,212,{opacity:.2f})",
            line=dict(color=_CYAN, width=1, dash="dot"), layer="below",
        )
        fig.add_annotation(
            x=1, y=z.center, xref="paper", yref="y", xanchor="right", yanchor="middle",
            text=f"{z.center:.2f} ×{z.strength}", showarrow=False,
            font=dict(color=_CYAN, size=10), bgcolor="rgba(13,17,23,0.7)",
        )
    layout_kwargs = _layout(title, height=420)
    layout_kwargs["margin"] = dict(l=65, r=90, t=55, b=45)
    fig.update_layout(
        **layout_kwargs,
        xaxis=dict(gridcolor=_GRID, rangeslider_visible=False, **_SPIKE),
        yaxis=dict(gridcolor=_GRID, title="Price", fixedrange=False),
    )
    return fig


def _wave_analysis_chart(df: pd.DataFrame, a: WaveAnalysis, nested: bool, symbol: str) -> go.Figure:
    fig = _base_candles(df)

    if a.impulse and len(a.impulse.pivots) > 1:
        pivots = a.impulse.pivots
        labels = _pivot_labels(pivots, "roman", nested)
        xs = [df.index[p.index] for p in pivots]
        ys = [p.price for p in pivots]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines+markers", line=dict(color=_IMPULSE_COLOR, width=1.5),
            marker=dict(size=6, color=_IMPULSE_COLOR), name=f"Impulse ({a.impulse.direction})",
            text=labels, hovertemplate="%{text}<br>%{x}<br>@ %{y:.2f}<extra></extra>",
        ))
        for x, y, label, p in zip(xs, ys, labels, pivots):
            if not label:
                continue
            up = p.kind.value == "high"
            fig.add_annotation(x=x, y=y, text=f"<b>{label}</b>", showarrow=False,
                                font=dict(color=_IMPULSE_COLOR, size=12), yshift=16 if up else -16)

    if a.correction and len(a.correction.pivots) > 1:
        pivots = a.correction.pivots
        labels = _pivot_labels(pivots, "letters", nested)
        xs = [df.index[p.index] for p in pivots]
        ys = [p.price for p in pivots]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines+markers", line=dict(color=_CORRECTION_COLOR, width=1.5, dash="dot"),
            marker=dict(size=6, color=_CORRECTION_COLOR), name=f"Correction ({a.correction.type.value.replace('_', ' ')})",
            text=labels, hovertemplate="%{text}<br>%{x}<br>@ %{y:.2f}<extra></extra>",
        ))
        for x, y, label, p in zip(xs, ys, labels, pivots):
            if not label:
                continue
            up = p.kind.value == "high"
            fig.add_annotation(x=x, y=y, text=f"<b>{label}</b>", showarrow=False,
                                font=dict(color=_CORRECTION_COLOR, size=12), yshift=16 if up else -16)

    if a.invalidation is not None:
        fig.add_shape(type="line", xref="paper", yref="y", x0=0, x1=1,
                       y0=a.invalidation, y1=a.invalidation,
                       line=dict(color=_INVALIDATION_COLOR, dash="dash", width=1.2))
        fig.add_annotation(x=1, y=a.invalidation, xref="paper", yref="y", xanchor="right", yanchor="bottom",
                            text=f"Invalidation @ {a.invalidation:.2f}",
                            showarrow=False, font=dict(color=_INVALIDATION_COLOR, size=10))

    bias_color = _G if a.bias == "long" else (_R if a.bias == "short" else "#8b93b8")
    bias_text = "Turning Up ↗" if a.bias == "long" else ("Turning Down ↘" if a.bias == "short" else "Neutral")
    fig.add_annotation(x=0.99, y=0.99, xref="paper", yref="paper", xanchor="right", yanchor="top",
                        text=f"<b>{bias_text}</b>", showarrow=False, font=dict(color=bias_color, size=12),
                        bgcolor="rgba(13,17,23,0.75)", bordercolor=bias_color, borderwidth=1, borderpad=4)

    layout_kwargs = _layout(f"{symbol} — {a.degree} degree Elliott Wave · {a.cycle_position}", height=480)
    layout_kwargs["legend"] = dict(orientation="h", y=-0.08, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(
        **layout_kwargs,
        xaxis=dict(gridcolor=_GRID, rangeslider_visible=False, **_SPIKE),
        yaxis=dict(gridcolor=_GRID, title="Price", fixedrange=False),
    )
    return fig


def _wave_analysis_sections(results: BacktestResults) -> dict:
    """Builds the HTML for all 5 Elliott Wave tabs (Wave Analysis, Swing
    Identification, Elliott Wave, Corrective Waves, Fibonacci), one degree's
    chart per section per degree -- mirrors ElliottWavePanel.tsx and friends
    in the live app exactly, same wave_analysis.py data underneath."""
    df = results.price_data
    symbol = results.symbol
    try:
        degrees = analyze_degrees(df)
    except Exception:
        degrees = {}

    try:
        med = float(np.nanmedian(_wave_atr(df["high"], df["low"], df["close"], 14)))
        swings_by_degree = {
            d["name"]: identify_swings(df, left=d["left"], right=d["right"], min_move=d["mm_mult"] * med)
            for d in _WAVE_DEGREES
        }
    except Exception:
        swings_by_degree = {}

    wave_analysis_html, swings_html, impulse_html, corrective_html, fib_html = [], [], [], [], []

    def _box(html: str) -> str:
        return f'<div class="chart-box">{html}</div>'

    # Mirrors ImpulseWavesPanel.tsx's WAVE_LABELS -- plain numbers, origin IS
    # labeled "0" here (unlike the other wave charts, which skip the origin).
    _WAVE_LABELS = ["0", "1", "2", "3", "4", "5", "6", "7"]

    for name, a in degrees.items():
        nested = name == "minor"
        wave_analysis_html.append(_box(_fig_to_div(_wave_analysis_chart(df, a, nested, symbol))))

        swing_pivots = swings_by_degree.get(name, [])
        swing_labels = [s.label.value if s.label else "" for s in swing_pivots]
        swings_html.append(_box(_fig_to_div(_wave_pivot_chart(
            df, swing_pivots, swing_labels, "#8b93b8", "Swings", f"{symbol} — {name} degree swings"))))

        if a.impulse:
            imp_labels = [_WAVE_LABELS[j] if j < len(_WAVE_LABELS) else str(j)
                          for j in range(len(a.impulse.pivots))]
            color = _G if a.impulse.valid else _R
            impulse_html.append(_box(_fig_to_div(_wave_pivot_chart(
                df, a.impulse.pivots, imp_labels, color, f"Impulse ({a.impulse.direction})",
                f"{symbol} — {name} degree impulse ({'valid' if a.impulse.valid else 'invalid'})"))))

        if a.correction:
            corr_labels = _pivot_labels(a.correction.pivots, "letters_upper", False)
            corrective_html.append(_box(_fig_to_div(_wave_pivot_chart(
                df, a.correction.pivots, corr_labels, _CORRECTION_COLOR,
                f"Correction ({a.correction.type.value.replace('_', ' ')})",
                f"{symbol} — {name} degree correction — {a.correction.type.value.replace('_', ' ')}", dash=True))))

        if a.target_zones:
            fib_html.append(_box(_fig_to_div(_fibonacci_zones_chart(
                df, a.target_zones, f"{symbol} — {name} degree Fibonacci confluence zones"))))

    def _joined(parts: list, empty_msg: str) -> str:
        return "".join(parts) if parts else f'<p style="color:#8b949e;padding:12px">{empty_msg}</p>'

    return {
        "wave_analysis": _joined(wave_analysis_html, "No wave structure detected in this backtest's price data."),
        "swings": _joined(swings_html, "No swings detected in this backtest's price data."),
        "impulse": _joined(impulse_html, "No structurally valid impulse wave found in this backtest's price data."),
        "corrective": _joined(corrective_html, "No correction detected yet following the impulse."),
        "fibonacci": _joined(fib_html, "No confluence zones formed yet."),
    }


# ─────────────────────────────────────────────────────────────────────────────
# HTML template
# ─────────────────────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ scroll-behavior: smooth; }}
  body {{ background: #0a0e16; color: #e6edf3;
         font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         font-feature-settings: "tnum" 1; }}
  .mono {{ font-family: 'JetBrains Mono', ui-monospace, monospace; }}
  .page {{ max-width: 1440px; margin: 0 auto; padding: 28px 28px 56px; }}

  /* ── header ── */
  header {{ padding-bottom: 20px; margin-bottom: 18px; position: relative; }}
  header::after {{
    content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 1px;
    background: linear-gradient(90deg, #58a6ff55, #21262d 35%, transparent 80%);
  }}
  .eyebrow {{ font-size: 0.72rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase;
              color: #58a6ff; margin-bottom: 6px; display: flex; align-items: center; gap: 8px; }}
  .eyebrow .dot {{ width: 6px; height: 6px; border-radius: 50%; background: #3fb950;
                   box-shadow: 0 0 0 3px #3fb95022; }}
  header h1 {{ font-size: 1.85rem; font-weight: 800; letter-spacing: -0.02em;
               background: linear-gradient(90deg, #e6edf3, #a8c7ff);
               -webkit-background-clip: text; background-clip: text; color: transparent; }}
  header p  {{ color: #8b949e; font-size: 0.85rem; margin-top: 10px; }}
  .badge {{ display: inline-flex; align-items: center; gap: 5px; background: #161b22;
            border: 1px solid #21262d; border-radius: 999px;
            padding: 4px 12px; font-size: 0.78rem; color: #c9d1d9; margin-right: 8px; }}
  .badge b {{ color: #58a6ff; font-weight: 600; }}

  /* ── sticky section nav ── */
  nav.toc {{
    position: sticky; top: 0; z-index: 50; background: #0a0e16ee;
    backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
    border-bottom: 1px solid #21262d; margin: 0 -28px 22px; padding: 10px 28px;
    display: flex; gap: 4px; overflow-x: auto; scrollbar-width: thin;
  }}
  nav.toc::-webkit-scrollbar {{ height: 4px; }}
  nav.toc::-webkit-scrollbar-thumb {{ background: #30363d; border-radius: 4px; }}
  nav.toc a {{
    flex: 0 0 auto; display: inline-flex; align-items: center; gap: 6px;
    color: #8b949e; text-decoration: none; font-size: 0.78rem; font-weight: 500;
    padding: 6px 12px; border-radius: 6px; white-space: nowrap;
    transition: background 0.15s, color 0.15s;
  }}
  nav.toc a:hover {{ background: #161b22; color: #e6edf3; }}

  /* ── zoom/controls hint bar ── */
  .controls-hint {{
    display: flex; gap: 20px; flex-wrap: wrap; align-items: center;
    background: #10151f; border: 1px solid #1c2333; border-radius: 10px;
    padding: 11px 18px; margin-bottom: 24px; font-size: 0.8rem; color: #8b949e;
  }}
  .controls-hint span {{ display: flex; align-items: center; gap: 6px; }}
  .kbd {{
    display: inline-block; background: #21262d; border: 1px solid #3a4150;
    border-radius: 5px; padding: 1px 7px; font-size: 0.75rem;
    color: #cdd6f4; font-family: 'JetBrains Mono', monospace; box-shadow: 0 1px 0 #000a;
  }}

  /* ── metric cards ── */
  .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
              gap: 12px; margin-bottom: 28px; }}
  .metric-card {{
    position: relative; background: #10151f; border: 1px solid #1c2333; border-radius: 10px;
    padding: 15px 16px 15px 18px; overflow: hidden;
    transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s;
  }}
  .metric-card::before {{
    content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
  }}
  .metric-card.positive::before {{ background: #3fb950; }}
  .metric-card.negative::before {{ background: #f85149; }}
  .metric-card.neutral::before  {{ background: #3a4150; }}
  .metric-card:hover {{
    transform: translateY(-2px); border-color: #30363d;
    box-shadow: 0 8px 20px -8px #000a;
  }}
  .metric-card .label {{ font-size: 0.7rem; color: #8b949e; text-transform: uppercase;
                          letter-spacing: 0.07em; margin-bottom: 6px; font-weight: 600; }}
  .metric-card .value {{ font-size: 1.4rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; }}
  .positive {{ color: #3fb950; }}
  .negative {{ color: #f85149; }}
  .neutral  {{ color: #e6edf3; }}

  /* ── section titles ── */
  .section-title {{
    display: flex; align-items: center; gap: 9px;
    font-size: 0.95rem; font-weight: 700; color: #e6edf3;
    margin: 40px 0 12px; padding-bottom: 8px; border-bottom: 1px solid #1c2333;
    scroll-margin-top: 58px;
  }}
  .section-title .icon {{ font-size: 1.05rem; }}
  .section-title .tag {{
    margin-left: auto; font-size: 0.68rem; font-weight: 600; color: #8b949e;
    text-transform: uppercase; letter-spacing: 0.06em; background: #161b22;
    border: 1px solid #21262d; border-radius: 999px; padding: 2px 10px;
  }}

  /* ── chart containers ── */
  .chart-box {{
    background: #0d1117; border: 1px solid #1c2333; border-radius: 12px;
    padding: 4px; margin-bottom: 20px; overflow: hidden;
    box-shadow: 0 1px 0 #ffffff05 inset;
  }}

  /* ── trade log table ── */
  table {{ width: 100%; border-collapse: collapse; font-size: 0.83rem; }}
  thead tr {{ background: #161b22; }}
  th {{ padding: 10px 14px; text-align: left; color: #8b949e; font-weight: 600;
        font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.07em;
        border-bottom: 1px solid #21262d; }}
  tbody tr {{ border-bottom: 1px solid #161b22; transition: background 0.1s; }}
  tbody tr:hover {{ background: #10151f; }}
  td {{ padding: 8px 14px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; }}
  .pnl-pos {{ color: #3fb950; font-weight: 600; }}
  .pnl-neg {{ color: #f85149; font-weight: 600; }}
  .dir-long  {{ color: #3fb950; font-weight: 600; }}
  .dir-short {{ color: #f85149; font-weight: 600; }}

  /* ── layout helpers ── */
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 768px) {{ .two-col {{ grid-template-columns: 1fr; }} }}

  footer {{
    margin-top: 48px; padding-top: 18px; border-top: 1px solid #1c2333;
    color: #6e7681; font-size: 0.78rem; text-align: center; letter-spacing: 0.02em;
  }}
  footer b {{ color: #8b949e; }}
</style>
</head>
<body>
<div class="page">

<header>
  <div class="eyebrow"><span class="dot"></span> Backtest Report</div>
  <h1>{title}</h1>
  <p>
    <span class="badge">Symbol <b>{symbol}</b></span>
    <span class="badge">Timeframe <b>{timeframe}</b></span>
    <span class="badge">{start} → {end}</span>
    <span class="badge">Generated {generated}</span>
  </p>
</header>

<nav class="toc">
  <a href="#price-chart">📊 Price &amp; Trades</a>
  <a href="#equity-curve">📈 Equity</a>
  <a href="#pnl-distribution">📈 P&amp;L</a>
  <a href="#monthly-returns">📅 Monthly</a>
  <a href="#trade-log">📋 Trade Log</a>
  <a href="#candlestick-patterns">🕯️ Candlesticks</a>
  <a href="#chart-patterns">📐 Chart Patterns</a>
  <a href="#wave-analysis">🌊 Wave Analysis</a>
  <a href="#swing-identification">🔀 Swings</a>
  <a href="#elliott-wave">📶 Elliott Wave</a>
  <a href="#corrective-waves">🔁 Corrective</a>
  <a href="#fibonacci">📐 Fibonacci</a>
</nav>

<!-- ── controls hint ── -->
<div class="controls-hint">
  <span>🖱️ <strong style="color:#cdd6f4">Chart Controls</strong></span>
  <span><kbd class="kbd">Scroll</kbd> Zoom in / out</span>
  <span><kbd class="kbd">Click + Drag</kbd> Pan</span>
  <span><kbd class="kbd">Double-click</kbd> Reset zoom</span>
  <span><kbd class="kbd">Shift + Drag</kbd> Box zoom</span>
  <span>Use the <strong style="color:#cdd6f4">1D / 1M / All</strong> buttons above each chart to jump to a time window</span>
  <span>📷 Camera icon → save PNG</span>
</div>

<div class="metrics">
{metric_cards}
</div>

<div class="section-title" id="price-chart"><span class="icon">📊</span> Price Chart, Indicators &amp; Trades</div>
<div class="chart-box">{chart_candle}</div>

<div class="section-title" id="equity-curve"><span class="icon">📈</span> Equity Curve</div>
<div class="chart-box">{chart_equity}</div>

<div class="two-col">
  <div>
    <div class="section-title" id="pnl-distribution"><span class="icon">📈</span> P&amp;L Distribution</div>
    <div class="chart-box">{chart_pnl}</div>
  </div>
  <div>
    <div class="section-title" id="monthly-returns"><span class="icon">📅</span> Monthly Returns</div>
    <div class="chart-box">{chart_monthly}</div>
  </div>
</div>

<div class="section-title" id="trade-log"><span class="icon">📋</span> Trade Log <span class="tag">{trade_count} trades</span></div>
<div class="chart-box" style="padding:0; overflow-x:auto">
<table>
  <thead>
    <tr>
      <th>#</th><th>Direction</th><th>Entry Time</th><th>Entry $</th>
      <th>Exit Time</th><th>Exit $</th><th>Duration</th><th>P&amp;L</th>
    </tr>
  </thead>
  <tbody>
{trade_rows}
  </tbody>
</table>
</div>

<div class="section-title" id="candlestick-patterns"><span class="icon">🕯️</span> Candlestick Patterns</div>
<div class="chart-box" style="padding:0">{candlestick_patterns_table}</div>

<div class="section-title" id="chart-patterns"><span class="icon">📐</span> Chart Patterns</div>
<div class="chart-box" style="padding:0">{chart_patterns_table}</div>

<div class="section-title" id="wave-analysis"><span class="icon">🌊</span> Wave Analysis</div>
{wave_analysis_charts}

<div class="section-title" id="swing-identification"><span class="icon">🔀</span> Swing Identification</div>
{swings_charts}

<div class="section-title" id="elliott-wave"><span class="icon">📶</span> Elliott Wave</div>
{impulse_charts}

<div class="section-title" id="corrective-waves"><span class="icon">🔁</span> Corrective Waves</div>
{corrective_charts}

<div class="section-title" id="fibonacci"><span class="icon">📐</span> Fibonacci</div>
{fibonacci_charts}

<footer><b>AutoTrader</b> Backtest Report &mdash; {title} &mdash; Generated {generated}</footer>
</div>
</body>
</html>
"""


def _metric_card(label: str, value: str, positive: bool | None = None) -> str:
    cls = "positive" if positive is True else ("negative" if positive is False else "neutral")
    return (
        f'<div class="metric-card {cls}">'
        f'<div class="label">{label}</div>'
        f'<div class="value {cls}">{value}</div>'
        f'</div>'
    )


def _fig_to_div(fig: go.Figure, first: bool = False) -> str:
    """Convert a figure to an HTML div with scroll-zoom enabled."""
    return pio.to_html(
        fig,
        include_plotlyjs="cdn" if first else False,
        full_html=False,
        config=_CHART_CFG,
    )


def generate_html_report(results: BacktestResults, output_path: str | None = None,
                         zz_deviation: float = 0.015, zz_deviation_3: float = 0.003) -> str:
    """
    Build a self-contained HTML report from BacktestResults.

    Returns the HTML string. Optionally writes it to output_path.
    """
    r = results

    cards = [
        _metric_card("Total Return",  f"{r.total_return_pct:+.1f}%",  r.total_return_pct >= 0),
        _metric_card("Total P&L",     f"${r.total_pnl:+,.0f}",        r.total_pnl >= 0),
        _metric_card("Final Capital", f"${r.final_capital:,.0f}"),
        _metric_card("Sharpe Ratio",  f"{r.sharpe_ratio:.2f}",         r.sharpe_ratio >= 1),
        _metric_card("Max Drawdown",  f"{r.max_drawdown_pct:.1f}%",    False),
        _metric_card("Win Rate",      f"{r.win_rate:.0f}%",            r.win_rate >= 50),
        _metric_card("Profit Factor", f"{r.profit_factor:.2f}",        r.profit_factor >= 1.5),
        _metric_card("Total Trades",  str(r.total_trades)),
        _metric_card("Avg Win",       f"${r.avg_win:,.0f}",            True),
        _metric_card("Avg Loss",      f"${r.avg_loss:,.0f}",           False),
        _metric_card("Sortino Ratio", f"{r.sortino_ratio:.2f}",        r.sortino_ratio >= 1),
        _metric_card("Avg Duration",  f"{r.avg_trade_duration_min:.0f} min"),
    ]

    trade_rows = []
    for i, t in enumerate(r.trades, 1):
        pnl_cls = "pnl-pos" if t.pnl >= 0 else "pnl-neg"
        dir_cls = "dir-long" if t.direction == "LONG" else "dir-short"
        dur = f"{t.duration_minutes:.0f}m" if t.duration_minutes else "—"
        exit_price_str = f"{t.exit_price:.2f}" if t.exit_price is not None else "—"
        exit_time_str  = t.exit_time.strftime("%Y-%m-%d %H:%M") if t.exit_time else "—"
        trade_rows.append(
            f"<tr>"
            f"<td>{i}</td>"
            f"<td class='{dir_cls}'>{t.direction}</td>"
            f"<td>{t.entry_time.strftime('%Y-%m-%d %H:%M')}</td>"
            f"<td>{t.entry_price:.2f}</td>"
            f"<td>{exit_time_str}</td>"
            f"<td>{exit_price_str}</td>"
            f"<td>{dur}</td>"
            f"<td class='{pnl_cls}'>${t.pnl:+,.0f}</td>"
            f"</tr>"
        )

    # First chart bundles Plotly.js from CDN; subsequent charts reuse it.
    chart_candle  = _fig_to_div(_candlestick_chart(r, zz_deviation=zz_deviation, zz_deviation_3=zz_deviation_3), first=True)
    chart_equity  = _fig_to_div(_equity_chart(r))
    chart_pnl     = _fig_to_div(_pnl_hist(r))
    chart_monthly = _fig_to_div(_monthly_heatmap(r))

    # Everything the live app's remaining tabs show, added here so the
    # exported file is a complete standalone copy of the whole dashboard,
    # not just the original 4 charts + trade log.
    candlestick_patterns_table = _candlestick_patterns_table(r)
    chart_patterns_table = _chart_patterns_table(r)
    wave_sections = _wave_analysis_sections(r)

    title = f"{r.strategy_name} — {r.symbol}"
    html = _HTML_TEMPLATE.format(
        title=title,
        symbol=r.symbol,
        timeframe=r.timeframe,
        start=r.start_date.strftime("%Y-%m-%d"),
        end=r.end_date.strftime("%Y-%m-%d"),
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        metric_cards="\n".join(cards),
        chart_candle=chart_candle,
        chart_equity=chart_equity,
        chart_pnl=chart_pnl,
        chart_monthly=chart_monthly,
        trade_count=len(r.trades),
        trade_rows="\n".join(trade_rows),
        candlestick_patterns_table=candlestick_patterns_table,
        chart_patterns_table=chart_patterns_table,
        wave_analysis_charts=wave_sections["wave_analysis"],
        swings_charts=wave_sections["swings"],
        impulse_charts=wave_sections["impulse"],
        corrective_charts=wave_sections["corrective"],
        fibonacci_charts=wave_sections["fibonacci"],
    )

    if output_path:
        Path(output_path).write_text(html, encoding="utf-8")

    return html
