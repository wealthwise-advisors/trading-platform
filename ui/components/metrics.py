"""Streamlit metric card helpers."""

import streamlit as st
from src.backtesting.results import BacktestResults


def render_summary_metrics(results: BacktestResults):
    cols = st.columns(4)
    with cols[0]:
        st.metric("Total Return", f"{results.total_return_pct:+.1f}%",
                  delta=f"${results.total_pnl:,.0f}")
    with cols[1]:
        st.metric("Sharpe Ratio", f"{results.sharpe_ratio:.2f}")
    with cols[2]:
        st.metric("Max Drawdown", f"{results.max_drawdown_pct:.1f}%")
    with cols[3]:
        st.metric("Win Rate", f"{results.win_rate:.0f}%",
                  delta=f"{results.total_trades} trades")


def render_detail_metrics(results: BacktestResults):
    cols = st.columns(4)
    with cols[0]:
        st.metric("Profit Factor", f"{results.profit_factor:.2f}")
        st.metric("Avg Win", f"${results.avg_win:,.0f}")
    with cols[1]:
        st.metric("Sortino Ratio", f"{results.sortino_ratio:.2f}")
        st.metric("Avg Loss", f"${results.avg_loss:,.0f}")
    with cols[2]:
        st.metric("Winners", str(results.winning_trades))
        st.metric("Losers", str(results.losing_trades))
    with cols[3]:
        st.metric("Final Capital", f"${results.final_capital:,.0f}")
        st.metric("Avg Duration", f"{results.avg_trade_duration_min:.0f} min")
