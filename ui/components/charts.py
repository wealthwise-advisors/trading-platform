"""Plotly chart builders for the Streamlit dashboard."""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.backtesting.results import BacktestResults, Trade
from src.analysis.indicators import calc_rsi as _calc_rsi, calc_stoch as _calc_stoch
from src.analysis.zigzag import calc_zigzag as _calc_zigzag, assign_swing_labels as _assign_swing_labels

# Re-exported under their old underscore-prefixed names (ui/report.py imports
# these from this module) -- the actual logic now lives in src/analysis/ so
# the FastAPI backend can share it without forking. See src/analysis/zigzag.py
# and src/analysis/indicators.py for the implementations.


_SWING_COLORS = ["#f0c040", "#bb86fc", "#42a5f5", "#66bb6a"]


_GREEN = "#26a69a"
_RED   = "#ef5350"
_BLUE  = "#2196f3"
_BG    = "#1e1e2e"
_GRID  = "#2a2a3e"

# Pass this to every st.plotly_chart() call so scroll-to-zoom works everywhere.
CHART_CONFIG = {
    "scrollZoom": True,           # mouse-wheel zooms the chart
    "displayModeBar": True,       # always show toolbar (not just on hover)
    "modeBarButtonsToRemove": [   # strip noisy buttons, keep useful ones
        "lasso2d", "select2d", "autoScale2d",
    ],
    "modeBarButtonsToAdd": ["hoverclosest", "hovercompare"],
    "toImageButtonOptions": {
        "format": "png", "filename": "autotrader_chart",
        "height": 800, "width": 1600, "scale": 2,
    },
}

# Quick-jump range selector shown above the x-axis.
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
    font=dict(color="#cdd6f4", size=11),
    x=0, y=1.02, xanchor="left",
)

_SPIKE = dict(
    showspikes=True,
    spikemode="across",
    spikesnap="cursor",
    spikethickness=1,
    spikedash="dot",
    spikecolor="#6b6b8a",
)


def _base_layout(title: str, height: int = 500) -> dict:
    return dict(
        title=dict(text=title, font=dict(size=14, color="#cdd6f4")),
        paper_bgcolor=_BG,
        plot_bgcolor=_BG,
        font=dict(color="#cdd6f4"),
        dragmode="pan",           # left-click drag pans; scroll-wheel zooms
        hovermode="x unified",    # single crosshair across all subplots
        legend=dict(bgcolor="rgba(0,0,0,0.3)", borderwidth=0),
        margin=dict(l=60, r=12, t=36, b=8),
        height=height,
        autosize=True,
        newshape=dict(line_color="#ffab40"),
        modebar=dict(bgcolor="rgba(0,0,0,0)", color="#6b6b8a", activecolor="#cdd6f4"),
    )


def candlestick_with_trades(
    results: BacktestResults,
    max_bars: int = 400,
    show_zigzag: bool = False,
    zigzag_dev_3: float = 0.003,
    zigzag_dev_10: float = 0.003,
) -> go.Figure:
    """
    Candlestick + EMA overlays + trade markers.
    Sub-panels (replacing volume): RSI(2) | Stoch K/D | RSI(13)
    """
    full_df = results.price_data  # full dataset — used for trade marker lookup
    df = full_df.copy()
    # Downsample candles only when the dataset is very large
    if len(df) > max_bars * 3:
        step = max(1, len(df) // max_bars)
        df = df.iloc[::step]
    trades = results.trades
    # Use the FULL index (pre-downsample) so markers always appear
    full_idx_set = set(full_df.index)

    # ── Compute indicators ────────────────────────────────────────────
    # Use full_df for indicators so ZigZag pivot alignment is exact
    rsi2   = _calc_rsi(full_df["close"], 2)
    rsi13  = _calc_rsi(full_df["close"], 13)
    stk, std = _calc_stoch(full_df["high"], full_df["low"], full_df["close"])
    # Downsample indicators to match the (possibly thinned) candle series
    rsi2  = rsi2.reindex(df.index, method="nearest")
    rsi13 = rsi13.reindex(df.index, method="nearest")
    stk   = stk.reindex(df.index, method="nearest")
    std   = std.reindex(df.index, method="nearest")

    # ── Layout: 4 rows ────────────────────────────────────────────────
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        row_heights=[0.55, 0.15, 0.15, 0.15],
        vertical_spacing=0.035,
    )

    # ── Row 1: Candlestick ────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        name="Price",
        increasing_line_color=_GREEN, decreasing_line_color=_RED,
        showlegend=False,
        hoverlabel=dict(bgcolor=_BG),
    ), row=1, col=1)

    for span, color in [(9, "#ffab40"), (21, "#80cbc4")]:
        ema = df["close"].ewm(span=span, adjust=False).mean()
        fig.add_trace(go.Scatter(
            x=df.index, y=ema, name=f"EMA{span}",
            line=dict(color=color, width=1.2),
        ), row=1, col=1)

    # ── ZigZag overlay with per-swing numbering (resets at each new swing) ──
    zz = pd.DataFrame()
    zz3 = pd.DataFrame()
    if show_zigzag:
        zz  = _calc_zigzag(full_df["high"], full_df["low"], full_df["close"], deviation=zigzag_dev_10, legs=10)
        zz3 = _calc_zigzag(full_df["high"], full_df["low"], full_df["close"], deviation=zigzag_dev_3,  legs=3)

        # ── 3-leg ZigZag: yellow dotted line (short-term) ──
        if not zz3.empty:
            fig.add_trace(go.Scatter(
                x=zz3.index, y=zz3["price"],
                name="ZigZag (3L)", mode="lines",
                line=dict(color="#f0c040", width=1.2, dash="dot"),
                showlegend=True, hoverinfo="skip",
            ), row=1, col=1)
            for ptype, color in (("H", "#ff6b6b"), ("L", "#69f0ae")):
                pts = zz3[zz3["type"] == ptype]
                if not pts.empty:
                    fig.add_trace(go.Scatter(
                        x=pts.index, y=pts["price"],
                        mode="markers",
                        marker=dict(symbol="circle", size=6, color=color,
                                    line=dict(color="white", width=1)),
                        showlegend=False,
                        hovertemplate=f"<b>{'High' if ptype=='H' else 'Low'} (3L)</b><br>%{{x}}<br>@ %{{y:.2f}}<extra></extra>",
                    ), row=1, col=1)

        if not zz.empty:
            # Swing 1 always starts at the FIRST candle of the selected date range.
            zz = _assign_swing_labels(zz)

        if not zz.empty:
            # ── 10-leg ZigZag: yellow dotted line (long-term) ──
            fig.add_trace(go.Scatter(
                x=zz.index, y=zz["price"],
                name="ZigZag (10L)", mode="lines",
                line=dict(color="#2196f3", width=1.5, dash="dot"),
                showlegend=True, hoverinfo="skip",
            ), row=1, col=1)

            # ── Swing boxes: dotted boundary spanning ALL 4 panels, with a
            #    "SWING N (X.1 to X.N)" header well above the price chart so
            #    it clears the title/range-selector, staggered on two height
            #    levels so adjacent narrow swings don't collide horizontally ──
            swing_groups = list(zz.groupby("swing"))
            for i, (swing_num, grp) in enumerate(swing_groups):
                x0 = grp.index.min()
                x1 = swing_groups[i + 1][1].index.min() if i + 1 < len(swing_groups) else df.index.max()
                color = _SWING_COLORS[(swing_num - 1) % len(_SWING_COLORS)]

                # Dotted boundary outline around the swing region (no fill tint)
                fig.add_shape(
                    type="rect", xref="x", yref="paper",
                    x0=x0, x1=x1, y0=0, y1=1,
                    fillcolor="rgba(0,0,0,0)",
                    line=dict(color=color, width=1.5, dash="dot"),
                    layer="below",
                )
                # "Swing N" + range, sitting right above the dotted boundary —
                # all headers on the SAME single line (no up/down stagger)
                first_label = grp["label"].iloc[0]
                last_label  = grp["label"].iloc[-1]
                x_mid = grp.index[len(grp) // 2]
                fig.add_annotation(
                    x=x_mid, y=1.005, xref="x", yref="paper", yanchor="bottom",
                    text=f"<b>Swing {swing_num}</b><br>({first_label} to {last_label})",
                    showarrow=False, font=dict(color=color, size=11),
                    align="center",
                )
                # Gold star marking the start of each new swing
                fig.add_trace(go.Scatter(
                    x=[x0], y=[grp["price"].iloc[0]],
                    mode="markers", marker=dict(symbol="star", size=10, color=color,
                                                 line=dict(color="white", width=0.5)),
                    showlegend=False, hoverinfo="skip",
                ), row=1, col=1)

            # ── Decimal-labeled circles on the price chart ────────────────
            for ptype, color in (("H", _RED), ("L", _GREEN)):
                pts = zz[zz["type"] == ptype]
                if pts.empty:
                    continue
                fig.add_trace(go.Scatter(
                    x=pts.index, y=pts["price"],
                    name="Swing High" if ptype == "H" else "Swing Low",
                    mode="markers+text",
                    marker=dict(symbol="circle", size=30,
                                color=_BG,
                                line=dict(color=color, width=1.8)),
                    text=pts["label"], textposition="middle center",
                    textfont=dict(color="white", size=9, family="Arial"),
                    hovertemplate="<b>Swing %{text}</b><br>%{x}<br>@ %{y:.2f}<extra></extra>",
                ), row=1, col=1)

            # ── Same decimal labels mirrored on RSI(2), Stoch, RSI(13) ────
            # bfill first: early-session pivots can fall inside an indicator's
            # warm-up window (Stoch needs 14 bars, RSI13 needs 13) where the
            # value is still NaN -- that silently drops the marker and makes
            # the panel look like it starts at 1.1 instead of 1.0.
            rsi2_s  = rsi2.bfill().reindex(zz.index, method="nearest")
            stk_s   = stk.bfill().reindex(zz.index, method="nearest")
            rsi13_s = rsi13.bfill().reindex(zz.index, method="nearest")
            border_colors = [_RED if t == "H" else _GREEN for t in zz["type"]]

            for row_n, vals in ((2, rsi2_s), (3, stk_s), (4, rsi13_s)):
                fig.add_trace(go.Scatter(
                    x=zz.index, y=vals.values,
                    mode="markers+text",
                    marker=dict(size=26,
                                color=_BG,
                                line=dict(color=border_colors, width=1.8)),
                    text=zz["label"], textposition="middle center",
                    textfont=dict(size=8, color="white", family="Arial"),
                    showlegend=False,
                    cliponaxis=False,
                    hovertemplate="<b>Swing %{text}</b><br>%{y:.1f}<extra></extra>",
                ), row=row_n, col=1)

    # Trade entry / exit markers
    full_idx_set = set(df.index)
    long_entries  = [t for t in trades if t.direction == "LONG"  and t.entry_time in full_idx_set]
    short_entries = [t for t in trades if t.direction == "SHORT" and t.entry_time in full_idx_set]
    exits         = [t for t in trades if t.exit_time is not None and t.exit_time in full_idx_set]

    if long_entries:
        fig.add_trace(go.Scatter(
            x=[t.entry_time for t in long_entries],
            y=[t.entry_price * 0.9985 for t in long_entries],
            mode="markers",
            marker=dict(symbol="triangle-up", size=13, color=_GREEN,
                        line=dict(color="white", width=1)),
            name="Long Entry",
            hovertemplate="<b>LONG ENTRY</b><br>%{x}<br>@ %{y:.2f}<extra></extra>",
        ), row=1, col=1)

    if short_entries:
        fig.add_trace(go.Scatter(
            x=[t.entry_time for t in short_entries],
            y=[t.entry_price * 1.0015 for t in short_entries],
            mode="markers",
            marker=dict(symbol="triangle-down", size=13, color=_RED,
                        line=dict(color="white", width=1)),
            name="Short Entry",
            hovertemplate="<b>SHORT ENTRY</b><br>%{x}<br>@ %{y:.2f}<extra></extra>",
        ), row=1, col=1)

    if exits:
        exit_colors = [_GREEN if t.pnl >= 0 else _RED for t in exits]
        fig.add_trace(go.Scatter(
            x=[t.exit_time for t in exits],
            y=[t.exit_price for t in exits],
            mode="markers",
            marker=dict(symbol="x", size=12, color=exit_colors,
                        line=dict(color=exit_colors, width=2)),
            name="Exit",
            customdata=[(f"${t.pnl:,.0f}", t.direction) for t in exits],
            hovertemplate=(
                "<b>EXIT (%{customdata[1]})</b><br>"
                "%{x}<br>@ %{y:.2f}<br>"
                "P&L: %{customdata[0]}<extra></extra>"
            ),
        ), row=1, col=1)

    for t in trades:
        if t.exit_time is None:
            continue
        if t.entry_time not in full_idx_set or t.exit_time not in full_idx_set:
            continue
        color = _GREEN if t.pnl >= 0 else _RED
        fig.add_trace(go.Scatter(
            x=[t.entry_time, t.exit_time],
            y=[t.entry_price, t.exit_price],
            mode="lines",
            line=dict(color=color, width=1, dash="dot"),
            showlegend=False, hoverinfo="skip",
        ), row=1, col=1)

    # ── Row 2: RSI(2) ─────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=df.index, y=rsi2,
        name="RSI(2)", line=dict(color="#ce93d8", width=1.4),
        hovertemplate="RSI(2): %{y:.1f}<extra></extra>",
    ), row=2, col=1)
    # Overbought / oversold bands
    for lvl, color in [(94, _RED), (2, _GREEN)]:
        fig.add_hline(y=lvl, line=dict(color=color, dash="dash", width=0.8),
                      row=2, col=1)

    # ── Row 3: Stochastic K & D ───────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=df.index, y=stk,
        name="%K", line=dict(color="#4fc3f7", width=1.4),
        hovertemplate="%%K: %{y:.1f}<extra></extra>",
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=std,
        name="%D", line=dict(color="#f48fb1", width=1.2, dash="dot"),
        hovertemplate="%%D: %{y:.1f}<extra></extra>",
    ), row=3, col=1)
    for lvl, color in [(80, _RED), (20, _GREEN)]:
        fig.add_hline(y=lvl, line=dict(color=color, dash="dash", width=0.8),
                      row=3, col=1)

    # ── Row 4: RSI(13) ────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=df.index, y=rsi13,
        name="RSI(13)", line=dict(color="#ffcc80", width=1.4),
        hovertemplate="RSI(13): %{y:.1f}<extra></extra>",
    ), row=4, col=1)
    for lvl, color in [(70, _RED), (30, _GREEN)]:
        fig.add_hline(y=lvl, line=dict(color=color, dash="dash", width=0.8),
                      row=4, col=1)

    # ── Layout ────────────────────────────────────────────────────────
    _ylabel = dict(font=dict(size=9, color="#8b8ba0"), standoff=4)
    layout = _base_layout(f"{results.symbol} — {results.strategy_name}", height=920)
    _has_swing_headers = show_zigzag and not zz.empty
    if _has_swing_headers:
        layout["margin"] = dict(l=60, r=12, t=145, b=8)  # room for range selector + Swing N headers
    # Visual stacking top-to-bottom: title -> range selector -> swing headers
    # (sitting right above the dotted boundary, no big gap) -> chart
    _rangeselector = {**_RANGE_SELECTOR, "y": 1.15} if _has_swing_headers else _RANGE_SELECTOR
    layout.update(
        xaxis=dict(
            gridcolor=_GRID, showgrid=True,
            rangeslider_visible=False,
            rangeselector=_rangeselector,
            **_SPIKE,
        ),
        xaxis2=dict(gridcolor=_GRID, **_SPIKE),
        xaxis3=dict(gridcolor=_GRID, **_SPIKE),
        xaxis4=dict(gridcolor=_GRID, **_SPIKE),
        yaxis =dict(gridcolor=_GRID, showgrid=True,
                    title=dict(text="Price",   **_ylabel), fixedrange=False),
        yaxis2=dict(gridcolor=_GRID, showgrid=True,
                    title=dict(text="RSI(2)",  **_ylabel), fixedrange=True, range=[0, 100]),
        yaxis3=dict(gridcolor=_GRID, showgrid=True,
                    title=dict(text="Stoch",   **_ylabel), fixedrange=True, range=[0, 100]),
        yaxis4=dict(gridcolor=_GRID, showgrid=True,
                    title=dict(text="RSI(13)", **_ylabel), fixedrange=True, range=[0, 100]),
    )
    fig.update_layout(**layout)
    return fig


def win_loss_donut(results: BacktestResults) -> go.Figure:
    """Win/Loss split as a donut — status colors only (green=good, red=critical),
    never reused as a categorical identity color elsewhere on the dashboard."""
    wins, losses = results.winning_trades, results.losing_trades
    fig = go.Figure(go.Pie(
        labels=["Wins", "Losses"],
        values=[wins, losses] if (wins + losses) else [1, 0],
        hole=0.65,
        marker=dict(colors=[_GREEN, _RED], line=dict(color=_BG, width=3)),
        textinfo="none",
        hovertemplate="<b>%{label}</b><br>%{value} trades (%{percent})<extra></extra>",
        sort=False,
    ))
    fig.add_annotation(
        text=f"<b>{results.win_rate:.0f}%</b><br><span style='font-size:11px'>Win Rate</span>",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=22, color="#cdd6f4"),
    )
    layout = _base_layout("Win / Loss", height=330)
    layout["margin"] = dict(l=20, r=20, t=45, b=10)
    layout.update(showlegend=True,
                  legend=dict(orientation="h", y=-0.08, bgcolor="rgba(0,0,0,0)"))
    fig.update_layout(**layout)
    return fig


def equity_curve(results: BacktestResults) -> go.Figure:
    eq = results.equity_curve
    drawdown = (eq - eq.cummax()) / eq.cummax() * 100

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.04,
    )

    fig.add_trace(go.Scatter(
        x=eq.index, y=eq.values,
        name="Portfolio Value",
        line=dict(color=_BLUE, width=2),
        fill="tozeroy", fillcolor="rgba(33,150,243,0.1)",
    ), row=1, col=1)

    fig.add_hline(y=results.initial_capital,
                  line=dict(color="gray", dash="dash", width=1), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=drawdown.index, y=drawdown.values,
        name="Drawdown %",
        line=dict(color=_RED, width=1.5),
        fill="tozeroy", fillcolor="rgba(239,83,80,0.2)",
    ), row=2, col=1)

    layout = _base_layout("Equity Curve & Drawdown", height=460)
    layout.update(
        xaxis=dict(
            gridcolor=_GRID, showgrid=True,
            rangeselector=_RANGE_SELECTOR,
            **_SPIKE,
        ),
        xaxis2=dict(gridcolor=_GRID, showgrid=True, **_SPIKE),
        yaxis=dict(gridcolor=_GRID, showgrid=True, title="Portfolio Value ($)",
                   fixedrange=False),
        yaxis2=dict(gridcolor=_GRID, showgrid=True, title="Drawdown (%)",
                    fixedrange=False),
    )
    fig.update_layout(**layout)
    return fig


def pnl_distribution(results: BacktestResults) -> go.Figure:
    if not results.trades:
        return go.Figure()
    pnls = [t.pnl for t in results.trades]
    colors = [_GREEN if p >= 0 else _RED for p in pnls]

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=pnls, nbinsx=30, marker_color=colors,
        name="Trade P&L",
        hovertemplate="P&L: $%{x:.0f}<br>Count: %{y}<extra></extra>",
    ))
    fig.add_vline(x=0, line=dict(color="white", dash="dash", width=1))

    layout = _base_layout("Trade P&L Distribution", height=330)
    layout.update(
        xaxis=dict(title="P&L ($)", gridcolor=_GRID),
        yaxis=dict(title="Count", gridcolor=_GRID, fixedrange=False),
        dragmode="zoom",   # histogram: box-zoom makes more sense than pan
    )
    fig.update_layout(**layout)
    return fig


def monthly_returns_heatmap(results: BacktestResults) -> go.Figure:
    if results.equity_curve.empty:
        return go.Figure()

    eq = results.equity_curve.resample("ME").last()
    monthly_ret = eq.pct_change() * 100
    monthly_ret.index = monthly_ret.index.to_period("M")

    years = sorted(set(p.year for p in monthly_ret.index))
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    z, text = [], []
    for year in years:
        row, row_text = [], []
        for m in range(1, 13):
            period = pd.Period(year=year, month=m, freq="M")
            val = monthly_ret.get(period, None)
            row.append(val if val is not None else None)
            row_text.append(f"{val:.1f}%" if val is not None else "")
        z.append(row)
        text.append(row_text)

    fig = go.Figure(go.Heatmap(
        z=z, x=month_names, y=[str(y) for y in years],
        text=text, texttemplate="%{text}",
        colorscale=[[0, _RED], [0.5, "#2a2a3e"], [1, _GREEN]],
        zmid=0, showscale=True,
        hovertemplate="%{y} %{x}: <b>%{z:.1f}%</b><extra></extra>",
    ))

    layout = _base_layout("Monthly Returns (%)", height=max(220, 65 * len(years) + 100))
    layout.update(dragmode="zoom")
    fig.update_layout(**layout)
    return fig
