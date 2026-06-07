"""Plotly chart builders for the Streamlit dashboard."""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.backtesting.results import BacktestResults, Trade


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
        margin=dict(l=65, r=30, t=55, b=45),
        height=height,
        newshape=dict(line_color="#ffab40"),
        modebar=dict(bgcolor="rgba(0,0,0,0)", color="#6b6b8a", activecolor="#cdd6f4"),
    )


def candlestick_with_trades(results: BacktestResults, max_bars: int = 400) -> go.Figure:
    """
    Candlestick chart with EMA overlays and entry/exit markers.
    - Scroll to zoom, click-drag to pan
    - Range-selector buttons for 1D / 5D / 1M / 3M / All
    - Crosshair cursor across subplots
    """
    df = results.price_data.tail(max_bars).copy()
    trades = results.trades

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.75, 0.25],
        vertical_spacing=0.03,
    )

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

    long_entries  = [t for t in trades if t.direction == "LONG"  and t.entry_time in df.index]
    short_entries = [t for t in trades if t.direction == "SHORT" and t.entry_time in df.index]
    exits         = [t for t in trades if t.exit_time is not None and t.exit_time in df.index]

    if long_entries:
        fig.add_trace(go.Scatter(
            x=[t.entry_time for t in long_entries],
            y=[t.entry_price * 0.9985 for t in long_entries],
            mode="markers",
            marker=dict(symbol="triangle-up", size=13, color=_GREEN,
                        line=dict(color="white", width=1)),
            name="Long Entry",
            hovertemplate="<b>LONG ENTRY</b><br>%{x}<br>Price: %{y:.2f}<extra></extra>",
        ), row=1, col=1)

    if short_entries:
        fig.add_trace(go.Scatter(
            x=[t.entry_time for t in short_entries],
            y=[t.entry_price * 1.0015 for t in short_entries],
            mode="markers",
            marker=dict(symbol="triangle-down", size=13, color=_RED,
                        line=dict(color="white", width=1)),
            name="Short Entry",
            hovertemplate="<b>SHORT ENTRY</b><br>%{x}<br>Price: %{y:.2f}<extra></extra>",
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
                "%{x}<br>Price: %{y:.2f}<br>"
                "P&L: %{customdata[0]}<extra></extra>"
            ),
        ), row=1, col=1)

    for t in trades:
        if t.exit_time is None or t.entry_time not in df.index or t.exit_time not in df.index:
            continue
        color = _GREEN if t.pnl >= 0 else _RED
        fig.add_trace(go.Scatter(
            x=[t.entry_time, t.exit_time],
            y=[t.entry_price, t.exit_price],
            mode="lines",
            line=dict(color=color, width=1, dash="dot"),
            showlegend=False, hoverinfo="skip",
        ), row=1, col=1)

    vol_colors = [_GREEN if c >= o else _RED
                  for o, c in zip(df["open"], df["close"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["volume"],
        name="Volume", marker_color=vol_colors, showlegend=False,
    ), row=2, col=1)

    layout = _base_layout(f"{results.symbol} — {results.strategy_name}", height=640)
    layout.update(
        xaxis=dict(
            gridcolor=_GRID, showgrid=True,
            rangeslider_visible=False,
            rangeselector=_RANGE_SELECTOR,
            **_SPIKE,
        ),
        xaxis2=dict(gridcolor=_GRID, showgrid=True, **_SPIKE),
        yaxis=dict(gridcolor=_GRID, showgrid=True, title="Price",
                   fixedrange=False),
        yaxis2=dict(gridcolor=_GRID, showgrid=True, title="Volume",
                    fixedrange=True),   # don't zoom volume panel vertically
    )
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
