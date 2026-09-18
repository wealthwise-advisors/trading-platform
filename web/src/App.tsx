import brandMark from "@/assets/brand-mark.png"
import brandWordmark from "@/assets/brand-wordmark.png"
import { ConfigForm } from "@/features/backtest/ConfigForm"
import { ResultsPage } from "@/features/backtest/ResultsPage"
import { ReplayPage } from "@/features/replay/ReplayPage"
import { DataExportPage } from "@/features/export/DataExportPage"
import { useConfigStore } from "@/store/configStore"
import { useChartSettingsStore } from "@/store/chartSettingsStore"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { type Me } from "@/lib/api"
import { AccountSettings } from "@/components/AccountSettings"
import { ExportReportButton } from "@/components/ExportReportButton"
import { HeaderNav, SymbolSearch, AccountMenu } from "@/components/HeaderNav"
import { StatusBar } from "@/components/StatusBar"
import { OfflineBanner } from "@/components/OfflineBanner"
// Drawn, not typed: an emoji brings its own colour from the system font
// and cannot be themed. These are strokes in currentColor.
import { Upload, Rocket, Settings, Sun, Moon } from "lucide-react"
import { useThemeStore } from "@/store/themeStore"

function App({ user }: { user: Me }) {
  const page = useConfigStore((s) => s.page)
  // Display-only: whether the config panel is showing. Hiding it changes nothing
  // about the configuration or the request -- the same store backs the form
  // either way, so reopening restores exactly what was there.
  const [configOpen, setConfigOpen] = useState(true)
  const setPage = useConfigStore((s) => s.setPage)
  const backtestId = useConfigStore((s) => s.backtestId)
  // The account dialog is opened from the avatar menu now, so the page owns
  // whether it is showing rather than the dialog's own trigger button.
  const [accountOpen, setAccountOpen] = useState(false)
  // Sent with Export Report so the report draws what the price chart shows.
  const chartSettings = useChartSettingsStore((s) => s.settings)
  // Dark is the default and stays the default; this only offers the way out.
  const theme = useThemeStore((s) => s.theme)
  const toggleTheme = useThemeStore((s) => s.toggle)

  return (
    // Stack sidebar above content on small screens; side-by-side from lg up.
    //
    // lg, not md. The sidebar is a fixed 384px, so at the md breakpoint (768px)
    // it took half the viewport and left the chart, the nine KPI cards and the
    // three market panels to share the other 384px -- measured at 768px, the
    // Total Trades card and the Avg Win card literally overlapped, and the
    // chart came out 342px wide. Below lg the three columns are stacked and
    // the PAGE scrolls (lg:h-screen / lg:overflow-hidden rather than the
    // unconditional pair), because the viewport-locked terminal layout only
    // makes sense once everything fits in the viewport to begin with.
    //
    // Sidebar stays fixed-width and sticky on desktop; content column uses
    // min-w-0 so a wide chart can never force the whole page to overflow
    // horizontally (the classic flexbox "child ignores parent width" bug).
    //
    // h-screen + overflow-hidden here (was min-h-screen + the scrolling
    // happening on <main>) so <main> becomes a real, viewport-bound flex
    // column: header is shrink-0, and the new inner scroll div is the ONE
    // thing that scrolls. That inner div has a genuine bounded height for
    // the first time, which is what finally lets the chart's flex-1 chain
    // resolve to "fill remaining viewport space" instead of an arbitrary
    // fixed pixel guess.
    <div className="app-shell min-h-screen lg:h-screen text-foreground flex flex-col lg:overflow-hidden">
      {/* First focusable thing on the page, and invisible until it is focused.
          Without it a keyboard or screen-reader user tabs through the entire
          config sidebar -- every input, slider and dropdown -- before reaching
          the results they came for, on every single page load. */}
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <AccountSettings user={user} open={accountOpen} onOpenChange={setAccountOpen} />
      {/* The two COLUMNS. Their own row, so the status strip below can be a
          full-width sibling of the pair rather than a child of one of them. */}
      <div className="flex-1 min-h-0 flex flex-col lg:flex-row lg:overflow-hidden">
      {page === "backtest" && configOpen && (
        <aside className="w-full lg:w-[335px] shrink-0 border-b lg:border-b-0 lg:border-r border-[color:var(--hairline-soft)] px-3 py-3 lg:overflow-y-auto lg:h-full lg:min-h-0"
               style={{ background: "var(--sidebar-ground-from)" }}>
          <ConfigForm onCollapse={() => setConfigOpen(false)} />
        </aside>
      )}
      <main className="flex-1 min-w-0 lg:h-full lg:min-h-0 flex flex-col lg:overflow-hidden">
        {/* Above the header and shrink-0, so losing the network pushes the app
            down by one strip rather than covering any of it. It renders
            nothing at all while the connection is fine. */}
        <div className="shrink-0"><OfflineBanner /></div>
        {/* TWO EXPLICIT ROWS, as the reference has them: identity, sections,
            search and account on the first; the export and deploy actions
            right-aligned on the second, above the KPI row. This was one
            wrapping row, which put the search box and the export buttons on
            the same line and pushed the sections to their own. */}
        <header className="px-3 pt-2 pb-0 flex flex-wrap items-center justify-between gap-3 shrink-0">
          {/* The brand artwork rather than the name in text. The monogram and the
              wordmark are separate crops of the same poster: dropping the whole
              1536x1024 image into a 56px header would render the lettering about
              four pixels tall. The h1 is kept for the document outline, with the
              wordmark carrying its alt text. */}
          <div className="flex items-center gap-2.5 min-w-0">
            <img
              src={brandMark}
              alt=""
              aria-hidden
              className="h-9 w-9 shrink-0 rounded-lg object-cover
                         ring-1 ring-violet-400/20 shadow-lg shadow-violet-900/30"
            />
            <div className="min-w-0">
              <h1 className="min-w-0">
                <img
                  src={brandWordmark}
                  alt="AutoTrader"
                  className="h-6 sm:h-7 w-auto object-contain"
                />
              </h1>
              {/* What the product is, in four words, for someone who has just
                  been sent a link to it. */}
              <p className="hidden sm:block text-[10.5px] leading-tight text-muted-foreground/75">
                Research. Backtest. Trade Smarter.
              </p>
            </div>
          </div>

          {/* The sections, in the middle, where a trading terminal puts them. */}
          <div className="order-last w-full xl:order-none xl:w-auto xl:flex-1 xl:justify-center flex">
            <HeaderNav />
          </div>
          {/* Row one, right: find an instrument, reach the account. Sign out
              and Account live in the avatar menu, where the reference puts
              them; nothing was removed and the sign-out still revokes the
              session server-side rather than only clearing the cookie. */}
          <div className="flex items-center gap-2">
            <SymbolSearch />
            {/* The icon shows what clicking it GIVES you, not what you are in:
                a moon offers the dark theme. The accessible name says the same
                thing in words, and aria-pressed carries the current state, so
                a screen reader is not left to infer it from an icon name. */}
            <Button size="sm" variant="secondary" className="px-2"
                    onClick={toggleTheme}
                    aria-pressed={theme === "light"}
                    title={theme === "dark" ? "Switch to the light theme" : "Switch to the dark theme"}>
              {/* The icon shows the theme you are IN, which is what the
                  reference draws: a moon while the app is dark. The
                  accessible name and the tooltip below still describe the
                  ACTION, so nothing about the behaviour or the announcement
                  depends on reading the picture. */}
              {theme === "dark"
                ? <Moon className="h-4 w-4" aria-hidden />
                : <Sun className="h-4 w-4" aria-hidden />}
              <span className="sr-only">
                {theme === "dark" ? "Switch to the light theme" : "Switch to the dark theme"}
              </span>
            </Button>
            <Button size="sm" variant="secondary" className="px-2"
                    onClick={() => setAccountOpen(true)} title="Account settings">
              <Settings className="h-4 w-4" aria-hidden />
              <span className="sr-only">Account settings</span>
            </Button>
            <AccountMenu user={user} onOpenAccount={() => setAccountOpen(true)} />
          </div>
        </header>

        {/* Row two: the actions, right-aligned above the KPI row. */}
        <div className="px-3 pt-0.5 pb-0 flex items-center justify-end gap-2 flex-wrap shrink-0">
            {/* The way back, so collapsing the panel is never a one-way door. */}
            {page === "backtest" && !configOpen && (
              <Button size="sm" variant="secondary" onClick={() => setConfigOpen(true)}
                      title="Show the config panel">
                Config
              </Button>
            )}
            <Button size="sm" variant={page === "export" ? "default" : "secondary"}
                    onClick={() => setPage("export")} title="Export raw OHLC bars">
              <Upload className="h-3.5 w-3.5" aria-hidden /> Export Data
            </Button>
            {backtestId && <ExportReportButton backtestId={backtestId} chartSettings={chartSettings} />}
            {/* Live trading isn't wired up yet (src/broker/rithmic_broker.py is
                still a stub) -- disabled rather than pretending this does
                something, styled to match the reference's premium look. */}
            <Button size="sm" disabled title="Live trading deployment isn't implemented yet">
              <Rocket className="h-3.5 w-3.5" aria-hidden /> Deploy
            </Button>
        </div>
        {/* key={page} remounts this on every switch, which replays the
            entrance. The class goes HERE rather than on a wrapper inside:
            ResultsPage's root is h-full, so it needs a parent with a real
            resolved height. An extra div in between has auto height, h-full
            collapses to content, and the chart loses its flex-1 chain -- which
            is exactly the empty space that appeared under it. */}
        {/* tabIndex -1 so the skip link can actually move focus here. Without
            it the browser scrolls to the anchor but leaves focus at the top of
            the document, and the next Tab goes straight back into the sidebar
            the link existed to skip. */}
        <div id="main-content" tabIndex={-1} key={page}
             className="lg:flex-1 lg:min-h-0 lg:overflow-y-auto page-swap">
          {page === "backtest" && <ResultsPage />}
          {page === "replay" && <ReplayPage />}
          {page === "export" && <DataExportPage />}
        </div>
      </main>
      </div>
      {/* FULL WIDTH, and therefore a sibling of both columns rather than a
          child of <main>. In the reference it runs the entire width of the
          window, under the config panel as well -- what was run is a fact
          about the whole application, not about the results column. Outside
          every scroll container, so it never scrolls away from the thing it
          describes. */}
      <div className="shrink-0 w-full"><StatusBar /></div>
    </div>
  )
}

export default App
