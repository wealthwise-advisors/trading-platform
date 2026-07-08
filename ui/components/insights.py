"""
Rule-based "insight" text and info-card rendering for the dashboard's right
rail (Performance Summary / Backtest Details / Quick Insights / AI Insight).

Honesty: nothing here calls an external API or an LLM. Every sentence is a
plain threshold check against fields already on BacktestResults -- the same
kind of heuristic as the rest of this project's rule-based features
(regime detection, chart patterns, trade quality). Labeled "AI Insight" to
match the requested design, but it's free and runs entirely locally.
"""

import streamlit as st

from src.backtesting.results import BacktestResults

_CARD_CSS = """
<style>
  .info-card { background: linear-gradient(160deg, #262638 0%, #1e1e2e 100%);
               border: 1px solid rgba(255,255,255,0.06); border-radius: 12px;
               padding: 14px 18px; margin-bottom: 14px;
               box-shadow: 0 4px 16px -6px rgba(0,0,0,0.4); }
  .info-card .info-title { font-size: 0.85rem; font-weight: 700; color: #cdd6f4;
                            margin-bottom: 10px; }
  .info-card .info-row { display: flex; justify-content: space-between;
                          align-items: center; padding: 4px 0;
                          font-size: 0.82rem; color: #a6adc8; }
  .info-card .info-row .v { font-weight: 700; color: #cdd6f4; }
  .info-card .insight-item { font-size: 0.82rem; color: #a6adc8; padding: 3px 0;
                              line-height: 1.4; }
  .info-card.ai-insight { background: linear-gradient(160deg, #2e2450 0%, #1e1e2e 100%);
                           border: 1px solid rgba(144,133,233,0.35); }
  .info-card.ai-insight .info-title { color: #cba6f7; }
</style>
"""


def _row(icon: str, label: str, value: str) -> str:
    return f'<div class="info-row"><span>{icon} {label}</span><span class="v">{value}</span></div>'


def render_performance_summary(results: BacktestResults):
    st.markdown(_CARD_CSS, unsafe_allow_html=True)
    rows = "".join([
        _row("🏆", "Win Rate", f"{results.win_rate:.0f}%"),
        _row("🔢", "Total Trades", str(results.total_trades)),
        _row("⚖️", "Profit Factor", f"{results.profit_factor:.2f}"),
        _row("💰", "Average Win", f"${results.avg_win:,.2f}"),
        _row("🔻", "Average Loss", f"${results.avg_loss:,.2f}"),
        _row("📉", "Max Drawdown", f"{results.max_drawdown_pct:.1f}%"),
        _row("📈", "Total Return", f"{results.total_return_pct:+.1f}%"),
    ])
    st.markdown(
        f'<div class="info-card"><div class="info-title">📊 Performance Summary</div>{rows}</div>',
        unsafe_allow_html=True,
    )


def render_backtest_details(symbol: str, strategy_name: str, timeframe: str,
                             start_date, end_date, session_start, session_end,
                             data_source: str):
    st.markdown(_CARD_CSS, unsafe_allow_html=True)
    rows = "".join([
        _row("📅", "Date Range", f"{start_date} → {end_date}"),
        _row("⏱️", "Timeframe", timeframe),
        _row("🕐", "Session Hours", f"{session_start.strftime('%H:%M')}–{session_end.strftime('%H:%M')} EST"),
        _row("🔌", "Data Source", data_source),
        _row("🧠", "Strategy", strategy_name),
    ])
    st.markdown(
        f'<div class="info-card"><div class="info-title">🗂️ Backtest Details</div>{rows}</div>',
        unsafe_allow_html=True,
    )


def generate_insights(results: BacktestResults) -> list[str]:
    """Plain threshold checks on results -- no LLM, no external call."""
    insights = []
    if results.total_trades == 0:
        return ["No trades were taken in this period — nothing to evaluate yet."]

    if results.win_rate >= 70:
        insights.append(f"Strategy shows a high win rate ({results.win_rate:.0f}%).")
    elif results.win_rate < 40:
        insights.append(f"Win rate is low ({results.win_rate:.0f}%) — review entry conditions.")

    if results.max_drawdown_pct <= 5:
        insights.append(f"Max drawdown is under control ({results.max_drawdown_pct:.1f}%).")
    else:
        insights.append(f"Max drawdown is significant ({results.max_drawdown_pct:.1f}%) — "
                        "consider tighter risk limits.")

    if results.profit_factor >= 1.5:
        insights.append(f"Profit factor ({results.profit_factor:.2f}) suggests a solid edge.")
    elif results.profit_factor < 1.0:
        insights.append(f"Profit factor is below 1.0 ({results.profit_factor:.2f}) — "
                        "this run lost money overall.")

    if results.total_trades < 10:
        insights.append(f"Only {results.total_trades} trades — treat these results as preliminary.")

    return insights[:4]


def generate_ai_insight(results: BacktestResults) -> str:
    """One heuristic suggestion. Rule-based, not a model call."""
    if results.total_trades == 0:
        return "No trades to analyze — try a longer date range or looser entry parameters."
    if results.avg_loss and abs(results.avg_loss) > results.avg_win * 1.5 > 0:
        return "Average loss is notably larger than average win — consider tightening stop-loss distance."
    if results.win_rate > 65 and results.profit_factor < 1.2:
        return ("High win rate but thin profit factor — winners may be cut short relative "
                "to losers; consider letting profits run longer.")
    if results.max_drawdown_pct > 15:
        return "Drawdown is deep relative to returns — consider reducing position size or adding a volatility filter."
    return "No strong red flags in this run — test across a longer date range to confirm robustness."


def render_quick_insights(results: BacktestResults):
    st.markdown(_CARD_CSS, unsafe_allow_html=True)
    items = "".join(f'<div class="insight-item">✅ {i}</div>' for i in generate_insights(results))
    st.markdown(
        f'<div class="info-card"><div class="info-title">💡 Quick Insights</div>{items}</div>',
        unsafe_allow_html=True,
    )


def render_ai_insight(results: BacktestResults):
    st.markdown(_CARD_CSS, unsafe_allow_html=True)
    st.markdown(
        f'<div class="info-card ai-insight"><div class="info-title">🧠 AI Insight '
        f'<span style="font-size:0.65rem; opacity:0.7;">(rule-based, free — no API call)</span></div>'
        f'<div class="insight-item">{generate_ai_insight(results)}</div></div>',
        unsafe_allow_html=True,
    )
