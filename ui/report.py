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
from ui.components.charts import (
    _calc_zigzag, _assign_swing_labels, _SWING_COLORS,
    _calc_rsi, _calc_stoch,
)

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

def _candlestick_chart(results: BacktestResults, zz_deviation: float = 0.015) -> go.Figure:
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

            color_map = {s: _SWING_COLORS[i % len(_SWING_COLORS)]
                         for i, s in enumerate(sorted(zz["swing"].unique()))}
            border_colors = [color_map[s] for s in zz["swing"]]

            # ZigZag dotted gold line on price panel
            fig.add_trace(go.Scatter(
                x=zz.index, y=zz["price"], mode="lines",
                line=dict(color="#f0c040", width=1.5, dash="dot"),
                name="ZigZag", showlegend=True,
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
                fig.add_annotation(
                    x=x_mid, y=1.005, xref="x", yref="paper", yanchor="bottom",
                    text=f"<b>Swing {swing_num}</b><br>({first_label} to {last_label})",
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
# HTML template
# ─────────────────────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0d1117; color: #e6edf3;
         font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
  .page {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}

  header {{ border-bottom: 1px solid #21262d; padding-bottom: 16px; margin-bottom: 20px; }}
  header h1 {{ font-size: 1.6rem; color: #58a6ff; }}
  header p  {{ color: #8b949e; font-size: 0.875rem; margin-top: 4px; }}
  .badge {{ display: inline-block; background: #21262d; border-radius: 4px;
            padding: 2px 10px; font-size: 0.78rem; color: #8b949e; margin-right: 8px; }}

  /* ── zoom/controls hint bar ── */
  .controls-hint {{
    display: flex; gap: 20px; flex-wrap: wrap; align-items: center;
    background: #161b22; border: 1px solid #21262d; border-radius: 8px;
    padding: 10px 16px; margin-bottom: 22px; font-size: 0.8rem; color: #8b949e;
  }}
  .controls-hint span {{ display: flex; align-items: center; gap: 6px; }}
  .kbd {{
    display: inline-block; background: #21262d; border: 1px solid #444;
    border-radius: 4px; padding: 1px 7px; font-size: 0.75rem;
    color: #cdd6f4; font-family: monospace;
  }}

  /* ── metric cards ── */
  .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr));
              gap: 12px; margin-bottom: 24px; }}
  .metric-card {{ background: #161b22; border: 1px solid #21262d; border-radius: 8px;
                  padding: 14px 16px; }}
  .metric-card .label {{ font-size: 0.72rem; color: #8b949e; text-transform: uppercase;
                          letter-spacing: 0.06em; margin-bottom: 4px; }}
  .metric-card .value {{ font-size: 1.35rem; font-weight: 600; }}
  .positive {{ color: #3fb950; }}
  .negative {{ color: #f85149; }}
  .neutral  {{ color: #e6edf3; }}

  /* ── section titles ── */
  .section-title {{ font-size: 0.78rem; font-weight: 700; color: #8b949e;
                    text-transform: uppercase; letter-spacing: 0.1em;
                    margin: 28px 0 10px; }}

  /* ── chart containers ── */
  .chart-box {{ background: #161b22; border: 1px solid #21262d; border-radius: 8px;
                padding: 4px; margin-bottom: 20px; overflow: hidden; }}

  /* ── trade log table ── */
  table {{ width: 100%; border-collapse: collapse; font-size: 0.83rem; }}
  thead tr {{ background: #21262d; }}
  th {{ padding: 8px 12px; text-align: left; color: #8b949e; font-weight: 600;
        font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; }}
  tbody tr {{ border-bottom: 1px solid #21262d; transition: background 0.1s; }}
  tbody tr:hover {{ background: #1c2128; }}
  td {{ padding: 7px 12px; }}
  .pnl-pos {{ color: #3fb950; font-weight: 600; }}
  .pnl-neg {{ color: #f85149; font-weight: 600; }}
  .dir-long  {{ color: #3fb950; }}
  .dir-short {{ color: #f85149; }}

  /* ── layout helpers ── */
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 768px) {{ .two-col {{ grid-template-columns: 1fr; }} }}

  footer {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid #21262d;
            color: #8b949e; font-size: 0.78rem; text-align: center; }}
</style>
</head>
<body>
<div class="page">

<header>
  <h1>{title}</h1>
  <p>
    <span class="badge">{symbol}</span>
    <span class="badge">{timeframe}</span>
    <span class="badge">{start} → {end}</span>
    <span class="badge">Generated {generated}</span>
  </p>
</header>

<!-- ── controls hint ── -->
<div class="controls-hint">
  <span>📊 <strong style="color:#cdd6f4">Chart Controls</strong></span>
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

<div class="section-title">Price Chart, Indicators &amp; Trades</div>
<div class="chart-box">{chart_candle}</div>

<div class="section-title">Equity Curve</div>
<div class="chart-box">{chart_equity}</div>

<div class="two-col">
  <div>
    <div class="section-title">P&amp;L Distribution</div>
    <div class="chart-box">{chart_pnl}</div>
  </div>
  <div>
    <div class="section-title">Monthly Returns</div>
    <div class="chart-box">{chart_monthly}</div>
  </div>
</div>

<div class="section-title">Trade Log &mdash; {trade_count} trades</div>
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

<footer>AutoTrader Backtest Report &mdash; {title} &mdash; {generated}</footer>
</div>
</body>
</html>
"""


def _metric_card(label: str, value: str, positive: bool | None = None) -> str:
    cls = "positive" if positive is True else ("negative" if positive is False else "neutral")
    return (
        f'<div class="metric-card">'
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
                         zz_deviation: float = 0.015) -> str:
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
    chart_candle  = _fig_to_div(_candlestick_chart(r, zz_deviation=zz_deviation), first=True)
    chart_equity  = _fig_to_div(_equity_chart(r))
    chart_pnl     = _fig_to_div(_pnl_hist(r))
    chart_monthly = _fig_to_div(_monthly_heatmap(r))

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
    )

    if output_path:
        Path(output_path).write_text(html, encoding="utf-8")

    return html
