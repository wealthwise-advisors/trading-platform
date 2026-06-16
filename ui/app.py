"""
AutoTrader — Streamlit dashboard.

Run with:  streamlit run ui/app.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date, datetime, timedelta, time as time_type
import streamlit as st
import pandas as pd

from src.data.csv_provider import CSVDataProvider
from src.data.sample_data import generate_sample_data
try:
    from src.data.rithmic_provider import RithmicDataProvider
    _RITHMIC_AVAILABLE = True
except ImportError:
    _RITHMIC_AVAILABLE = False
try:
    from src.data.external_csv_provider import ExternalCSVProvider
    _EXTERNAL_AVAILABLE = True
except Exception:
    _EXTERNAL_AVAILABLE = False
try:
    from src.data.schwab_provider import SchwabDataProvider
    _SCHWAB_AVAILABLE = True
except Exception:
    _SCHWAB_AVAILABLE = False
from src.strategies import MACrossoverStrategy, RSIMeanReversionStrategy, BreakoutStrategy, RSIDivergenceStrategy
from src.backtesting.engine import BacktestEngine
from ui.components.charts import (
    candlestick_with_trades, equity_curve, pnl_distribution,
    monthly_returns_heatmap, CHART_CONFIG,
)
from ui.components.metrics import render_summary_metrics, render_detail_metrics
from ui.report import generate_html_report


# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AutoTrader",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  [data-testid="stAppViewContainer"] { background: #1e1e2e; }
  [data-testid="stSidebar"] { background: #181825; }
  h1, h2, h3 { color: #cdd6f4; }
  .stMetric label { color: #a6adc8; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Backtest Config")
    st.divider()

    data_source_options = ["Synthetic Data", "My Historical Data (CSV)", "Live Data (Schwab)", "Real Data (Rithmic)"]
    data_source = st.selectbox("Data Source", data_source_options, index=1)
    if data_source == "My Historical Data (CSV)":
        import yaml
        from pathlib import Path as _Path
        try:
            _cfg = yaml.safe_load(open(_Path(__file__).parent.parent / "config" / "settings.yaml"))
            _ext_dir = _cfg.get("data", {}).get("external_dir", "C:/Data")
        except Exception:
            _ext_dir = "C:/Data"
        st.caption(f"Reading from: `{_ext_dir}`")
        st.caption("Change path in `config/settings.yaml` → `data.external_dir`")
    if data_source == "Real Data (Rithmic)" and not _RITHMIC_AVAILABLE:
        st.warning(
            "pyrithmic package not found.\n\n"
            "Install it with:  `pip install -r requirements.txt`\n\n"
            "Then restart this app."
        )
    if data_source == "Live Data (Schwab)":
        _schwab_ready = False
        if not _SCHWAB_AVAILABLE:
            st.error("SchwabDataProvider failed to import — check config/credentials.yaml.")
        else:
            try:
                _schwab_prov = SchwabDataProvider()
                _rt_hours = _schwab_prov.refresh_token_hours_remaining()
                if not _schwab_prov.is_authenticated():
                    st.warning("Not authenticated with Schwab. Complete the steps below.")
                elif _schwab_prov.needs_reauth():
                    st.warning(f"Schwab token expires in {_rt_hours:.1f} h — re-authenticate now.")
                else:
                    st.success(f"Schwab connected  ({_rt_hours:.0f} h remaining)")
                    _schwab_ready = True

                if not _schwab_ready:
                    _auth_url = _schwab_prov.get_auth_url()
                    st.markdown(
                        f"**Step 1:** [Click here to authorize with Schwab]({_auth_url})\n\n"
                        "**Step 2:** After approving, copy the full browser URL and paste below."
                    )
                    _redirect_url = st.text_input("Paste redirect URL here", key="schwab_redirect")
                    if st.button("Submit & Save Tokens", key="schwab_submit"):
                        try:
                            _schwab_prov.complete_auth(_redirect_url)
                            st.success("Schwab authenticated successfully! Click Run Backtest.")
                            st.rerun()
                        except Exception as _e:
                            st.error(f"Authentication failed: {_e}")
            except Exception as _e:
                st.error(f"Schwab setup error: {_e}")

    if data_source == "My Historical Data (CSV)" and _EXTERNAL_AVAILABLE:
        try:
            _prov_preview = ExternalCSVProvider()
            _avail_syms = _prov_preview.list_available()
        except Exception:
            _avail_syms = ["ES", "NQ", "GC", "CL"]
        _es_idx = _avail_syms.index("ES") if "ES" in _avail_syms else 0
        _sym_list = _avail_syms + ["Other…"]
        _sym_sel = st.selectbox("Symbol", _sym_list, index=_es_idx)
    else:
        _sym_list = ["ES", "NQ", "MES", "CL", "Other…"]
        _sym_sel = st.selectbox("Symbol", _sym_list, index=0)
    if _sym_sel == "Other…":
        symbol = st.text_input("Enter symbol", placeholder="e.g. GC, ZN, NQ").strip().upper()
    else:
        symbol = _sym_sel
    timeframe = st.selectbox("Timeframe", ["1m", "5m", "15m", "30m", "1h"], index=0)

    _strategies = ["MA Crossover", "RSI Mean Reversion", "Breakout (Donchian)", "RSI Divergence"]
    strategy_name = st.selectbox("Strategy", _strategies, index=_strategies.index("RSI Divergence"))

    st.subheader("Strategy Parameters")
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
        params["atr_mult"] = st.slider("ATR Stop Multiplier", 0.5, 5.0, 2.0)
    elif strategy_name == "RSI Divergence":
        params["rsi_overbought"] = st.slider("RSI Overbought", 80, 99, 94)
        params["rsi_oversold"]   = st.slider("RSI Oversold",    1, 20,  2)
        params["swing_lookback"] = st.slider("Swing Lookback (bars)", 2, 20, 5)

    st.subheader("Capital & Risk")
    initial_capital = st.number_input("Initial Capital ($)", 10_000, 1_000_000, 100_000, step=10_000)
    contracts = st.slider("Contracts per Trade", 1, 10, 1)
    commission = st.number_input("Commission / Contract ($)", 0.0, 20.0, 2.50, step=0.25)

    st.subheader("Date Range")
    _today = date.today()
    start_date = st.date_input("Start", _today - timedelta(days=1))
    end_date = st.date_input("End", _today)

    st.subheader("Session Hours (EST)")
    _tc1, _tc2 = st.columns(2)
    with _tc1:
        session_start = st.time_input("From", time_type(9, 30))
    with _tc2:
        session_end = st.time_input("To", time_type(16, 0))

    st.divider()
    run_btn = st.button("▶ Run Backtest", use_container_width=True, type="primary")


# ── Contract specs ────────────────────────────────────────────────────────────
CONTRACT_SPECS = {
    "ES":  dict(tick_size=0.25, tick_value=12.50, point_value=50.0),
    "NQ":  dict(tick_size=0.25, tick_value=5.00,  point_value=20.0),
    "MES": dict(tick_size=0.25, tick_value=1.25,  point_value=5.0),
    "CL":  dict(tick_size=0.01, tick_value=10.00, point_value=1000.0),
}
BASE_PRICES = {"ES": 4500.0, "NQ": 15000.0, "MES": 4500.0, "CL": 75.0}


def build_strategy(name: str, p: dict):
    if name == "MA Crossover":
        return MACrossoverStrategy(fast=p["fast"], slow=p["slow"])
    if name == "RSI Mean Reversion":
        return RSIMeanReversionStrategy(period=p["period"], oversold=p["oversold"], overbought=p["overbought"])
    if name == "Breakout (Donchian)":
        return BreakoutStrategy(lookback=p["lookback"], atr_mult=p["atr_mult"])
    if name == "RSI Divergence":
        return RSIDivergenceStrategy(
            rsi_overbought=float(p["rsi_overbought"]),
            rsi_oversold=float(p["rsi_oversold"]),
            swing_lookback=p["swing_lookback"],
        )
    return BreakoutStrategy(lookback=p.get("lookback", 20), atr_mult=p.get("atr_mult", 2.0))


# ── Main ──────────────────────────────────────────────────────────────────────
st.title("📈 AutoTrader — Backtesting Dashboard")

if "results" not in st.session_state:
    st.session_state.results = None

if run_btn:
    if data_source == "Real Data (Rithmic)":
        spinner_msg = "Downloading real data from Rithmic…"
    elif data_source == "My Historical Data (CSV)":
        spinner_msg = f"Loading {symbol} historical data & running backtest…"
    elif data_source == "Live Data (Schwab)":
        spinner_msg = f"Fetching {symbol} data from Schwab & running backtest…"
    else:
        spinner_msg = "Generating synthetic data & running backtest…"
    with st.spinner(spinner_msg):
        spec = CONTRACT_SPECS.get(symbol, dict(tick_size=0.25, tick_value=12.50, point_value=50.0))

        if data_source == "Real Data (Rithmic)":
            if not _RITHMIC_AVAILABLE:
                st.error(
                    "Cannot use Rithmic data — pyrithmic package not installed.\n\n"
                    "Run: `pip install -r requirements.txt` then restart."
                )
                st.stop()
            provider = RithmicDataProvider(cache_dir="data/historical")
        elif data_source == "Live Data (Schwab)":
            try:
                provider = SchwabDataProvider()
                if not provider.is_authenticated():
                    st.error("Not authenticated with Schwab. Complete the re-auth flow in the sidebar.")
                    st.stop()
            except Exception as e:
                st.error(f"Schwab provider error: {e}")
                st.stop()
        elif data_source == "My Historical Data (CSV)":
            try:
                provider = ExternalCSVProvider()
            except FileNotFoundError as e:
                st.error(str(e))
                st.stop()
        else:
            tf_min = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60}[timeframe]
            total_minutes = (end_date - start_date).days * 6.5 * 60
            bars = int(total_minutes / tf_min)

            generate_sample_data(
                symbol=symbol,
                start=datetime.combine(start_date, datetime.min.time()).replace(hour=9, minute=30),
                bars=bars,
                timeframe_minutes=tf_min,
                base_price=BASE_PRICES.get(symbol, 4500.0),
                tick_size=spec["tick_size"],
                save_dir="data/historical",
            )
            provider = CSVDataProvider("data/historical")
        strategy = build_strategy(strategy_name, params)
        engine = BacktestEngine(
            data_provider=provider,
            strategy=strategy,
            symbol=symbol,
            timeframe=timeframe,
            initial_capital=float(initial_capital),
            commission_per_contract=float(commission),
            contracts_per_trade=contracts,
            session_start=session_start,
            session_end=session_end,
            **spec,
        )
        # Load full day range from provider; session filter is applied inside engine
        start_dt = datetime.combine(start_date, time_type(0, 0))
        end_dt   = datetime.combine(end_date,   time_type(23, 59))
        results = engine.run(start=start_dt, end=end_dt)
        st.session_state.results = results
    st.success("Backtest complete!")

results = st.session_state.results

if results is None:
    st.info("Configure your backtest in the sidebar and click **▶ Run Backtest**.")
    st.stop()

# ── Results header + action buttons ──────────────────────────────────────────
render_summary_metrics(results)

action_col1, action_col2, action_col3 = st.columns([2, 2, 4])
with action_col1:
    html_report = generate_html_report(results)
    st.download_button(
        label="⬇ Export Report (HTML)",
        data=html_report.encode("utf-8"),
        file_name=f"backtest_{results.symbol}_{results.strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
        mime="text/html",
        help="Download a self-contained HTML file — share via email, Slack, or Google Drive. "
             "Opens in any browser, no Python needed.",
        use_container_width=True,
    )
with action_col2:
    st.link_button(
        "⚡ Open Live Replay",
        url="http://localhost:8502",
        help="Open the bar-by-bar replay dashboard (run: streamlit run ui/live_app.py --server.port 8502)",
        use_container_width=True,
    )

st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Price & Trades",
    "📈 Equity Curve",
    "📋 Trade Log",
    "📉 P&L Analysis",
    "📅 Monthly Returns",
])

with tab1:
    st.plotly_chart(candlestick_with_trades(results), use_container_width=True, config=CHART_CONFIG)
    st.caption(
        "▲ Green triangle = Long entry  |  ▼ Red triangle = Short entry  |  "
        "✕ Green/Red X = Profitable / Loss exit  |  Dotted line = trade duration"
    )

with tab2:
    st.plotly_chart(equity_curve(results), use_container_width=True, config=CHART_CONFIG)
    render_detail_metrics(results)

with tab3:
    df_trades = results.trades_df()
    if df_trades.empty:
        st.warning("No completed trades in this period.")
    else:
        def highlight_pnl(val):
            if isinstance(val, float):
                color = "#1b4332" if val >= 0 else "#4a1010"
                return f"background-color: {color}"
            return ""

        styled = df_trades.style.applymap(highlight_pnl, subset=["pnl"])
        st.dataframe(styled, use_container_width=True, height=420)
        csv = df_trades.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Download Trade Log (CSV)", csv, "trades.csv", "text/csv")

with tab4:
    c1, c2 = st.columns([1, 1])
    with c1:
        st.plotly_chart(pnl_distribution(results), use_container_width=True, config=CHART_CONFIG)
    with c2:
        st.subheader("Consecutive Analysis")
        if results.trades:
            pnls = [t.pnl for t in results.trades]
            max_consec_wins = max_consec_losses = curr_w = curr_l = 0
            for p in pnls:
                if p > 0:
                    curr_w += 1
                    curr_l = 0
                    max_consec_wins = max(max_consec_wins, curr_w)
                else:
                    curr_l += 1
                    curr_w = 0
                    max_consec_losses = max(max_consec_losses, curr_l)
            st.metric("Max Consecutive Wins", max_consec_wins)
            st.metric("Max Consecutive Losses", max_consec_losses)
            st.metric("Largest Win", f"${max(pnls):,.0f}")
            st.metric("Largest Loss", f"${min(pnls):,.0f}")

with tab5:
    st.plotly_chart(monthly_returns_heatmap(results), use_container_width=True, config=CHART_CONFIG)
