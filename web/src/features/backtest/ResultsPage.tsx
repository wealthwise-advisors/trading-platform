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
import { OptimizerPanel } from "@/components/tables/OptimizerPanel"
import { ElliottWavePanel } from "@/components/tables/ElliottWavePanel"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card } from "@/components/ui/card"

export function ResultsPage() {
  const backtestId = useConfigStore((s) => s.backtestId)

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
  const elliottWaveQ = useQuery({
    queryKey: ["backtest", backtestId, "elliott-wave"],
    queryFn: () => api.getElliottWave(backtestId!),
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

  return (
    // Root fills the bounded height App.tsx hands down (its scroll div is
    // flex-1 min-h-0). KPI row/toolbar/footer stay natural height
    // (shrink-0); the hero row below is the ONE flex-1 element, so it --
    // and the chart's already-flex-1 chain inside it -- finally resolves
    // against a real viewport-derived number instead of a guessed minHeight.
    <div className="h-full flex flex-col gap-2 p-3 w-full max-w-none">
      {/* ── KPI row — sparklines/donut removed per explicit request (numbers
           only, no graphs) so this row is as short as possible, handing
           the freed vertical space straight to the chart below via the
           existing flex-1 hero row -- same mechanism every prior round
           used, just less content generating the height this time.
           items-start (not items-stretch) -- .stat-card isn't a flex
           container, so stretching it to match a taller row just left the
           label+value sitting at the top with dead space below; each card
           now takes only its own natural (tiny) height instead. ── */}
      <div className="shrink-0 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2 items-start">
        <StatCard label="Total Return" icon="📈" accent={ACCENTS[0]}
                  value={`${s.total_return_pct >= 0 ? "+" : ""}${s.total_return_pct.toFixed(1)}%`}
                  valueColor={retColor} />
        <StatCard label="Sharpe Ratio" icon="🎯" accent={ACCENTS[1]} value={s.sharpe_ratio.toFixed(2)} />
        <StatCard label="Max Drawdown" icon="📉" accent={ACCENTS[2]}
                  value={`${s.max_drawdown_pct.toFixed(1)}%`} valueColor={CRITICAL} />
        <StatCard label="Win Rate" icon="🏆" accent={ACCENTS[3]}
                  value={`${s.win_rate.toFixed(0)}%`} valueColor={winColor} />
        <WinLossDonut wins={winLossQ.data?.wins ?? 0} losses={winLossQ.data?.losses ?? 0}
                      winRate={winLossQ.data?.win_rate ?? 0} />
      </div>

      <Tabs defaultValue="price" className="flex-1 min-h-0 flex flex-col gap-0">
        {/* ── Tab bar. Export Report + Live Replay now live in the header (App.tsx),
             next to each other with the requested ~56px gap -- removed the
             duplicates that used to sit here to avoid two visible "Live Replay"
             entry points; same setPage("replay")/reportUrl() calls either way. ── */}
        <div className="shrink-0 flex flex-wrap items-center gap-2">
          <TabsList>
            <TabsTrigger value="price">📊 Price & Trades</TabsTrigger>
            <TabsTrigger value="equity">📈 Equity Curve</TabsTrigger>
            <TabsTrigger value="trades">📋 Trade Log</TabsTrigger>
            <TabsTrigger value="pnl">📈 P&L Analysis</TabsTrigger>
            <TabsTrigger value="monthly">📅 Monthly Returns</TabsTrigger>
            <TabsTrigger value="candles">🕯️ Candlestick Patterns</TabsTrigger>
            <TabsTrigger value="chartpatterns">📐 Chart Patterns</TabsTrigger>
            <TabsTrigger value="optimizer">✨ Strategy Optimizer</TabsTrigger>
            <TabsTrigger value="elliottwave">📶 Elliott Wave</TabsTrigger>
          </TabsList>
        </div>

        {/* ── Hero row: chart (fills remaining space) + narrow fixed sidebar ──
             This is a FLEX row now, not a CSS Grid. Grid rows default to
             auto-sizing (fit-content) unless grid-template-rows is set
             explicitly -- items-stretch only stretches items *within* a
             row's height, so with the old grid the row itself never grew
             past its content's height, leaving the leftover flex-1 space
             as blank area below the chart. Flexbox doesn't have that
             pitfall: a flex-row's children stretch to the container's full
             cross-size by default, so flex-1 on the chart column now
             actually reaches the bottom of the available viewport space. ── */}
        <div className="flex-1 min-h-0 flex flex-col xl:flex-row gap-3 items-stretch mt-2">
          <div className="min-w-0 flex-1 flex flex-col space-y-2 overflow-y-auto">
            <TabsContent value="price" className="mt-0 flex-1 flex flex-col min-h-0">
              <Card className="p-2 border border-white/6 w-full flex-1 flex flex-col min-h-0">
                {priceDataQ.data && zigzagQ.data && (
                  <div className="flex-1 min-h-0">
                    <CandlestickChart
                      symbol={s.symbol}
                      strategyName={s.strategy_name}
                      bars={priceDataQ.data.bars}
                      indicators={priceDataQ.data.indicators}
                      zigzag={zigzagQ.data}
                      trades={tradesQ.data ?? []}
                    />
                  </div>
                )}
              </Card>
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
            <TabsContent value="optimizer" className="mt-0">
              <Card className="p-4 border border-white/6 w-full">
                <OptimizerPanel />
              </Card>
            </TabsContent>
            <TabsContent value="elliottwave" className="mt-0">
              <Card className="p-4 border border-white/6 w-full">
                {elliottWaveQ.data && priceDataQ.data && (
                  <ElliottWavePanel data={elliottWaveQ.data} bars={priceDataQ.data.bars} symbol={s.symbol} />
                )}
              </Card>
            </TabsContent>
          </div>
        </div>
      </Tabs>
    </div>
  )
}
