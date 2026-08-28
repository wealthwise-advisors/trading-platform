import { useQuery } from "@tanstack/react-query"
import { lazy, Suspense, useState } from "react"
import { api } from "@/lib/api"
import {
  useConfigStore, ZIGZAG_DEV_3_DEFAULT, ZIGZAG_DEV_10_DEFAULT,
} from "@/store/configStore"
import { StatCard, ACCENTS, GOOD, CRITICAL, NEUTRAL } from "@/components/cards/StatCard"
import { WinLossDonut } from "@/components/charts/WinLossDonut"
import { TradeLogTable } from "@/components/tables/TradeLogTable"
import { CandlestickPatternsTable } from "@/components/tables/CandlestickPatternsTable"
import { ChartPatternsTable } from "@/components/tables/ChartPatternsTable"
import { MonthlyReturnsHeatmap } from "@/components/charts/MonthlyReturnsHeatmap"
import { OptimizerPanel } from "@/components/tables/OptimizerPanel"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card } from "@/components/ui/card"
import { LoadingBlock } from "@/components/ui/loader"
import {
  TrendingUp, TrendingDown, Trophy, Gauge, LineChart,
  // The page already imports a CandlestickChart component; alias the icon.
  CandlestickChart as CandlestickIcon,
  ClipboardList, BarChart3, CalendarDays, Activity, Shapes, Sparkles, Waves,
} from "lucide-react"

/**
 * The four Plotly charts are split out of the main bundle.
 *
 * plotly.js is 96 MB installed and roughly 4.5 MB of the 5.19 MB production
 * bundle -- by far the largest thing the app ships. Every visitor was
 * downloading and PARSING all of it before anything appeared, and measured cold
 * on the deployed site that cost 6.57s to first render: 1.9s of download and
 * about 4.7s of script evaluation.
 *
 * Nothing here needs it up front. This page returns the "configure a backtest"
 * sentence until a backtest id exists, Live Replay is a table, and Export has no
 * chart at all -- so on first paint there is no Plotly figure on screen in any
 * tab. Splitting it means the chart code is fetched the moment a result is
 * actually rendered, and never for someone who only opens the app.
 *
 * These are the only four modules that import Plotly. WinLossDonut and
 * MonthlyReturnsHeatmap draw with plain SVG and stay in the main chunk, so the
 * summary view is unaffected.
 *
 * Named exports, hence the .then() mapping -- React.lazy resolves `default`.
 */
const CandlestickChart = lazy(() =>
  import("@/components/charts/CandlestickChart").then((m) => ({ default: m.CandlestickChart })))
const ElliottWaveChart = lazy(() =>
  import("@/components/charts/ElliottWaveChart").then((m) => ({ default: m.ElliottWaveChart })))
const EquityChart = lazy(() =>
  import("@/components/charts/EquityChart").then((m) => ({ default: m.EquityChart })))
const PnlDistributionChart = lazy(() =>
  import("@/components/charts/PnlDistributionChart").then((m) => ({ default: m.PnlDistributionChart })))

/** Shown while a chart chunk is in flight. */
function ChartLoading() {
  return <LoadingBlock label="Loading chart" hint="preparing the plot" />
}


export function ResultsPage() {
  const backtestId = useConfigStore((s) => s.backtestId)
  const [ewScale, setEwScale] = useState<number | "all">("all")

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
    queryFn: () => api.getZigZag(backtestId!, ZIGZAG_DEV_3_DEFAULT / 100, ZIGZAG_DEV_10_DEFAULT / 100),
    enabled: !!backtestId,
  })
  // Elliott Wave: its own top-level tab with its own chart -- never an overlay
  // on Price & Trades. Params are omitted so the server's own D-13 defaults
  // apply and client/server cannot drift (SRS FR-1e.4).
  const elliottWaveQ = useQuery({
    queryKey: ["backtest", backtestId, "elliott-wave"],
    queryFn: () => api.getElliottWave(backtestId!),
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
    // A panel, not a filter.
    //
    // This line is the only text in the application that sits directly on the
    // background image, and over bright candles it was hard to read. The fix
    // belongs here rather than as a tint over the whole picture: one small
    // dark surface gives this sentence its own ground, and leaves the
    // photograph exactly as it is.
    return (
      <div className="flex items-center justify-center h-full p-8">
        <div className="flex items-center gap-3 rounded-xl border px-6 py-4
                        backdrop-blur-md shadow-lg"
             style={{ background: "rgba(16, 17, 23, 0.82)",
                      borderColor: "rgba(190, 190, 214, 0.14)" }}>
          <span className="text-lg leading-none" style={{ color: "#9b8afb" }}>▶</span>
          <p className="text-sm text-foreground">
            Configure your backtest in the sidebar, then click{" "}
            <b style={{ color: "#9b8afb" }}>Run Backtest</b>.
          </p>
        </div>
      </div>
    )
  }

  const s = summaryQ.data
  const isLoading = summaryQ.isLoading || tradesQ.isLoading || priceDataQ.isLoading
  const anyError = summaryQ.error || tradesQ.error || priceDataQ.error || equityQ.error || zigzagQ.error

  if (isLoading || !s) {
    return <LoadingBlock label="Loading results…" hint="Fetching trades, equity curve and price data" />
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
        <StatCard label="Total Return" icon={<TrendingUp className="h-4 w-4" />} accent={ACCENTS[0]}
                  value={`${s.total_return_pct >= 0 ? "+" : ""}${s.total_return_pct.toFixed(1)}%`}
                  valueColor={retColor} />
        <StatCard label="Sharpe Ratio" icon={<Gauge className="h-4 w-4" />} accent={ACCENTS[1]} value={s.sharpe_ratio.toFixed(2)} />
        <StatCard label="Max Drawdown" icon={<TrendingDown className="h-4 w-4" />} accent={ACCENTS[2]}
                  value={`${s.max_drawdown_pct.toFixed(1)}%`} valueColor={CRITICAL} />
        <StatCard label="Win Rate" icon={<Trophy className="h-4 w-4" />} accent={ACCENTS[3]}
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
          <TabsList className="tabs-scroll">
            <TabsTrigger value="price"><CandlestickIcon className="h-3.5 w-3.5 shrink-0" aria-hidden /> Price &amp; Trades</TabsTrigger>
            <TabsTrigger value="equity"><LineChart className="h-3.5 w-3.5 shrink-0" aria-hidden /> Equity Curve</TabsTrigger>
            <TabsTrigger value="trades"><ClipboardList className="h-3.5 w-3.5 shrink-0" aria-hidden /> Trade Log</TabsTrigger>
            <TabsTrigger value="pnl"><BarChart3 className="h-3.5 w-3.5 shrink-0" aria-hidden /> P&amp;L Analysis</TabsTrigger>
            <TabsTrigger value="monthly"><CalendarDays className="h-3.5 w-3.5 shrink-0" aria-hidden /> Monthly Returns</TabsTrigger>
            <TabsTrigger value="candles"><Activity className="h-3.5 w-3.5 shrink-0" aria-hidden /> Candlestick Patterns</TabsTrigger>
            <TabsTrigger value="chartpatterns"><Shapes className="h-3.5 w-3.5 shrink-0" aria-hidden /> Chart Patterns</TabsTrigger>
            <TabsTrigger value="optimizer"><Sparkles className="h-3.5 w-3.5 shrink-0" aria-hidden /> Strategy Optimizer</TabsTrigger>
            <TabsTrigger value="elliottwave"><Waves className="h-3.5 w-3.5 shrink-0" aria-hidden /> Elliott Wave</TabsTrigger>
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
                    <Suspense fallback={<ChartLoading />}>
                      <CandlestickChart
                        symbol={s.symbol}
                        strategyName={s.strategy_name}
                        bars={priceDataQ.data.bars}
                        indicators={priceDataQ.data.indicators}
                        zigzag={zigzagQ.data}
                        trades={tradesQ.data ?? []}
                      />
                    </Suspense>
                  </div>
                )}
              </Card>
            </TabsContent>
            <TabsContent value="equity" className="mt-0">
              <Card className="p-2 border border-white/6 w-full">
                <Suspense fallback={<ChartLoading />}>
                  <EquityChart points={equity} initialCapital={s.initial_capital} />
                </Suspense>
              </Card>
            </TabsContent>
            <TabsContent value="trades" className="mt-0">
              <Card className="p-4 border border-white/6 w-full">
                <TradeLogTable trades={tradesQ.data ?? []} />
              </Card>
            </TabsContent>
            <TabsContent value="pnl" className="mt-0">
              <Card className="p-4 border border-white/6 w-full">
                <Suspense fallback={<ChartLoading />}>
                  <PnlDistributionChart trades={tradesQ.data ?? []} />
                </Suspense>
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
            <TabsContent value="elliottwave" className="mt-0 flex-1 flex flex-col min-h-0">
              <Card className="p-2 border border-white/6 w-full flex-1 flex flex-col min-h-0">
                {priceDataQ.data && (
                  <div className="flex-1 min-h-0">
                    <Suspense fallback={<ChartLoading />}>
                      <ElliottWaveChart
                        symbol={s.symbol}
                        strategyName={s.strategy_name}
                        bars={priceDataQ.data.bars}
                        data={elliottWaveQ.data}
                        isLoading={elliottWaveQ.isLoading}
                        error={elliottWaveQ.error}
                        scaleFilter={ewScale}
                        onScaleFilter={setEwScale}
                      />
                    </Suspense>
                  </div>
                )}
              </Card>
            </TabsContent>
          </div>
        </div>
      </Tabs>
    </div>
  )
}
