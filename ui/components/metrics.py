"""Streamlit metric card helpers — colorful stat-tile dashboard styling.

Card accent colors are the validated dark-mode categorical set (fixed order,
never cycled/reassigned by value) from the dataviz skill's reference palette.
Good/critical are the reserved status colors, used only for value polarity
(e.g. return sign), never as a card's identity accent.

Each card gets a real sparkline (equity curve / drawdown / rolling win-rate),
not decoration -- it's the same series the number summarizes, just shown as a
trend instead of a single point.
"""

import streamlit as st
from src.backtesting.results import BacktestResults

_GOOD = "#0ca30c"
_CRITICAL = "#d03b3b"
_NEUTRAL = "#cdd6f4"

# Fixed categorical order — card N always gets slot N, regardless of value.
_ACCENTS = ["#3987e5", "#9085e9", "#d95926", "#199e70", "#c98500", "#d55181"]

_CARD_CSS = """
<style>
  .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
               gap: 16px; margin-bottom: 18px; }
  .stat-card {
    position: relative; overflow: hidden;
    background: linear-gradient(160deg, #2a2a40 0%, #20202f 100%);
    border-radius: 12px; padding: 16px 18px 12px;
    border: 1px solid rgba(255,255,255,0.06);
    border-left: 4px solid var(--accent);
    box-shadow: 0 6px 20px -8px color-mix(in srgb, var(--accent) 55%, transparent),
                0 1px 3px rgba(0,0,0,0.5);
    transition: transform 0.15s ease;
  }
  .stat-card:hover { transform: translateY(-2px); }
  .stat-card .stat-icon { font-size: 1.1rem; opacity: 0.85; float: right; margin-top: -2px; }
  .stat-card .stat-label { font-size: 0.72rem; color: #a6adc8; text-transform: uppercase;
                            letter-spacing: 0.07em; margin-bottom: 6px; }
  .stat-card .stat-value { font-size: 1.65rem; font-weight: 800; line-height: 1.1;
                            font-variant-numeric: tabular-nums; }
  .stat-card .stat-sub { font-size: 0.75rem; color: #7f849c; margin-top: 4px; }
  .stat-card svg { display: block; margin-top: 6px; }
</style>
"""


def _sparkline_svg(values, color: str, width: int = 150, height: int = 34, filled: bool = True) -> str:
    vals = [float(v) for v in values if v == v]  # drop NaN
    if len(vals) < 2:
        return ""
    if len(vals) > 40:
        step = len(vals) // 40
        vals = vals[::step]
    vmin, vmax = min(vals), max(vals)
    rng = (vmax - vmin) or 1.0
    n = len(vals)
    pts = [f"{i / (n - 1) * width:.1f},{height - ((v - vmin) / rng) * height:.1f}"
           for i, v in enumerate(vals)]
    points = " ".join(pts)
    area = f'<polyline points="0,{height} {points} {width},{height}" fill="{color}" fill-opacity="0.16" stroke="none"/>' if filled else ""
    return (
        f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" preserveAspectRatio="none">'
        f'{area}'
        f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f"</svg>"
    )


def _card(label: str, value: str, accent: str, icon: str = "", value_color: str = _NEUTRAL,
          sub: str = "", spark: str = "") -> str:
    sub_html = f'<div class="stat-sub">{sub}</div>' if sub else ""
    icon_html = f'<span class="stat-icon">{icon}</span>' if icon else ""
    return (
        f'<div class="stat-card" style="--accent:{accent}">'
        f'{icon_html}'
        f'<div class="stat-label">{label}</div>'
        f'<div class="stat-value" style="color:{value_color}">{value}</div>'
        f"{sub_html}{spark}</div>"
    )


def render_summary_metrics(results: BacktestResults):
    st.markdown(_CARD_CSS, unsafe_allow_html=True)
    ret_color = _GOOD if results.total_return_pct >= 0 else _CRITICAL
    win_color = _GOOD if results.win_rate >= 50 else _NEUTRAL

    eq = results.equity_curve
    drawdown = (eq - eq.cummax()) / eq.cummax() * 100 if not eq.empty else eq
    if results.trades:
        running_wins, cum_win_pct = 0, []
        for i, t in enumerate(results.trades, 1):
            running_wins += 1 if t.pnl >= 0 else 0
            cum_win_pct.append(100 * running_wins / i)
    else:
        cum_win_pct = []

    cards = [
        _card("Total Return", f"{results.total_return_pct:+.1f}%", _ACCENTS[0], icon="📈",
              value_color=ret_color, sub=f"${results.total_pnl:+,.0f}",
              spark=_sparkline_svg(eq.values, ret_color) if not eq.empty else ""),
        _card("Sharpe Ratio", f"{results.sharpe_ratio:.2f}", _ACCENTS[1], icon="🎯"),
        _card("Max Drawdown", f"{results.max_drawdown_pct:.1f}%", _ACCENTS[2], icon="📉",
              value_color=_CRITICAL,
              spark=_sparkline_svg(drawdown.values, _CRITICAL) if not drawdown.empty else ""),
        _card("Win Rate", f"{results.win_rate:.0f}%", _ACCENTS[3], icon="🏆",
              value_color=win_color, sub=f"{results.total_trades} trades",
              spark=_sparkline_svg(cum_win_pct, _GOOD) if cum_win_pct else ""),
    ]
    st.markdown(f'<div class="stat-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_detail_metrics(results: BacktestResults):
    st.markdown(_CARD_CSS, unsafe_allow_html=True)
    cards = [
        _card("Profit Factor", f"{results.profit_factor:.2f}", _ACCENTS[4], icon="⚖️"),
        _card("Sortino Ratio", f"{results.sortino_ratio:.2f}", _ACCENTS[1], icon="🧭"),
        _card("Winners", str(results.winning_trades), _ACCENTS[3], icon="✅", value_color=_GOOD),
        _card("Losers", str(results.losing_trades), _ACCENTS[2], icon="❌", value_color=_CRITICAL),
        _card("Avg Win", f"${results.avg_win:,.0f}", _ACCENTS[0], icon="💰", value_color=_GOOD),
        _card("Avg Loss", f"${results.avg_loss:,.0f}", _ACCENTS[5], icon="🔻", value_color=_CRITICAL),
        _card("Final Capital", f"${results.final_capital:,.0f}", _ACCENTS[3], icon="🏦"),
        _card("Avg Duration", f"{results.avg_trade_duration_min:.0f} min", _ACCENTS[4], icon="⏱️"),
    ]
    st.markdown(f'<div class="stat-grid">{"".join(cards)}</div>', unsafe_allow_html=True)
