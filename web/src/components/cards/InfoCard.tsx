// Port of ui/components/insights.py's render_performance_summary /
// render_backtest_details / render_quick_insights / render_ai_insight.
// All content is either plain fields off BacktestSummary or the rule-based
// generateInsights/generateAiInsight functions (lib/insights.ts) -- no LLM.

import type { BacktestSummary } from "@/lib/types"
import { generateInsights, generateAiInsight } from "@/lib/insights"
import type { ReactNode } from "react"
import {
  BarChart3, Trophy, Hash, Scale, ArrowUpRight, ArrowDownRight,
  TrendingDown, TrendingUp, Layers, CalendarRange, Timer, Clock,
  Plug, Target, Lightbulb, Check, Sparkles,
} from "lucide-react"

function Row({ icon, label, value }:
             { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="info-row">
      <span className="flex items-center gap-1.5">{icon} {label}</span>
      <span className="v">{value}</span>
    </div>
  )
}

export function PerformanceSummaryCard({ s }: { s: BacktestSummary }) {
  return (
    <div className="info-card" style={{ ["--info-accent" as string]: "#7c6cf5" }}>
      <div className="info-title flex items-center gap-2">
        <BarChart3 className="h-4 w-4" aria-hidden /> Performance Summary</div>
      <Row icon={<Trophy className="h-3.5 w-3.5 shrink-0" aria-hidden />} label="Win Rate" value={`${s.win_rate.toFixed(0)}%`} />
      <Row icon={<Hash className="h-3.5 w-3.5 shrink-0" aria-hidden />} label="Total Trades" value={String(s.total_trades)} />
      <Row icon={<Scale className="h-3.5 w-3.5 shrink-0" aria-hidden />} label="Profit Factor" value={s.profit_factor.toFixed(2)} />
      <Row icon={<ArrowUpRight className="h-3.5 w-3.5 shrink-0" aria-hidden />} label="Average Win" value={`$${s.avg_win.toFixed(2)}`} />
      <Row icon={<ArrowDownRight className="h-3.5 w-3.5 shrink-0" aria-hidden />} label="Average Loss" value={`$${s.avg_loss.toFixed(2)}`} />
      <Row icon={<TrendingDown className="h-3.5 w-3.5 shrink-0" aria-hidden />} label="Max Drawdown" value={`${s.max_drawdown_pct.toFixed(1)}%`} />
      <Row icon={<TrendingUp className="h-3.5 w-3.5 shrink-0" aria-hidden />} label="Total Return" value={`${s.total_return_pct >= 0 ? "+" : ""}${s.total_return_pct.toFixed(1)}%`} />
    </div>
  )
}

export function BacktestDetailsCard({ s }: { s: BacktestSummary }) {
  return (
    <div className="info-card" style={{ ["--info-accent" as string]: "#9b8afb" }}>
      <div className="info-title flex items-center gap-2">
        <Layers className="h-4 w-4" aria-hidden /> Backtest Details</div>
      <Row icon={<CalendarRange className="h-3.5 w-3.5 shrink-0" aria-hidden />} label="Date Range" value={`${s.start_date} → ${s.end_date}`} />
      <Row icon={<Timer className="h-3.5 w-3.5 shrink-0" aria-hidden />} label="Timeframe" value={s.timeframe} />
      <Row icon={<Clock className="h-3.5 w-3.5 shrink-0" aria-hidden />} label="Session Hours" value={`${s.session_start}–${s.session_end} EST`} />
      <Row icon={<Plug className="h-3.5 w-3.5 shrink-0" aria-hidden />} label="Data Source" value={s.data_source} />
      <Row icon={<Target className="h-3.5 w-3.5 shrink-0" aria-hidden />} label="Strategy" value={s.strategy_name} />
    </div>
  )
}

export function QuickInsightsCard({ s }: { s: BacktestSummary }) {
  return (
    <div className="info-card" style={{ ["--info-accent" as string]: "#22d3a8" }}>
      <div className="info-title flex items-center gap-2">
        <Lightbulb className="h-4 w-4" aria-hidden /> Quick Insights</div>
      {generateInsights(s).map((text, i) => (
        <div key={i} className="insight-item flex items-start gap-1.5">
          <Check className="h-3.5 w-3.5 shrink-0 mt-0.5" aria-hidden /> {text}</div>
      ))}
    </div>
  )
}

export function AiInsightCard({ s }: { s: BacktestSummary }) {
  return (
    <div className="info-card ai-insight" style={{ ["--info-accent" as string]: "#9b8afb" }}>
      <span className="ai-insight-badge">BETA</span>
      <span className="ai-insight-brain" aria-hidden><Sparkles className="h-full w-full" /></span>
      <div className="info-title relative z-10">
        <span className="inline-flex items-center gap-2"><Sparkles className="h-4 w-4" aria-hidden /> AI Insight</span> <span className="text-[0.65rem] opacity-70">(rule-based, free — no API call)</span>
      </div>
      <div className="insight-item relative z-10">{generateAiInsight(s)}</div>
      <svg className="ai-insight-wave" viewBox="0 0 300 40" preserveAspectRatio="none" aria-hidden>
        <path d="M0,25 Q25,5 50,25 T100,25 T150,25 T200,25 T250,25 T300,25 V40 H0 Z"
              fill="url(#ai-wave-gradient)" />
        <defs>
          <linearGradient id="ai-wave-gradient" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#7c6cf5" />
            <stop offset="100%" stopColor="#9b8afb" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  )
}
