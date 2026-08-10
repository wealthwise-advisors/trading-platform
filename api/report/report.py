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
from api.report.wave_layout import tier_filter_run, declutter_static, split_into_segments, display_wave, label_segments


_G      = "#3fb950"
_R      = "#f85149"
_B      = "#58a6ff"
_BG     = "#0d1117"
_GRID   = "#21262d"
_SURFACE = "#161b22"
_TEXT   = "#e6edf3"
_MUTED  = "#8b949e"
_MARKER_BG = "#1e1e2e"  # solid fill so boundary lines don't bleed through circles

# Elliott Wave chart -- cycled per detected structure (segment), same
# palette as ElliottWaveChart.tsx's SEGMENT_COLORS (keep in sync).
_EW_RUN_COLORS = ["#2196f3", "#f0c040", "#7ee787", "#c77dff", "#4cc9f0", "#ff8a65"]
# Uniform label styling, matching ElliottWaveChart.tsx's LABEL_STYLE --
# Wave 1 through Wave 5 must all be EQUALLY visible, not a tiered
# hierarchy. tier_of() is still used for collision-priority ordering only
# (see wave_layout.py's module docstring), never for size/weight/opacity.
_EW_LABEL_STYLE = dict(font_size=12, marker_size=6, opacity=1.0, bold=True)

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

# Default initial view for the candlestick chart -- see _candlestick_chart's
# _initial_range for why this exists (avoids opening on the fully-crammed
# "All" view for anything longer than a few weeks of bars). ~150 bars reads
# comfortably regardless of timeframe (5m, 1h, 1d, ...) -- the "All" range
# button still shows everything, this only changes the FIRST render.
_DEFAULT_VIEW_BARS = 150

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
    # Default view: the most recent DEFAULT_VIEW_BARS bars, not the whole
    # series -- with no explicit range, Plotly renders every bar (and every
    # swing header, which are pinned to a shared paper-space strip) crammed
    # into one view, which for anything longer than a few weeks makes the
    # candles themselves shrink to invisible slivers behind the swing
    # overlay. The full series is still one click away via the "All" range
    # button (unchanged) -- this only changes what's shown on first render.
    _initial_range = (
        [df.index[max(0, len(df) - _DEFAULT_VIEW_BARS)], df.index[-1]]
        if len(df) > _DEFAULT_VIEW_BARS else None
    )
    fig.update_layout(
        **_base,
        xaxis=dict(
            gridcolor=_GRID, rangeslider_visible=False,
            rangeselector={**_RANGE_SELECTOR, "y": _rs_y},
            range=_initial_range,
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
# Elliott Wave chart -- static-report counterpart of
# web/src/components/charts/ElliottWaveChart.tsx. Missing from the export
# until 2026-07-17 (the live React tab had it, the HTML export didn't).
# Renders one chart per degree ("primary"/"minor") at a single fixed detail
# level (see wave_layout.py) since there's no client-side zoom handler here
# to progressively reveal more -- the exported chart is still pannable/
# zoomable via Plotly's native controls, it just doesn't re-declutter live.
# ─────────────────────────────────────────────────────────────────────────────

def _group_wave_runs(sequence):
    """Same grouping rule as ElliottWaveChart.tsx's groupRuns(): a new run
    starts every time the count resets back to Wave 1. Input to
    split_into_segments(), which splits each run further into its own
    genuine structural segments (see that function's docstring)."""
    runs = []
    for w in sequence:
        if w.wave == "1" or not runs:
            runs.append([w])
        else:
            runs[-1].append(w)
    return runs


def _elliott_wave_chart(df: pd.DataFrame, analysis: WaveAnalysis, degree_name: str,
                        nested: bool, symbol: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color=_G, decreasing_line_color=_R,
        name="Price", showlegend=False,
    ))

    runs = _group_wave_runs(analysis.wave_sequence)
    all_items: list[dict] = []
    segments: list[list[dict]] = []
    # Raw (real-label) segments, kept parallel to `segments` (same index)
    # so label_segments() can compute each segment's real type from the
    # UNMODIFIED labels -- the loop below overwrites "wave" with the
    # display-transformed value (uppercased letters, digits unchanged),
    # which would otherwise lose that signal. See label_segments()'s
    # docstring for the label/range/naming design.
    raw_segments: list[list[dict]] = []

    for run in runs:
        raw_items = [
            {
                "t": df.index[w.swing.index].timestamp(),
                "ts": df.index[w.swing.index],
                "price": w.price,
                "wave": w.wave,
                "sub": w.sub,
                "kind": w.swing.kind.value,
            }
            for w in run
        ]
        # Real Elliott Wave notation (numbers for motive waves, letters for
        # corrective waves -- see wave_layout.py's module docstring):
        # splits this run into segments at every genuine structural
        # boundary; each item's displayed "wave" is display_wave() applied
        # to its own real label (uppercases corrective letters, passes
        # digits through) -- zero engine changes, analysis.wave_sequence
        # itself is untouched, this rewrites only the per-item dicts built
        # for this chart.
        for seg in split_into_segments(raw_items):
            raw_segments.append(seg)
            items = []
            for it0 in seg:
                it = dict(it0)
                it["wave"] = display_wave(it0["wave"])
                items.append(it)
            segments.append(items)

    # This chart is always solo (report.py has no merged Global+Nested
    # mode) -- always 1-indexed "Wave N", matching ElliottWaveChart.tsx's
    # solo mode.
    segment_labels = label_segments(raw_segments, zero_indexed=False)

    for i, items in enumerate(segments):
        color = _EW_RUN_COLORS[i % len(_EW_RUN_COLORS)]
        for it in items:
            it["color"] = color
        all_items.extend(items)

    # Numbers only (required, reversing an earlier "Structure N" header/
    # legend addition -- see ElliottWaveChart.tsx's module docstring for the
    # full history): the ONLY things distinguishing one detected structure
    # from the next are color, cycled per segment, a full boxed region
    # around each structure's own price+time extent, and a header -- a
    # plain "Wave N" for impulse/diagonal segments, or the actual detected
    # corrective type (ABC Correction/Triangle/WXY Correction/Triple Three,
    # see wave_layout.py's describe_structure_type(), 2026-07-20) for
    # corrective segments, never anything about the classical wave position
    # inside it, which the "1".."5" numbers below already say). No legend
    # entries, no colored fill.
    #
    # FULL WAVE REGION, 2026-07-19 -- a first attempt at this box used
    # xref="x"/yref="paper", y0=0, y1=1 (full plot height), copying
    # charts.py's own ZigZag swing rectangles literally -- but that's wrong
    # for THIS chart: every box's top/bottom edges then land at the exact
    # same two lines (the very top and bottom of the whole plot), since
    # "paper" y is chart-wide, not per-box. All those coincident top/bottom
    # edges visually merge into what looks like just two horizontal lines
    # shared by the whole chart, leaving only each box's own left/right
    # edges as visually distinct elements -- reported back, correctly, as
    # "you only added two vertical dashed lines." Swing regions get away
    # with paper-y boxes because they're meant to tile the FULL vertical
    # height of a shared multi-panel chart; an Elliott structure's box
    # instead needs to hug ONLY that structure's own price swing. Fixed by
    # switching to yref="y" (data/price space): y0/y1 are now THIS
    # segment's own min/max price, padded a little so the box doesn't clip
    # flush against the extreme points. fillcolor stays fully transparent
    # (rgba(0,0,0,0), NOT a tinted fill -- an earlier translucent-color
    # version was explicitly rejected as unwanted background noise), dotted
    # border in the segment's own color.
    #
    # The header is "Wave N", anchored just above THIS box's own top edge
    # (not a chart-wide shared strip, so it visibly "belongs" to its own
    # region) using the same collision-avoidance recipe validated for
    # ElliottWaveChart.tsx's per-peak headers: an ABSOLUTE time duration
    # (not a fraction of the visible range -- a header's pixel width
    # doesn't scale with how many weeks of history are on screen) compared
    # against EVERY recently-placed header (not just the immediate
    # predecessor, so a broken chain can't coincidentally land on a
    # different chain's tail), stacking collisions onto a shared rising
    # ceiling in DATA space (price units, never a raw pixel offset -- a
    # pixel offset on top of a different price anchor can get silently
    # cancelled by the price gap between two peaks). The step fraction
    # (0.15) is deliberately generous: since the y-axis auto-expands to fit
    # the tallest stacked header, a dense cluster's stack compresses the
    # effective pixels-per-price-unit for the WHOLE chart, so a step that
    # looks fine in isolation can still visually collide once other
    # clusters push the axis range taller -- confirmed by hand against real
    # multi-week data at 0.06 (too tight) before landing on 0.15.
    _HEADER_COLLISION_SECONDS = 24 * 60 * 60
    _HEADER_PRICE_STEP_FRACTION = 0.15
    box_price_span = (max(it["price"] for it in all_items) - min(it["price"] for it in all_items)) if all_items else 1.0
    box_price_span = box_price_span or 1.0
    placed_headers: list[dict] = []
    # How many times each corrective type occurs across this WHOLE
    # structure-set, so a type that recurs (e.g. three separate corrections)
    # gets a disambiguating "#N" suffix -- see label_segments()'s docstring.
    for i, items in enumerate(segments):
        if not items:
            continue
        color = _EW_RUN_COLORS[i % len(_EW_RUN_COLORS)]
        seg_start = items[0]["ts"]
        seg_end = items[-1]["ts"]
        x_mid = items[len(items) // 2]["ts"]
        x_mid_t = items[len(items) // 2]["t"]
        seg_prices = [it["price"] for it in items]
        price_min = min(seg_prices)
        price_max = max(seg_prices)
        # Floor RAISED 0.02 -> 0.06 (2026-07-26): the header's x-anchor is
        # this segment's OWN middle point (items[len(items)//2] below), which
        # for a 4-point run is literally the same swing as point label "3" --
        # confirmed directly against a real report's rendered annotations
        # (header at data-y 6892.2, point "3" at data-y 6876.0, same
        # timestamp). Point labels sit a FIXED 22px above/below their own
        # anchor (_EW_LABEL_STYLE-driven yshift in the per-point loop below),
        # a pixel budget that doesn't shrink just because this particular
        # segment's own price move is small -- the old 2% floor cleared that
        # 22px gap for large segments (where the *0.15 term dominates instead)
        # but not for small ones, which is exactly why only the tiny early
        # structures (not the big Wave-1-to-11 run) showed the collision.
        box_pad = max((price_max - price_min) * 0.15, box_price_span * 0.06)

        # Full detail, every point, always (see wave_layout.py's module
        # docstring, bug 1) -- tier_filter_run is now a passthrough, kept
        # as a named call so this reads as deliberate, not forgotten.
        visible = tier_filter_run(items)
        opacities = [0.45 if it["sub"] == 2 else 1.0 for it in visible]
        labels = [it["wave"] for it in visible]
        technical = segment_labels[i]["technical"]

        # This segment's line extended to ALSO touch the very first point of
        # the NEXT segment (if any) -- confirmed design (2026-07-20, matching
        # ElliottWaveChart.tsx's identical fix): the connector between two
        # structures reads as a continuous colored path in the OUTGOING
        # segment's own color, not a separate neutral line, so the handoff
        # to the next (differently colored) structure is seamless. Split
        # into its own trace (was combined "lines+markers") specifically so
        # this extra endpoint doesn't also draw a duplicate marker/label at
        # the next segment's first point -- that segment already draws its
        # own marker there.
        next_first = segments[i + 1][0] if i + 1 < len(segments) else None
        line_ts = [it["ts"] for it in visible]
        line_price = [it["price"] for it in visible]
        if next_first is not None:
            line_ts.append(next_first["ts"])
            line_price.append(next_first["price"])
        fig.add_trace(go.Scatter(
            x=line_ts, y=line_price,
            mode="lines",
            line=dict(color=color, width=1.4),
            showlegend=False, hoverinfo="skip",
        ))
        # The real Elliott type name (e.g. "Triple Three"), not shown on the
        # header anymore per the simplified naming (see label_segments()'s
        # docstring), surfaces here on hover instead -- available on
        # demand, not deleted. Numeric segments (technical is None) keep
        # the original "Wave N" phrasing.
        hover = (
            f"{technical} — point %{{text}}<br>%{{x}}<br>@ %{{y:.2f}}<extra></extra>"
            if technical else "Wave %{text}<br>%{x}<br>@ %{y:.2f}<extra></extra>"
        )
        fig.add_trace(go.Scatter(
            x=[it["ts"] for it in visible], y=[it["price"] for it in visible],
            mode="markers",
            marker=dict(size=_EW_LABEL_STYLE["marker_size"], color=color, opacity=opacities,
                        line=dict(color=_BG, width=0.5)),
            showlegend=False,
            hovertemplate=hover,
            text=labels,
        ))

        fig.add_shape(
            type="rect", xref="x", yref="y",
            x0=seg_start, x1=seg_end, y0=price_min - box_pad, y1=price_max + box_pad,
            fillcolor="rgba(0,0,0,0)",
            line=dict(color=color, width=1.3, dash="dot"), opacity=0.85,
            layer="below",
        )

        colliders = [p for p in placed_headers if abs(p["t"] - x_mid_t) < _HEADER_COLLISION_SECONDS]
        header_y = (
            max(price_max + box_pad, max(c["y"] for c in colliders) + _HEADER_PRICE_STEP_FRACTION * box_price_span)
            if colliders else price_max + box_pad
        )
        placed_headers.append({"t": x_mid_t, "y": header_y})

        header_label = segment_labels[i]["display"]

        fig.add_annotation(
            x=x_mid, y=header_y, xref="x", yref="y", yanchor="bottom",
            text=f"<b>{header_label}</b>", showarrow=False,
            font=dict(color=color, size=10), align="center",
            yshift=4,
        )

    if all_items:
        t_span = max(it["t"] for it in all_items) - min(it["t"] for it in all_items)
        p_span = max(it["price"] for it in all_items) - min(it["price"] for it in all_items)
        # Never hides a candidate -- collisions fan outward via
        # stack_index instead (see wave_layout.py's module docstring, bug 1).
        shown = declutter_static(all_items, t_span, p_span)
        for it in shown:
            text = f"<b>{it['wave']}</b>" if _EW_LABEL_STYLE["bold"] else it["wave"]
            stack_gap = _EW_LABEL_STYLE["font_size"] + 3
            base_offset = 10 + _EW_LABEL_STYLE["font_size"] + it["stack_index"] * stack_gap
            fig.add_annotation(
                x=it["ts"], y=it["price"], xref="x", yref="y",
                text=text, showarrow=False,
                font=dict(color=it["color"], size=_EW_LABEL_STYLE["font_size"]),
                opacity=_EW_LABEL_STYLE["opacity"],
                yshift=base_offset if it["kind"] == "high" else -base_offset,
            )

    # _layout()'s "margin" key needs overriding here (more top space for the
    fig.update_layout(
        **_layout(f"{symbol} — {degree_name} degree Elliott Wave", height=520),
        showlegend=False,
        xaxis=dict(gridcolor=_GRID, rangeslider_visible=False,
                   rangeselector=_RANGE_SELECTOR, **_SPIKE),
        yaxis=dict(gridcolor=_GRID, title=dict(text="Price", font=dict(size=9, color=_MUTED))),
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
  <a href="#elliott-wave">🌊 Elliott Wave</a>
  <a href="#equity-curve">📈 Equity</a>
  <a href="#pnl-distribution">📈 P&amp;L</a>
  <a href="#monthly-returns">📅 Monthly</a>
  <a href="#trade-log">📋 Trade Log</a>
  <a href="#candlestick-patterns">🕯️ Candlesticks</a>
  <a href="#chart-patterns">📐 Chart Patterns</a>
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

<div class="section-title" id="elliott-wave"><span class="icon">🌊</span> Elliott Wave</div>
{chart_elliott}

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

    # Elliott Wave -- one chart per degree (primary, intermediate, minor,
    # ... down the ladder -- see wave_analysis.py's DEFAULT_DEGREE_LADDER),
    # same source (analyze_degrees) and same tier/color scheme as the live
    # React tab. Was missing from the export entirely until 2026-07-17. A
    # one-line description per chart (2026-07-21, matching
    # ElliottWavePanel.tsx's identical addition on the live side) --
    # name-based throughout, not hardcoded to any specific degree name, so
    # any ladder depth gets the same treatment automatically.
    def _elliott_description(name: str, degrees: dict) -> str:
        base = name.replace("_global", "")
        label = base[0].upper() + base[1:]
        if name.endswith("_global"):
            return f"Shows higher-level {label} structures across the entire chart."
        if f"{name}_global" in degrees:
            return f"Shows smaller {label} structures detected inside the larger trend."
        return "Shows the highest-level Elliott Wave structures detected for this timeframe."

    if not r.price_data.empty:
        degrees = analyze_degrees(r.price_data)

        def _elliott_chart_box(name: str, a) -> str:
            is_nested = name != "primary" and not name.endswith("_global")
            fig_div = _fig_to_div(_elliott_wave_chart(r.price_data, a, name, nested=is_nested, symbol=r.symbol))
            desc = _elliott_description(name, degrees)
            return (f'<div class="chart-box">{fig_div}'
                    f'<p style="color:#8b949e;font-size:0.8rem;padding:4px 8px 0">{desc}</p></div>')

        chart_elliott = "".join(_elliott_chart_box(name, a) for name, a in degrees.items())
    else:
        chart_elliott = '<p style="color:#8b949e;padding:12px">No price data available for wave analysis.</p>'

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
        chart_elliott=chart_elliott,
        chart_equity=chart_equity,
        chart_pnl=chart_pnl,
        chart_monthly=chart_monthly,
        trade_count=len(r.trades),
        trade_rows="\n".join(trade_rows),
        candlestick_patterns_table=candlestick_patterns_table,
        chart_patterns_table=chart_patterns_table,
    )

    if output_path:
        Path(output_path).write_text(html, encoding="utf-8")

    return html
