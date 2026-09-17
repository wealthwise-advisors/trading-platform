import { useQuery } from "@tanstack/react-query"
import { lazy, Suspense, useState } from "react"
import { api } from "@/lib/api"
import {
  useConfigStore, ZIGZAG_DEV_3_DEFAULT, ZIGZAG_DEV_10_DEFAULT,
} from "@/store/configStore"
import { StatCard, ACCENTS, GOOD, CRITICAL, NEUTRAL } from "@/components/cards/StatCard"
import { WatchlistPanel, MarketSummaryPanel, TradeStatsPanel } from "@/components/panels/MarketPanels"
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
  Sigma, Hash, ArrowUpRight, ArrowDownRight,
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

/**
 * Signed dollars, with the minus BEFORE the symbol: -$18.60, not $-18.60.
 *
 * `avg_loss` is the mean of every P&L at or below zero (see
 * src/backtesting/metrics.py), so it arrives negative and a naive `$${n}`
 * prints the sign in the middle of the number.
 */
const money = (n: number) =>
  `${n < 0 ? "-" : ""}$${Math.abs(n).toLocaleString(undefined, {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  })}`


export function ResultsPage() {
  const backtestId = useConfigStore((s) => s.backtestId)
  const resultsTab = useConfigStore((s) => s.resultsTab)
  const setResultsTab = useConfigStore((s) => s.setResultsTab)
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

  /**
   * Profit factor, read from the trade counts rather than the number.
   *
   * With no losing trades the engine computes float("inf") — the best possible
   * outcome — and api/serializers.py turns non-finite values into None and then
   * `None or 0.0` into a plain 0.0. So the API reports the best case as 0.00,
   * which is also what a total wipeout would report. Nothing on screen showed
   * this field before, so the collision never surfaced.
   *
   * winning_trades and losing_trades are exact, so they decide the wording:
   * wins and no losses is infinite, no trades at all is nothing to divide.
   */
  const pf = s.losing_trades === 0
    ? (s.winning_trades > 0
        ? { text: "∞", color: GOOD, sub: "no losing trades" }
        : { text: "—", color: NEUTRAL, sub: "no trades" })
    : { text: s.profit_factor.toFixed(2), color: s.profit_factor >= 1 ? GOOD : CRITICAL, sub: undefined }

  return (
    // Root fills the bounded height App.tsx hands down (its scroll div is
    // flex-1 min-h-0). KPI row/toolbar/footer stay natural height
    // (shrink-0); the hero row below is the ONE flex-1 element, so it --
    // and the chart's already-flex-1 chain inside it -- finally resolves
    // against a real viewport-derived number instead of a guessed minHeight.
    // A three-column page: the config rail is App.tsx's left aside, this is
    // the centre, and the market rail is the column on the right. Below xl the
    // rail moves UNDER the chart as a row of three -- the same components, one
    // instance. Rendering a second hidden copy for small screens would poll
    // Schwab twice every fifteen seconds to show one of them.
    <div className="h-full flex flex-col xl:flex-row gap-3 p-3 w-full max-w-none">
    <div className="min-h-0 flex-1 min-w-0 flex flex-col gap-2">
      {/* ── KPI row — sparklines/donut removed per explicit request (numbers
           only, no graphs) so this row is as short as possible, handing
           the freed vertical space straight to the chart below via the
           existing flex-1 hero row -- same mechanism every prior round
           used, just less content generating the height this time.
           items-stretch, and .stat-card centres its own content. This was
           items-start for exactly one reason -- a stretched card used to
           leave its label and value stranded at the top with dead space
           under them -- but that was a symptom of the card not being a flex
           column, not a reason to let a row hold three different heights. ── */}
      {/* ── NINE CELLS, ONE GRID ──────────────────────────────────────────
           Profit Factor, Total Trades, Avg Win and Avg Loss used to be
           readable only inside the Trade Log and the exported report, even
           though the summary already carries all four. They are cards now,
           in the SAME grid as the other five and using the same .stat-card
           markup, which is what makes them identical in height, width and
           padding -- a second container beside this one is exactly how a
           KPI row ends up misaligned with itself.

           Avg Win and Avg Loss are NOT here: they head the right rail, above
           the watchlist, which is where the reference puts them and which
           leaves this row seven cards instead of nine. At nine, "Win % /
           Loss %" and "Profit Factor" both wrapped to two lines on a 1700px
           screen — the row was squeezing the labels to hold cards that read
           better beside the trade statistics anyway.

           Columns step 2 -> 3 -> 4 -> 7 so the row never has to squeeze. ── */}
      <div className="shrink-0 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-7 gap-2 items-stretch">
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
        {/* Every value below comes from the same summary the other cards read
            (`profit_factor`, `total_trades`, `avg_win`, `avg_loss`) — nothing
            is recomputed here, so a card cannot disagree with the report. */}
        <StatCard label="Profit Factor" icon={<Sigma className="h-4 w-4" />} accent={ACCENTS[5]}
                  value={pf.text} valueColor={pf.color} sub={pf.sub} />
        <StatCard label="Total Trades" icon={<Hash className="h-4 w-4" />} accent={ACCENTS[2]}
                  value={s.total_trades.toLocaleString()} />
      </div>

      {/* Controlled, not defaultValue: the header's Chart / Strategy Lab /
          Analytics links open the view they name, which they cannot do if the
          tab strip owns its own state. */}
      <Tabs value={resultsTab} onValueChange={setResultsTab}
            className="flex-1 min-h-0 flex flex-col gap-0">
        {/* ── Tab bar. Export Report + Live Replay now live in the header (App.tsx),
             next to each other with the requested ~56px gap -- removed the
             duplicates that used to sit here to avoid two visible "Live Replay"
             entry points; same setPage("replay")/reportUrl() calls either way. ── */}
        <div className="shrink-0 flex flex-wrap items-center gap-2">
          <TabsList className="tabs-scroll">
            <TabsTrigger value="price"><CandlestickIcon className="h-3.5 w-3.5 shrink-0" aria-hidden /> Chart</TabsTrigger>
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
      <aside className="shrink-0 grid grid-cols-1 sm:grid-cols-3 gap-3
                        xl:flex xl:flex-col xl:w-[266px] xl:overflow-y-auto"
             aria-label="Market and trade panels">
        {/* The pair that heads the rail. Same .stat-card as the KPI row, so
            they are the same object in two columns rather than a lookalike.
            Green and red are meaning here: a $0.00 average loss with no losing
            trades is NOT red, because nothing was lost. */}
        <div className="grid grid-cols-2 gap-2 sm:col-span-3 xl:col-span-1">
          <StatCard label="Avg Win" icon={<ArrowUpRight className="h-4 w-4" />} accent={ACCENTS[3]}
                    value={money(s.avg_win)} valueColor={s.winning_trades > 0 ? GOOD : NEUTRAL}
                    sub={s.winning_trades === 0 ? "no winning trades" : undefined} />
          <StatCard label="Avg Loss" icon={<ArrowDownRight className="h-4 w-4" />} accent={ACCENTS[0]}
                    value={money(s.avg_loss)} valueColor={s.losing_trades > 0 ? CRITICAL : NEUTRAL}
                    sub={s.losing_trades === 0 ? "no losing trades" : undefined} />
        </div>
        <WatchlistPanel />
        <MarketSummaryPanel />
        <TradeStatsPanel s={s} />
      </aside>
    </div>
  )
}
