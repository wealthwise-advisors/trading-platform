import { useQuery } from "@tanstack/react-query"
import { lazy, Suspense, useState } from "react"
import { api } from "@/lib/api"
import {
  useConfigStore, ZIGZAG_DEV_3_DEFAULT, ZIGZAG_DEV_10_DEFAULT,
} from "@/store/configStore"
import { StatCard, ACCENTS, GOOD, CRITICAL, NEUTRAL } from "@/components/cards/StatCard"
import {
  WatchlistPanel, MarketSummaryPanel, TradeStatsPanel, AccountSummaryPanel, AlertsPanel,
} from "@/components/panels/MarketPanels"
import { TradeLogTable } from "@/components/tables/TradeLogTable"
import {
  PositionsTable, OrdersTable, OrderHistoryTable, BalanceHistoryTable,
  TradingJournalTable, openPositionCount,
} from "@/components/tables/TradingPanels"
import { CandlestickPatternsTable } from "@/components/tables/CandlestickPatternsTable"
import { ChartPatternsTable } from "@/components/tables/ChartPatternsTable"
import { MonthlyReturnsHeatmap } from "@/components/charts/MonthlyReturnsHeatmap"
import { OptimizerPanel } from "@/components/tables/OptimizerPanel"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { MoreAnalyses } from "@/features/backtest/MoreAnalyses"
import { Card } from "@/components/ui/card"
import { LoadingBlock } from "@/components/ui/loader"
import {
  TrendingUp, TrendingDown, Trophy, Gauge,
  // The page already imports a CandlestickChart component; alias the icon.
  CandlestickChart as CandlestickIcon,
  // LineChart, Activity, Shapes and Sparkles left with their tabs when Equity
  // Curve, Candlestick Patterns, Chart Patterns and Strategy Optimizer moved
  // into MoreAnalyses -- the icons are declared there now, beside the entries.
  ClipboardList, BarChart3, CalendarDays,
  Sigma, Hash, ArrowUpRight, ArrowDownRight,
  // The reference's trading dock.
  Wallet, Inbox, History, Landmark, NotebookPen,
  // The collapsible right rail.
  ChevronsLeft, ChevronsRight, Star, Bell, Activity,
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
/**
 * A price move, for the Avg Win / Avg Loss pair.
 *
 * null means there were no trades on that side to average -- not a move of
 * zero. An em dash says "nothing to measure"; "0.0 pts" would claim the
 * trades happened and went nowhere.
 */
const points = (n: number | null | undefined) =>
  n == null ? "—" : `${n > 0 ? "+" : ""}${n.toFixed(1)} pts`

const money = (n: number) =>
  `${n < 0 ? "-" : ""}$${Math.abs(n).toLocaleString(undefined, {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  })}`


export function ResultsPage() {
  const backtestId = useConfigStore((s) => s.backtestId)
  const resultsTab = useConfigStore((s) => s.resultsTab)
  /** The right rail's open state. Per session rather than persisted: it is a
   *  "give the chart room for a moment" control, not a preference. */
  const [railOpen, setRailOpen] = useState(true)
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
  const dataSource = useConfigStore((st) => st.dataSource)
  // Shares the config panel's request (same key) purely to name the
  // instrument in the chart header. Absent, the header omits the description
  // and the exchange rather than inventing either.
  const symbolsQ = useQuery({
    queryKey: ["symbols", dataSource],
    queryFn: () => api.symbols(dataSource),
    staleTime: 5 * 60_000,
  })
  const instrument = (symbolsQ.data ?? []).find((m) => m.symbol === summaryQ.data?.symbol)


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
          <span className="text-lg leading-none" style={{ color: "var(--accent)" }}>▶</span>
          <p className="text-sm text-foreground">
            Configure your backtest in the sidebar, then click{" "}
            <b style={{ color: "var(--accent)" }}>Run Backtest</b>.
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

  /**
   * The mark for open positions: the close of the last bar the chart drew.
   *
   * Deliberately the SAME series the chart renders, so a position's unrealised
   * P&L can never disagree with the candle the user is looking at. null while
   * price data is still loading -- the Positions panel prints an em dash for
   * that rather than falling back to the entry price, which would show every
   * open trade at exactly break-even and read as a real quote.
   */
  const bars = priceDataQ.data?.bars ?? []
  const lastPrice = bars.length ? bars[bars.length - 1].c : null
  const openCount = openPositionCount(tradesQ.data ?? [])

  const retColor = s.total_return_pct >= 0 ? GOOD : CRITICAL
  const winColor = s.win_rate >= 50 ? GOOD : NEUTRAL

  /**
   * Profit factor. The API sends null when there is no finite ratio, and the
   * trade counts say which kind of "no finite ratio" it was: winners with no
   * losers is unbounded, nothing won and nothing lost is undefined.
   */
  const pf = s.profit_factor == null
    ? (s.winning_trades > 0
        ? { text: "∞", color: GOOD, sub: "no losing trades" }
        : { text: "—", color: NEUTRAL, sub: s.total_trades === 0 ? "no trades" : "no wins or losses" })
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
    //
    // xl:h-full, not h-full. Below xl this column stack is TALLER than the
    // viewport -- config panel, nine cards, a chart and three market panels --
    // and h-full told it otherwise. Its children then overflowed a box that
    // claimed to be the right size, which is not a scroll: measured at 768px,
    // the Total Trades card and the Avg Win card overlapped by 65px and the
    // chart was squeezed to nothing. Above xl the rail is a real column beside
    // the chart, everything fits, and the viewport-bound flex chain that lets
    // the chart claim the leftover height is exactly right -- so it is kept,
    // and only there. The same reasoning is why flex-1/min-h-0/overflow-y-auto
    // are xl:-prefixed all the way down this file.
    <div className="xl:h-full flex flex-col gap-1.5 px-3 pt-0.5 pb-3 xl:pb-1.5 w-full max-w-none">
      {/* THE TOP ROW: eight metrics, ONE grid.
           It used to be two containers -- six cards in a grid, then Avg Win
           and Avg Loss in a separate 338px box nudged 25px down and rendered
           `dense`. Three differences at once (own width, own vertical offset,
           own type scale) is why that pair read as detached and oversized
           rather than as the last two cards of a row. They are cells of the
           same grid now, so they are the same width, height, padding and type
           as the other six by construction -- not by two sets of numbers being
           kept in agreement. Nothing was renamed and no value is computed
           differently; only the box each one sits in changed. */}
      <div className="shrink-0 min-w-0">
      <div className="grid kpi-row gap-2 min-w-0 items-stretch">
        <StatCard label="Total Return" icon={<TrendingUp className="h-4 w-4" />} accent={ACCENTS[0]}
                  value={`${s.total_return_pct >= 0 ? "+" : ""}${s.total_return_pct.toFixed(1)}%`}
                  valueColor={retColor} />
        <StatCard label="Sharpe Ratio" icon={<Gauge className="h-4 w-4" />} accent={ACCENTS[1]} value={s.sharpe_ratio.toFixed(2)} />
        <StatCard label="Max Drawdown" icon={<TrendingDown className="h-4 w-4" />} accent={ACCENTS[2]}
                  value={`${s.max_drawdown_pct.toFixed(1)}%`} valueColor={CRITICAL} />
        <StatCard label="Win Rate" icon={<Trophy className="h-4 w-4" />} accent={ACCENTS[3]}
                  value={`${s.win_rate.toFixed(0)}%`} valueColor={winColor} />
        {/* Every value below comes from the same summary the other cards read
            (`profit_factor`, `total_trades`, `avg_win`, `avg_loss`) — nothing
            is recomputed here, so a card cannot disagree with the report. */}
        <StatCard label="Profit Factor" icon={<Sigma className="h-4 w-4" />} accent={ACCENTS[5]}
                  value={pf.text} valueColor={pf.color} sub={pf.sub} />
        <StatCard label="Total Trades" icon={<Hash className="h-4 w-4" />} accent={ACCENTS[2]}
                  value={s.total_trades.toLocaleString()} />
        {/* IN POINTS, as the reference shows them -- and derived, not
            relabelled. avg_win_points is the mean price move across the
            winning trades, computed on the server from each trade's entry and
            exit (api/serializers.py::_avg_points). It is null when there were
            no trades on that side, and an em dash says so rather than "0.0
            pts", which would read as "won nothing" instead of "won nothing
            yet". The dollar figure is not lost: it is a row in Trade
            Statistics directly below, and it is what the exported report
            carries.

            No sub-line here: "no losing trades" already appears under Profit
            Factor and in the panel beneath. */}
        <StatCard label="Avg Win" icon={<ArrowUpRight className="h-4 w-4" />}
                  accent={ACCENTS[3]}
                  value={points(s.avg_win_points)}
                  valueColor={s.winning_trades > 0 ? GOOD : NEUTRAL}
                  title={`${money(s.avg_win)} average on ${s.winning_trades} winning trade(s)`} />
        <StatCard label="Avg Loss" icon={<ArrowDownRight className="h-4 w-4" />}
                  accent={ACCENTS[0]}
                  value={points(s.avg_loss_points)}
                  valueColor={s.losing_trades > 0 ? CRITICAL : NEUTRAL}
                  title={`${money(s.avg_loss)} average on ${s.losing_trades} losing trade(s)`} />
      </div>
      </div>
      {/* The two columns, BELOW the top row: chart workspace and market rail. */}
      <div className="xl:min-h-0 xl:flex-1 flex flex-col xl:flex-row gap-3">
      <div className="xl:min-h-0 xl:flex-1 min-w-0 flex flex-col gap-2">
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

           SIX cards, as the reference has. "Win % / Loss %" moved to the
           Trade Statistics panel -- the number is still one glance away,
           and this row now holds what the reference holds.

           Columns step 2 -> 3 -> 3 -> 6 so the row never has to squeeze. ── */}

      {/* Controlled, not defaultValue: the header's Chart / Strategy Lab /
          Analytics links open the view they name, which they cannot do if the
          tab strip owns its own state. */}
      <Tabs value={resultsTab} onValueChange={setResultsTab}
            className="xl:flex-1 xl:min-h-0 flex flex-col gap-0">
        {/* ── Tab bar. Export Report + Live Replay now live in the header (App.tsx),
             next to each other with the requested ~56px gap -- removed the
             duplicates that used to sit here to avoid two visible "Live Replay"
             entry points; same setPage("replay")/reportUrl() calls either way. ── */}
        <div className="shrink-0 flex items-center gap-2 min-w-0">
          <TabsList className="tabs-scroll">
            {/* THE REFERENCE'S BOTTOM DOCK, in its order: Positions, Orders,
                Order History, Trade Log, P&L Analysis, Monthly Returns,
                Balance History, Trading Journal.

                Chart stays first and stays in the strip. In the reference the
                chart is not a tab at all -- it sits permanently above the dock
                -- so there is no position in that row that corresponds to it.
                Dropping it into the overflow menu to make the row match
                exactly would bury the app's primary view behind a menu, which
                is a worse trade than one extra tab. Everything the strip can
                no longer hold moved to MoreAnalyses, not deleted. */}
            <TabsTrigger value="price"><CandlestickIcon className="h-3.5 w-3.5 shrink-0" aria-hidden /> Chart</TabsTrigger>
            <TabsTrigger value="positions">
              <Wallet className="h-3.5 w-3.5 shrink-0" aria-hidden /> Positions{openCount > 0 ? ` (${openCount})` : ""}
            </TabsTrigger>
            <TabsTrigger value="orders"><Inbox className="h-3.5 w-3.5 shrink-0" aria-hidden /> Orders</TabsTrigger>
            <TabsTrigger value="orderhistory"><History className="h-3.5 w-3.5 shrink-0" aria-hidden /> Order History</TabsTrigger>
            <TabsTrigger value="trades"><ClipboardList className="h-3.5 w-3.5 shrink-0" aria-hidden /> Trade Log</TabsTrigger>
            <TabsTrigger value="pnl"><BarChart3 className="h-3.5 w-3.5 shrink-0" aria-hidden /> P&amp;L Analysis</TabsTrigger>
            <TabsTrigger value="monthly"><CalendarDays className="h-3.5 w-3.5 shrink-0" aria-hidden /> Monthly Returns</TabsTrigger>
            <TabsTrigger value="balance"><Landmark className="h-3.5 w-3.5 shrink-0" aria-hidden /> Balance History</TabsTrigger>
            <TabsTrigger value="journal"><NotebookPen className="h-3.5 w-3.5 shrink-0" aria-hidden /> Trading Journal</TabsTrigger>
          </TabsList>
          {/* ELLIOTT WAVE LIVES HERE NOW, not deleted.
              The reference shows eight tabs and they fit; ours was nine and
              the strip clipped after "Chart Patterns" at the reference width.
              Rather than drop a working feature -- twelve modules and eight
              structures sit behind it -- the ninth moves into an overflow
              menu, which is where a ninth item belongs once a row of eight is
              the design. It stays a real tab: the trigger below is the same
              TabsTrigger the strip would have rendered, so selecting it
              switches the panel exactly as before and the tab keeps its
              roving-focus and aria wiring. */}
          <MoreAnalyses value={resultsTab} onSelect={setResultsTab} />
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
        <div className="xl:flex-1 xl:min-h-0 flex flex-col xl:flex-row gap-3 items-stretch mt-1">
          <div className="relative min-w-0 xl:flex-1 flex flex-col space-y-2 xl:overflow-y-auto">
            {/* h-[60vh] below xl: with no flex-1 chain to inherit from, a chart
                 whose only height instruction is "fill the parent" fills nothing. */}
            <TabsContent value="price" className="mt-0 h-[60vh] xl:h-auto xl:flex-1 flex flex-col min-h-0">
              <Card className="p-1.5 border border-[color:var(--hairline-soft)] w-full flex-1 flex flex-col min-h-0">
                {/* The chart draws its own header now, so that the instrument
                    line and the Indicators / Save / full-screen controls share
                    one row. Rendering ChartHeader here as well would put the
                    instrument on the page twice. */}
                {priceDataQ.data && zigzagQ.data && (
                  <div className="flex-1 min-h-0">
                    <Suspense fallback={<ChartLoading />}>
                      <CandlestickChart
                        symbol={s.symbol}
                        strategyName={s.strategy_name}
                        description={instrument?.name}
                        exchange={instrument?.exchange}
                        interval={s.timeframe}
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
              <Card className="p-2 border border-[color:var(--hairline-soft)] w-full">
                <Suspense fallback={<ChartLoading />}>
                  <EquityChart points={equity} initialCapital={s.initial_capital} />
                </Suspense>
              </Card>
            </TabsContent>
            <TabsContent value="trades" className="mt-0">
              <Card className="p-4 border border-[color:var(--hairline-soft)] w-full">
                <TradeLogTable trades={tradesQ.data ?? []} />
              </Card>
            </TabsContent>
            {/* ── The reference's trading dock. Every figure on these five is
                 derived from the trades and the equity curve this page already
                 holds, so nothing here can disagree with the Trade Log or the
                 Equity Curve, and no panel invents a fill or a balance. ── */}
            <TabsContent value="positions" className="mt-0">
              <Card className="p-4 border border-[color:var(--hairline-soft)] w-full">
                <PositionsTable trades={tradesQ.data ?? []} lastPrice={lastPrice} symbol={s?.symbol ?? ""} />
              </Card>
            </TabsContent>
            <TabsContent value="orders" className="mt-0">
              <Card className="p-4 border border-[color:var(--hairline-soft)] w-full">
                <OrdersTable trades={tradesQ.data ?? []} symbol={s?.symbol ?? ""} />
              </Card>
            </TabsContent>
            <TabsContent value="orderhistory" className="mt-0">
              <Card className="p-4 border border-[color:var(--hairline-soft)] w-full">
                <OrderHistoryTable trades={tradesQ.data ?? []} symbol={s?.symbol ?? ""} />
              </Card>
            </TabsContent>
            <TabsContent value="balance" className="mt-0">
              <Card className="p-4 border border-[color:var(--hairline-soft)] w-full">
                <BalanceHistoryTable equity={equityQ.data ?? []}
                                     initialCapital={s?.initial_capital ?? 0} />
              </Card>
            </TabsContent>
            <TabsContent value="journal" className="mt-0">
              <Card className="p-4 border border-[color:var(--hairline-soft)] w-full">
                <TradingJournalTable trades={tradesQ.data ?? []} backtestId={backtestId} />
              </Card>
            </TabsContent>
            <TabsContent value="pnl" className="mt-0">
              <Card className="p-4 border border-[color:var(--hairline-soft)] w-full">
                <Suspense fallback={<ChartLoading />}>
                  <PnlDistributionChart trades={tradesQ.data ?? []} />
                </Suspense>
              </Card>
            </TabsContent>
            <TabsContent value="monthly" className="mt-0">
              <Card className="p-4 border border-[color:var(--hairline-soft)] w-full">
                {monthlyReturnsQ.data && <MonthlyReturnsHeatmap data={monthlyReturnsQ.data} />}
              </Card>
            </TabsContent>
            <TabsContent value="candles" className="mt-0">
              <Card className="p-4 border border-[color:var(--hairline-soft)] w-full">
                <CandlestickPatternsTable patterns={candlestickPatternsQ.data ?? []} />
              </Card>
            </TabsContent>
            <TabsContent value="chartpatterns" className="mt-0">
              <Card className="p-4 border border-[color:var(--hairline-soft)] w-full">
                <ChartPatternsTable patterns={chartPatternsQ.data ?? []} />
              </Card>
            </TabsContent>
            <TabsContent value="optimizer" className="mt-0">
              <Card className="p-4 border border-[color:var(--hairline-soft)] w-full">
                <OptimizerPanel />
              </Card>
            </TabsContent>
            <TabsContent value="elliottwave" className="mt-0 h-[60vh] xl:h-auto xl:flex-1 flex flex-col min-h-0">
              <Card className="p-2 border border-[color:var(--hairline-soft)] w-full flex-1 flex flex-col min-h-0">
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
      {/* COLLAPSED: a narrow rail of icons rather than nothing.
          Hiding the panels entirely leaves no clue they exist and no way back
          except a control somewhere else on the page. The strip keeps the
          affordance where the panels were, and each icon says which panel it
          brings back. Only from xl up -- below that the rail is a grid under
          the chart, not a column beside it, and there is no width to win. */}
      {!railOpen && (
        <aside className="hidden xl:flex shrink-0 w-9 flex-col items-center gap-1 border-l
                          border-[color:var(--hairline-soft)] py-2"
               aria-label="Market and trade panels, collapsed">
          <button type="button" onClick={() => setRailOpen(true)}
                  title="Show the market and trade panels"
                  aria-label="Show the market and trade panels"
                  className="rounded p-1.5 text-muted-foreground hover:bg-[color:var(--raise-3)]
                             hover:text-foreground">
            <ChevronsLeft className="h-4 w-4" aria-hidden />
          </button>
          <span className="my-0.5 h-px w-5 bg-[color:var(--hairline-soft)]" aria-hidden />
          {[
            { Icon: Star, label: "Watchlist" },
            { Icon: BarChart3, label: "Market Summary" },
            { Icon: Bell, label: "Alerts" },
            { Icon: Activity, label: "Trade Statistics" },
            { Icon: Wallet, label: "Account Summary" },
          ].map(({ Icon, label }) => (
            <button key={label} type="button" onClick={() => setRailOpen(true)}
                    title={label} aria-label={`Show ${label}`}
                    className="rounded p-1.5 text-muted-foreground hover:bg-[color:var(--raise-3)]
                               hover:text-foreground">
              <Icon className="h-4 w-4" aria-hidden />
            </button>
          ))}
        </aside>
      )}

      <aside className={`relative shrink-0 grid grid-cols-1 lg:grid-cols-3 gap-3
                        xl:flex xl:flex-col xl:w-[285px] xl:gap-1 xl:overflow-y-auto
                        ${railOpen ? "" : "xl:hidden"}`}
             aria-label="Market and trade panels">
        {/* The collapse control lives with the panels it hides. */}
        <div className="hidden xl:flex justify-end">
          <button type="button" onClick={() => setRailOpen(false)}
                  title="Hide the market and trade panels"
                  aria-label="Hide the market and trade panels"
                  className="rounded p-1 text-muted-foreground hover:bg-[color:var(--raise-3)]
                             hover:text-foreground">
            <ChevronsRight className="h-4 w-4" aria-hidden />
          </button>
        </div>
        {/* STACKED, NOT TABBED. An earlier pass put Watchlist, Market Summary
            and Alerts behind one tab strip to save vertical space. The current
            reference shows all of them open at once, and it is right: a
            watchlist you have to click to see is not a watchlist, and the
            whole point of the rail is answering "what is the market doing"
            without taking an action. The rail scrolls independently instead,
            and collapses entirely when the chart needs the width. */}
        <WatchlistPanel />
        <MarketSummaryPanel />
        {/* Alerts, judged against the bars this chart is drawn from -- the
            same array, so the panel and the level on the chart agree. */}
        <AlertsPanel bars={bars} />
        <TradeStatsPanel s={s} />
        {/* Account Summary sits below Trade Statistics, as the reference has
            it: the stats describe the trading, the account describes the
            capital it was done with. */}
        <AccountSummaryPanel s={s} openPositions={openCount} />
      </aside>
      </div>
    </div>
  )
}
