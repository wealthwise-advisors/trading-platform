import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { useConfigStore } from "@/store/configStore"
import { StatCard, ACCENTS, GOOD, CRITICAL, NEUTRAL } from "@/components/cards/StatCard"
import { WinLossDonut } from "@/components/charts/WinLossDonut"
import { CandlestickChart } from "@/components/charts/CandlestickChart"
import { EquityChart } from "@/components/charts/EquityChart"
import { TradeLogTable } from "@/components/tables/TradeLogTable"
import { CandlestickPatternsTable } from "@/components/tables/CandlestickPatternsTable"
import { ChartPatternsTable } from "@/components/tables/ChartPatternsTable"
import { MonthlyReturnsHeatmap } from "@/components/charts/MonthlyReturnsHeatmap"
import { PnlDistributionChart } from "@/components/charts/PnlDistributionChart"
import {
  PerformanceSummaryCard, BacktestDetailsCard, QuickInsightsCard, AiInsightCard,
} from "@/components/cards/InfoCard"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { StatusBanner } from "@/components/StatusBanner"
import { ResultsFooterBar } from "@/components/ResultsFooterBar"

export function ResultsPage() {
  const backtestId = useConfigStore((s) => s.backtestId)
  const setPage = useConfigStore((s) => s.setPage)
  const lastRunAt = useConfigStore((s) => s.lastRunAt)

  const summaryQ = useQuery({
    queryKey: ["backtest", backtestId, "summary"],
    queryFn: () => api.getBacktest(backtestId!),
    enabled: !!backtestId,
  })
  const tradesQ = useQuery({
    queryKey: ["backtest", backtestId, "trades"],
    queryFn: () => api.getTrades(backtestId!),
    enabled: !!backtestId,
  })
  const priceDataQ = useQuery({
    queryKey: ["backtest", backtestId, "price-data"],
    queryFn: () => api.getPriceData(backtestId!),
    enabled: !!backtestId,
  })
  const equityQ = useQuery({
    queryKey: ["backtest", backtestId, "equity-curve"],
    queryFn: () => api.getEquityCurve(backtestId!),
    enabled: !!backtestId,
  })
  const zigzagQ = useQuery({
    queryKey: ["backtest", backtestId, "zigzag"],
    queryFn: () => api.getZigZag(backtestId!, 0.003, 0.003),
    enabled: !!backtestId,
  })
  const winLossQ = useQuery({
    queryKey: ["backtest", backtestId, "win-loss"],
    queryFn: () => api.getWinLoss(backtestId!),
    enabled: !!backtestId,
  })
  const monthlyReturnsQ = useQuery({
    queryKey: ["backtest", backtestId, "monthly-returns"],
    queryFn: () => api.getMonthlyReturns(backtestId!),
    enabled: !!backtestId,
  })
  const candlestickPatternsQ = useQuery({
    queryKey: ["backtest", backtestId, "candlestick-patterns"],
    queryFn: () => api.getCandlestickPatterns(backtestId!, 0),
    enabled: !!backtestId,
  })
  const chartPatternsQ = useQuery({
    queryKey: ["backtest", backtestId, "chart-patterns"],
    queryFn: () => api.getChartPatterns(backtestId!),
    enabled: !!backtestId,
  })

  if (!backtestId) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground p-8">
        <p>Configure your backtest in the sidebar and click <b>▶ Run Backtest</b>.</p>
      </div>
    )
  }

  const s = summaryQ.data
  const isLoading = summaryQ.isLoading || tradesQ.isLoading || priceDataQ.isLoading
  const anyError = summaryQ.error || tradesQ.error || priceDataQ.error || equityQ.error || zigzagQ.error

  if (isLoading || !s) {
    return <div className="p-8 text-muted-foreground">Loading results…</div>
  }
  if (anyError) {
    return <div className="p-8 text-destructive">Error: {String(anyError)}</div>
  }

  const equity = equityQ.data ?? []
  const retColor = s.total_return_pct >= 0 ? GOOD : CRITICAL
  const winColor = s.win_rate >= 50 ? GOOD : NEUTRAL

  const cumWinPct: number[] = []
  let wins = 0
  ;(tradesQ.data ?? []).forEach((t, i) => {
    wins += t.pnl >= 0 ? 1 : 0
    cumWinPct.push((100 * wins) / (i + 1))
  })

  return (
    // Grid layout: Header/Banner/KPIs/Tabs+actions span full width, then a
    // Large Chart | Right Panel row -- chart fills all remaining space
    // (1fr), the info-card sidebar stays a fixed 300px regardless of
    // viewport width. Footer spans full width again below.
    <div className="space-y-3 p-3 w-full max-w-none">
      <StatusBanner s={s} lastRunAt={lastRunAt} />

      {/* ── KPI row — every card equal height/width ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 items-stretch">
        <StatCard label="Total Return" icon="📈" accent={ACCENTS[0]}
                  value={`${s.total_return_pct >= 0 ? "+" : ""}${s.total_return_pct.toFixed(1)}%`}
                  valueColor={retColor} sub={`$${s.total_pnl.toLocaleString(undefined, { maximumFractionDigits: 0, signDisplay: "always" })}`}
                  sparklineValues={equity.map((e) => e.equity)} sparklineColor={retColor} />
        <StatCard label="Sharpe Ratio" icon="🎯" accent={ACCENTS[1]} value={s.sharpe_ratio.toFixed(2)} />
        <StatCard label="Max Drawdown" icon="📉" accent={ACCENTS[2]}
                  value={`${s.max_drawdown_pct.toFixed(1)}%`} valueColor={CRITICAL}
                  sparklineValues={equity.map((e) => e.drawdown_pct)} sparklineColor={CRITICAL} />
        <StatCard label="Win Rate" icon="🏆" accent={ACCENTS[3]}
                  value={`${s.win_rate.toFixed(0)}%`} valueColor={winColor}
                  sub={`${s.total_trades} trades`} sparklineValues={cumWinPct} sparklineColor={GOOD} />
        <WinLossDonut wins={winLossQ.data?.wins ?? 0} losses={winLossQ.data?.losses ?? 0}
                      winRate={winLossQ.data?.win_rate ?? 0} />
      </div>

      <Tabs defaultValue="price">
        {/* ── Tabs + action buttons, one toolbar ── */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <TabsList className="flex-wrap h-auto">
            <TabsTrigger value="price">📊 Price & Trades</TabsTrigger>
            <TabsTrigger value="equity">📈 Equity Curve</TabsTrigger>
            <TabsTrigger value="trades">📋 Trade Log</TabsTrigger>
            <TabsTrigger value="pnl">📈 P&L Analysis</TabsTrigger>
            <TabsTrigger value="monthly">📅 Monthly Returns</TabsTrigger>
            <TabsTrigger value="candles">🕯️ Candlestick Patterns</TabsTrigger>
            <TabsTrigger value="chartpatterns">📐 Chart Patterns</TabsTrigger>
          </TabsList>
          <div className="flex gap-2 shrink-0">
            <Button asChild variant="default" size="sm">
              <a href={api.reportUrl(backtestId)} download>⬇ Export Report (HTML)</a>
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setPage("replay")}>⚡ Open Live Replay</Button>
          </div>
        </div>

        {/* ── Hero row: chart (fills remaining space) + fixed-width right panel ── */}
        <div className="grid grid-cols-1 xl:grid-cols-[1fr_300px] gap-3 items-start mt-3">
          <div className="min-w-0 space-y-2">
            <TabsContent value="price" className="mt-0">
              <Card className="p-2 border border-white/6 w-full">
                {priceDataQ.data && zigzagQ.data && (
                  <CandlestickChart
                    symbol={s.symbol}
                    strategyName={s.strategy_name}
                    bars={priceDataQ.data.bars}
                    indicators={priceDataQ.data.indicators}
                    zigzag={zigzagQ.data}
                    trades={tradesQ.data ?? []}
                  />
                )}
              </Card>
              <p className="text-xs text-muted-foreground mt-4">
                ▲ Green triangle = Long entry &nbsp;|&nbsp; ▼ Red triangle = Short entry &nbsp;|&nbsp;
                ✕ Green/Red X = Profitable / Loss exit &nbsp;|&nbsp; Dotted line = trade duration
              </p>
            </TabsContent>
            <TabsContent value="equity" className="mt-0">
              <Card className="p-2 border border-white/6 w-full">
                <EquityChart points={equity} initialCapital={s.initial_capital} />
              </Card>
            </TabsContent>
            <TabsContent value="trades" className="mt-0">
              <Card className="p-4 border border-white/6 w-full">
                <TradeLogTable trades={tradesQ.data ?? []} />
              </Card>
            </TabsContent>
            <TabsContent value="pnl" className="mt-0">
              <Card className="p-4 border border-white/6 w-full">
                <PnlDistributionChart trades={tradesQ.data ?? []} />
              </Card>
            </TabsContent>
            <TabsContent value="monthly" className="mt-0">
              <Card className="p-4 border border-white/6 w-full">
                {monthlyReturnsQ.data && <MonthlyReturnsHeatmap data={monthlyReturnsQ.data} />}
              </Card>
            </TabsContent>
            <TabsContent value="candles" className="mt-0">
              <Card className="p-4 border border-white/6 w-full">
                <CandlestickPatternsTable patterns={candlestickPatternsQ.data ?? []} />
              </Card>
            </TabsContent>
            <TabsContent value="chartpatterns" className="mt-0">
              <Card className="p-4 border border-white/6 w-full">
                <ChartPatternsTable patterns={chartPatternsQ.data ?? []} />
              </Card>
            </TabsContent>
          </div>

          {/* ── Right panel — fixed width, stays put while the chart flexes ── */}
          <div className="flex flex-col gap-3 xl:w-[300px] shrink-0">
            <PerformanceSummaryCard s={s} />
            <BacktestDetailsCard s={s} />
            <QuickInsightsCard s={s} />
            <AiInsightCard s={s} />
          </div>
        </div>
      </Tabs>

      <ResultsFooterBar s={s} lastRunAt={lastRunAt} />
    </div>
  )
}
