// Port of ui/components/insights.py's render_performance_summary /
// render_backtest_details / render_quick_insights / render_ai_insight.
// All content is either plain fields off BacktestSummary or the rule-based
// generateInsights/generateAiInsight functions (lib/insights.ts) -- no LLM.

import type { BacktestSummary } from "@/lib/types"
import { generateInsights, generateAiInsight } from "@/lib/insights"

function Row({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div className="info-row">
      <span>{icon} {label}</span>
      <span className="v">{value}</span>
    </div>
  )
}

export function PerformanceSummaryCard({ s }: { s: BacktestSummary }) {
  return (
    <div className="info-card" style={{ ["--info-accent" as string]: "#4f8ef7" }}>
      <div className="info-title">📊 Performance Summary</div>
      <Row icon="🏆" label="Win Rate" value={`${s.win_rate.toFixed(0)}%`} />
      <Row icon="🔢" label="Total Trades" value={String(s.total_trades)} />
      <Row icon="⚖️" label="Profit Factor" value={s.profit_factor.toFixed(2)} />
      <Row icon="💰" label="Average Win" value={`$${s.avg_win.toFixed(2)}`} />
      <Row icon="🔻" label="Average Loss" value={`$${s.avg_loss.toFixed(2)}`} />
      <Row icon="📉" label="Max Drawdown" value={`${s.max_drawdown_pct.toFixed(1)}%`} />
      <Row icon="📈" label="Total Return" value={`${s.total_return_pct >= 0 ? "+" : ""}${s.total_return_pct.toFixed(1)}%`} />
    </div>
  )
}

export function BacktestDetailsCard({ s }: { s: BacktestSummary }) {
  return (
    <div className="info-card" style={{ ["--info-accent" as string]: "#9d7bf0" }}>
      <div className="info-title">🗂️ Backtest Details</div>
      <Row icon="📅" label="Date Range" value={`${s.start_date} → ${s.end_date}`} />
      <Row icon="⏱️" label="Timeframe" value={s.timeframe} />
      <Row icon="🕐" label="Session Hours" value={`${s.session_start}–${s.session_end} EST`} />
      <Row icon="🔌" label="Data Source" value={s.data_source} />
      <Row icon="🧠" label="Strategy" value={s.strategy_name} />
    </div>
  )
}

export function QuickInsightsCard({ s }: { s: BacktestSummary }) {
  return (
    <div className="info-card" style={{ ["--info-accent" as string]: "#22d3a8" }}>
      <div className="info-title">💡 Quick Insights</div>
      {generateInsights(s).map((text, i) => (
        <div key={i} className="insight-item">✅ {text}</div>
      ))}
    </div>
  )
}

export function AiInsightCard({ s }: { s: BacktestSummary }) {
  return (
    <div className="info-card ai-insight" style={{ ["--info-accent" as string]: "#cba6f7" }}>
      <div className="info-title">
        🧠 AI Insight <span className="text-[0.65rem] opacity-70">(rule-based, free — no API call)</span>
      </div>
      <div className="insight-item">{generateAiInsight(s)}</div>
    </div>
  )
}
