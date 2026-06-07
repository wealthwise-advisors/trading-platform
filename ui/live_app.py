"""
AutoTrader — Live Replay Dashboard

Replays a backtest bar-by-bar so you can watch candles arrive,
see trades trigger in real-time, and observe metrics update live.

Run:  streamlit run ui/live_app.py
"""

import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, date
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.data.csv_provider import CSVDataProvider
from src.data.sample_data import generate_sample_data
from src.strategies import MACrossoverStrategy, RSIMeanReversionStrategy, BreakoutStrategy, RSIDivergenceStrategy
from src.backtesting.replay_engine import ReplayEngine, FrameState
from src.backtesting.results import Trade
from ui.components.charts import CHART_CONFIG, _RANGE_SELECTOR, _SPIKE

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AutoTrader — Live",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  [data-testid="stAppViewContainer"] { background: #0d1117; }
  [data-testid="stSidebar"] { background: #161b22; }
  h1, h2, h3 { color: #e6edf3; }
  .stMetric label { color: #8b949e; font-size: 0.78rem !important; }
  .stMetric [data-testid="metric-container"] > div:first-child { font-size: 0.78rem; }
  div[data-testid="stMetricValue"] { font-size: 1.3rem; }
  .status-long  { color: #3fb950; font-weight: 700; }
  .status-short { color: #f85149; font-weight: 700; }
  .status-flat  { color: #8b949e; font-weight: 700; }
  [data-testid="stProgress"] > div { background: #21262d; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
CONTRACT_SPECS = {
    "ES":  dict(tick_size=0.25, tick_value=12.50, point_value=50.0,  base_price=4500.0),
    "NQ":  dict(tick_size=0.25, tick_value=5.00,  point_value=20.0,  base_price=15000.0),
    "MES": dict(tick_size=0.25, tick_value=1.25,  point_value=5.0,   base_price=4500.0),
    "CL":  dict(tick_size=0.01, tick_value=10.00, point_value=1000.0, base_price=75.0),
}
_G = "#3fb950"   # green
_R = "#f85149"   # red
_B = "#58a6ff"   # blue
_BG = "#0d1117"
_GRID = "#21262d"
_SIGNAL_COLORS = {"BUY": _G, "SELL": _R, "CLOSE": "#e3b341"}


def _ss(key, default=None):
    """Shorthand for st.session_state with default."""
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


# ── Session state init ────────────────────────────────────────────────────────
_ss("engine", None)
_ss("frames", [])        # list of FrameState
_ss("running", False)
_ss("df_full", None)
_ss("ready", False)      # True after engine.load()
_ss("replay_speed", 0.12)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚡ Live Replay")
    st.caption("Watch your strategy trade bar-by-bar")
    st.divider()

    symbol = st.selectbox("Symbol", list(CONTRACT_SPECS.keys()), index=0)
    timeframe = st.selectbox("Timeframe", ["1m", "5m", "15m", "1h"], index=1)

    strategy_name = st.selectbox(
        "Strategy",
        ["MA Crossover", "RSI Mean Reversion", "Breakout (Donchian)", "RSI Divergence"],
    )
    params = {}
    if strategy_name == "MA Crossover":
        params["fast"] = st.slider("Fast EMA", 3, 50, 9)
        params["slow"] = st.slider("Slow EMA", 10, 200, 21)
    elif strategy_name == "RSI Mean Reversion":
        params["period"] = st.slider("RSI Period", 5, 30, 14)
        params["oversold"] = st.slider("Oversold", 10, 40, 30)
        params["overbought"] = st.slider("Overbought", 60, 90, 70)
    elif strategy_name == "Breakout (Donchian)":
        params["lookback"] = st.slider("Channel Lookback", 5, 60, 20)
        params["atr_mult"] = st.slider("ATR Multiplier", 0.5, 5.0, 2.0)
    else:  # RSI Divergence
        params["rsi_overbought"] = st.slider("RSI Overbought", 80, 99, 94)
        params["rsi_oversold"]   = st.slider("RSI Oversold",    1, 20,  2)
        params["swing_lookback"] = st.slider("Swing Lookback (bars)", 2, 20, 5)

    st.subheader("Capital")
    initial_capital = st.number_input("Initial Capital ($)", 10_000, 1_000_000, 100_000, step=10_000)
    contracts = st.slider("Contracts per trade", 1, 10, 1)

    st.subheader("Data range")
    start_date = st.date_input("Start", date(2024, 1, 2))
    end_date = st.date_input("End", date(2025, 1, 1))

    st.divider()
    st.subheader("Playback")
    replay_speed_label = st.select_slider(
        "Speed",
        options=["0.05s", "0.1s", "0.2s", "0.5s", "1s", "2s"],
        value="0.1s",
    )
    _speed_map = {"0.05s": 0.05, "0.1s": 0.1, "0.2s": 0.2, "0.5s": 0.5, "1s": 1.0, "2s": 2.0}
    st.session_state.replay_speed = _speed_map[replay_speed_label]

    visible_bars = st.slider("Visible bars on chart", 50, 500, 150, step=25)

    st.divider()
    load_btn = st.button("⬇ Load Data", use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        play_btn = st.button("▶ Play", use_container_width=True, type="primary",
                              disabled=not st.session_state.ready)
    with col2:
        pause_btn = st.button("⏸ Pause", use_container_width=True,
                               disabled=not st.session_state.ready)

    reset_btn = st.button("↺ Reset", use_container_width=True,
                           disabled=not st.session_state.ready)


# ── Helper: build strategy ────────────────────────────────────────────────────
def _make_strategy():
    if strategy_name == "MA Crossover":
        return MACrossoverStrategy(fast=params["fast"], slow=params["slow"])
    if strategy_name == "RSI Mean Reversion":
        return RSIMeanReversionStrategy(
            period=params["period"], oversold=params["oversold"], overbought=params["overbought"]
        )
    if strategy_name == "Breakout (Donchian)":
        return BreakoutStrategy(lookback=params["lookback"], atr_mult=params["atr_mult"])
    if strategy_name == "RSI Divergence":
        return RSIDivergenceStrategy(
            rsi_overbought=float(params["rsi_overbought"]),
            rsi_oversold=float(params["rsi_oversold"]),
            swing_lookback=params["swing_lookback"],
        )
    return BreakoutStrategy(lookback=params.get("lookback", 20), atr_mult=params.get("atr_mult", 2.0))


# ── Load data ─────────────────────────────────────────────────────────────────
if load_btn:
    spec = CONTRACT_SPECS[symbol]
    tf_min = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}[timeframe]
    total_min = (end_date - start_date).days * 6.5 * 60
    bars = max(200, int(total_min / tf_min))

    with st.spinner(f"Generating {bars} bars for {symbol}…"):
        df = generate_sample_data(
            symbol=symbol,
            start=datetime.combine(start_date, datetime.min.time()).replace(hour=9, minute=30),
            bars=bars, timeframe_minutes=tf_min,
            base_price=spec["base_price"], tick_size=spec["tick_size"],
            save_dir="data/historical",
        )

    engine = ReplayEngine(
        strategy=_make_strategy(),
        symbol=symbol, timeframe=timeframe,
        initial_capital=float(initial_capital),
        contracts_per_trade=contracts,
        tick_size=spec["tick_size"], tick_value=spec["tick_value"],
        point_value=spec["point_value"],
    )
    engine.load(df)
    st.session_state.engine = engine
    st.session_state.frames = []
    st.session_state.df_full = df
    st.session_state.ready = True
    st.session_state.running = False
    st.rerun()

if play_btn:
    st.session_state.running = True

if pause_btn:
    st.session_state.running = False

if reset_btn:
    engine = st.session_state.engine
    if engine:
        engine.reset()
        engine.strategy = _make_strategy()
        engine.strategy.reset()
        engine.load(st.session_state.df_full)
    st.session_state.frames = []
    st.session_state.running = False
    st.rerun()


# ── Main UI ───────────────────────────────────────────────────────────────────
st.title("⚡ Live Strategy Replay")

if not st.session_state.ready:
    st.info("Configure your strategy in the sidebar, then click **⬇ Load Data** to begin.")
    st.stop()

engine: ReplayEngine = st.session_state.engine
frames: list[FrameState] = st.session_state.frames
done = engine.is_done
processed, total = engine.progress

# ── Progress bar ─────────────────────────────────────────────────────────────
prog_col, status_col = st.columns([4, 1])
with prog_col:
    progress_pct = processed / total if total else 0
    st.progress(progress_pct, text=f"Bar {processed:,} / {total:,}")
with status_col:
    if done:
        st.success("Complete")
    elif st.session_state.running:
        st.info("▶ Playing")
    else:
        st.warning("⏸ Paused")


# ── Live metrics row ──────────────────────────────────────────────────────────
m_cols = st.columns(7)

if frames:
    last: FrameState = frames[-1]
    trades = last.completed_trades
    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    total_pnl = sum(pnls)
    win_rate = (len(wins) / len(trades) * 100) if trades else 0.0
    unrealised = last.portfolio_value - (last.portfolio_value - total_pnl)

    pos_str = "FLAT"
    pos_color = "status-flat"
    if last.position > 0:
        pos_str = f"LONG +{last.position}"
        pos_color = "status-long"
    elif last.position < 0:
        pos_str = f"SHORT {last.position}"
        pos_color = "status-short"

    with m_cols[0]:
        delta_pct = (total_pnl / initial_capital) * 100
        st.metric("Portfolio", f"${last.portfolio_value:,.0f}",
                  delta=f"{delta_pct:+.1f}%")
    with m_cols[1]:
        st.metric("Total P&L", f"${total_pnl:+,.0f}")
    with m_cols[2]:
        st.metric("Trades", str(len(trades)))
    with m_cols[3]:
        st.metric("Win Rate", f"{win_rate:.0f}%")
    with m_cols[4]:
        st.metric("Avg Win", f"${(sum(wins)/len(wins)):,.0f}" if wins else "$0")
    with m_cols[5]:
        st.metric("Avg Loss", f"${(sum(losses)/len(losses)):,.0f}" if losses else "$0")
    with m_cols[6]:
        st.markdown(f"**Position**<br><span class='{pos_color}'>{pos_str}</span>", unsafe_allow_html=True)

    # Last signal badge
    if last.signal:
        sig = last.signal
        color = _SIGNAL_COLORS.get(sig.signal_type.value, "#8b949e")
        st.markdown(
            f"<div style='background:{color}22;border-left:3px solid {color};"
            f"padding:6px 12px;border-radius:4px;margin:4px 0'>"
            f"<b style='color:{color}'>{sig.signal_type.value}</b> &nbsp; "
            f"<span style='color:#8b949e'>{sig.reason}</span> &nbsp;"
            f"<span style='color:#8b949e'>{sig.timestamp.strftime('%H:%M')}</span></div>",
            unsafe_allow_html=True,
        )
else:
    for col in m_cols:
        with col:
            st.metric("—", "—")

st.divider()

# ── Chart + equity side-by-side ───────────────────────────────────────────────
chart_col, equity_col = st.columns([3, 1])

chart_placeholder = chart_col.empty()
equity_placeholder = equity_col.empty()

# Build chart from frames so far
def _build_live_chart(frames: list[FrameState], visible: int) -> go.Figure:
    if not frames:
        return go.Figure()

    last = frames[-1]
    all_bars = [f.bar for f in frames][-visible:]
    trades = last.completed_trades
    open_trade = last.open_trade

    ts  = [b.timestamp for b in all_bars]
    o   = [b.open for b in all_bars]
    h   = [b.high for b in all_bars]
    l   = [b.low for b in all_bars]
    c   = [b.close for b in all_bars]
    vol = [b.volume for b in all_bars]

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.78, 0.22], vertical_spacing=0.02,
    )

    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=ts, open=o, high=h, low=l, close=c,
        increasing_line_color=_G, decreasing_line_color=_R,
        name="Price", showlegend=False,
        increasing_fillcolor=_G, decreasing_fillcolor=_R,
    ), row=1, col=1)

    # EMAs
    if len(all_bars) >= 3:
        closes_s = pd.Series([b.close for b in all_bars], index=ts)
        for span, color in [(9, "#ffa657"), (21, "#79c0ff")]:
            ema = closes_s.ewm(span=span, adjust=False).mean()
            fig.add_trace(go.Scatter(
                x=ts, y=ema.values,
                line=dict(color=color, width=1.2),
                name=f"EMA{span}",
            ), row=1, col=1)

    # Completed trade markers (only those in visible window)
    visible_ts_set = set(ts)
    vis_longs  = [t for t in trades if t.direction == "LONG"  and t.entry_time in visible_ts_set]
    vis_shorts = [t for t in trades if t.direction == "SHORT" and t.entry_time in visible_ts_set]
    vis_exits  = [t for t in trades if t.exit_time  is not None and t.exit_time  in visible_ts_set]

    if vis_longs:
        fig.add_trace(go.Scatter(
            x=[t.entry_time for t in vis_longs],
            y=[t.entry_price * 0.9985 for t in vis_longs],
            mode="markers",
            marker=dict(symbol="triangle-up", size=14, color=_G,
                        line=dict(color="white", width=1)),
            name="Long",
            hovertemplate="<b>LONG</b><br>%{x|%H:%M}<br>@ %{y:.2f}<extra></extra>",
        ), row=1, col=1)

    if vis_shorts:
        fig.add_trace(go.Scatter(
            x=[t.entry_time for t in vis_shorts],
            y=[t.entry_price * 1.0015 for t in vis_shorts],
            mode="markers",
            marker=dict(symbol="triangle-down", size=14, color=_R,
                        line=dict(color="white", width=1)),
            name="Short",
            hovertemplate="<b>SHORT</b><br>%{x|%H:%M}<br>@ %{y:.2f}<extra></extra>",
        ), row=1, col=1)

    if vis_exits:
        exit_colors = [_G if t.pnl >= 0 else _R for t in vis_exits]
        fig.add_trace(go.Scatter(
            x=[t.exit_time for t in vis_exits],
            y=[t.exit_price for t in vis_exits],
            mode="markers",
            marker=dict(symbol="x-thin", size=13, color=exit_colors,
                        line=dict(color=exit_colors, width=2)),
            name="Exit",
            customdata=[(f"${t.pnl:+,.0f}", t.direction) for t in vis_exits],
            hovertemplate="<b>EXIT %{customdata[1]}</b><br>%{x|%H:%M}<br>@ %{y:.2f}<br>P&L %{customdata[0]}<extra></extra>",
        ), row=1, col=1)

    # Entry→exit connector lines
    for t in trades:
        if t.exit_time is None:
            continue
        if t.entry_time not in visible_ts_set and t.exit_time not in visible_ts_set:
            continue
        color = _G if t.pnl >= 0 else _R
        fig.add_trace(go.Scatter(
            x=[t.entry_time, t.exit_time],
            y=[t.entry_price, t.exit_price],
            mode="lines",
            line=dict(color=color, width=1, dash="dot"),
            showlegend=False, hoverinfo="skip",
        ), row=1, col=1)

    # Open trade marker (blinking effect via different symbol)
    if open_trade and open_trade.entry_time in visible_ts_set:
        c_ot = _G if open_trade.direction == "LONG" else _R
        sym_ot = "triangle-up" if open_trade.direction == "LONG" else "triangle-down"
        ep = open_trade.entry_price
        last_c = all_bars[-1].close
        unrealised = (last_c - ep if open_trade.direction == "LONG" else ep - last_c) * 50
        fig.add_trace(go.Scatter(
            x=[open_trade.entry_time],
            y=[ep * (0.9985 if open_trade.direction == "LONG" else 1.0015)],
            mode="markers",
            marker=dict(symbol=sym_ot, size=16, color=c_ot,
                        line=dict(color="white", width=2)),
            name=f"Open {open_trade.direction}",
            hovertemplate=(
                f"<b>OPEN {open_trade.direction}</b><br>"
                f"Entry: {ep:.2f}<br>"
                f"Unrealised: ${unrealised:+,.0f}<extra></extra>"
            ),
        ), row=1, col=1)

        # Draw current unrealised line to last bar
        color_ur = _G if unrealised >= 0 else _R
        fig.add_trace(go.Scatter(
            x=[open_trade.entry_time, all_bars[-1].timestamp],
            y=[ep, last_c],
            mode="lines",
            line=dict(color=color_ur, width=1.5, dash="dash"),
            showlegend=False, hoverinfo="skip",
        ), row=1, col=1)

    # Volume bars
    vol_colors = [_G if c >= o else _R for o, c in zip([b.open for b in all_bars], [b.close for b in all_bars])]
    fig.add_trace(go.Bar(
        x=ts, y=vol, marker_color=vol_colors, name="Volume", showlegend=False,
    ), row=2, col=1)

    fig.update_layout(
        paper_bgcolor=_BG, plot_bgcolor=_BG,
        font=dict(color="#e6edf3", size=11),
        dragmode="pan",          # left-click drag = pan; scroll = zoom
        hovermode="x unified",   # single crosshair across price + volume
        # uirevision keeps the user's current zoom/pan alive between frame reruns.
        # Without this the chart snaps back to full-range on every new candle.
        uirevision="live-replay",
        xaxis=dict(
            gridcolor=_GRID,
            rangeslider_visible=False,
            rangeselector=_RANGE_SELECTOR,
            **_SPIKE,
        ),
        xaxis2=dict(gridcolor=_GRID, **_SPIKE),
        yaxis=dict(gridcolor=_GRID, title="Price", fixedrange=False),
        yaxis2=dict(gridcolor=_GRID, title="Vol",  fixedrange=True),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=1.02, x=0),
        modebar=dict(bgcolor="rgba(0,0,0,0)", color="#555", activecolor="#e6edf3"),
        margin=dict(l=60, r=20, t=45, b=20),
        height=510,
    )
    return fig


def _build_equity_panel(frames: list[FrameState], initial_capital: float) -> go.Figure:
    if not frames:
        return go.Figure()
    last = frames[-1]
    eq_ts = [e[0] for e in last.equity]
    eq_val = [e[1] for e in last.equity]

    fig = go.Figure()
    fill_color = _G if (eq_val[-1] >= initial_capital) else _R
    fig.add_trace(go.Scatter(
        x=eq_ts, y=eq_val,
        line=dict(color=fill_color, width=2),
        fill="tozeroy",
        fillcolor=f"rgba({'63,185,80' if fill_color == _G else '248,81,73'},0.15)",
        name="Equity",
    ))
    fig.add_hline(y=initial_capital, line=dict(color="#8b949e", dash="dash", width=1))
    fig.update_layout(
        paper_bgcolor=_BG, plot_bgcolor=_BG,
        font=dict(color="#e6edf3", size=10),
        dragmode="pan",
        uirevision="equity-panel",   # preserve zoom between reruns
        xaxis=dict(gridcolor=_GRID, showticklabels=False, **_SPIKE),
        yaxis=dict(gridcolor=_GRID, fixedrange=False),
        showlegend=False,
        margin=dict(l=50, r=10, t=30, b=10),
        height=510,
        title=dict(text="Equity Curve", font=dict(size=12)),
    )
    return fig


# Render current state
chart_placeholder.plotly_chart(
    _build_live_chart(frames, visible_bars),
    use_container_width=True, config=CHART_CONFIG,
)
equity_placeholder.plotly_chart(
    _build_equity_panel(frames, initial_capital),
    use_container_width=True, config=CHART_CONFIG,
)

# ── Recent trades table ───────────────────────────────────────────────────────
if frames:
    last_f = frames[-1]
    recent = last_f.completed_trades[-10:][::-1]
    if recent:
        st.markdown("**Recent Trades**")
        rows = []
        for t in recent:
            pnl_str = f"${t.pnl:+,.0f}"
            dur = f"{t.duration_minutes:.0f}m" if t.duration_minutes else "—"
            rows.append({
                "Entry": t.entry_time.strftime("%m/%d %H:%M"),
                "Exit": t.exit_time.strftime("%m/%d %H:%M") if t.exit_time else "OPEN",
                "Dir": t.direction,
                "Entry $": f"{t.entry_price:.2f}",
                "Exit $": f"{t.exit_price:.2f}" if t.exit_price else "—",
                "P&L": pnl_str,
                "Duration": dur,
            })
        df_rec = pd.DataFrame(rows)
        st.dataframe(df_rec, use_container_width=True, height=260, hide_index=True)

# ── Replay loop ───────────────────────────────────────────────────────────────
if st.session_state.running and not done:
    frame = engine.step()
    st.session_state.frames.append(frame)
    time.sleep(st.session_state.replay_speed)
    st.rerun()
elif done and st.session_state.running:
    st.session_state.running = False
    st.balloons()
