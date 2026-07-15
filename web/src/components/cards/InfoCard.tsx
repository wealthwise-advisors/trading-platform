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
    <div className="info-card" style={{ ["--info-accent" as string]: "#2f80ff" }}>
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
    <div className="info-card" style={{ ["--info-accent" as string]: "#8b5cf6" }}>
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
    <div className="info-card ai-insight" style={{ ["--info-accent" as string]: "#8b5cf6" }}>
      <span className="ai-insight-badge">BETA</span>
      <span className="ai-insight-brain" aria-hidden>🧠</span>
      <div className="info-title relative z-10">
        🧠 AI Insight <span className="text-[0.65rem] opacity-70">(rule-based, free — no API call)</span>
      </div>
      <div className="insight-item relative z-10">{generateAiInsight(s)}</div>
      <svg className="ai-insight-wave" viewBox="0 0 300 40" preserveAspectRatio="none" aria-hidden>
        <path d="M0,25 Q25,5 50,25 T100,25 T150,25 T200,25 T250,25 T300,25 V40 H0 Z"
              fill="url(#ai-wave-gradient)" />
        <defs>
          <linearGradient id="ai-wave-gradient" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#2f80ff" />
            <stop offset="100%" stopColor="#8b5cf6" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  )
}
