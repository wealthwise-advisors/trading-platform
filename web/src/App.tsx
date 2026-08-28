import brandMark from "@/assets/brand-mark.png"
import brandWordmark from "@/assets/brand-wordmark.png"
import { ConfigForm } from "@/features/backtest/ConfigForm"
import { ResultsPage } from "@/features/backtest/ResultsPage"
import { ReplayPage } from "@/features/replay/ReplayPage"
import { DataExportPage } from "@/features/export/DataExportPage"
import { useConfigStore } from "@/store/configStore"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { api, auth, SIGN_IN_PAGE } from "@/lib/api"

const REPORT_FORMATS = [
  { id: "html", label: "HTML" },
  { id: "csv", label: "CSV" },
  { id: "xlsx", label: "Excel" },
  { id: "pdf", label: "PDF" },
  { id: "docx", label: "Word" },
]

function App() {
  const page = useConfigStore((s) => s.page)
  // Display-only: whether the config panel is showing. Hiding it changes nothing
  // about the configuration or the request -- the same store backs the form
  // either way, so reopening restores exactly what was there.
  const [configOpen, setConfigOpen] = useState(true)
  const setPage = useConfigStore((s) => s.setPage)
  const backtestId = useConfigStore((s) => s.backtestId)
  const [reportFormat, setReportFormat] = useState("html")

  return (
    // Stack sidebar above content on small screens; side-by-side from md up.
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
    <div className="app-shell h-screen text-foreground flex flex-col md:flex-row overflow-hidden">
      {page === "backtest" && configOpen && (
        <aside className="w-full md:w-96 shrink-0 border-b md:border-b-0 md:border-r border-white/6 p-4 overflow-y-auto md:h-screen md:sticky md:top-0"
               style={{ background: "linear-gradient(180deg, #0b1325 0%, #060b18 100%)" }}>
          <ConfigForm onCollapse={() => setConfigOpen(false)} />
        </aside>
      )}
      <main className="flex-1 min-w-0 h-screen flex flex-col overflow-hidden">
        <header className="p-3 pb-0 flex flex-wrap items-center justify-between gap-3 shrink-0">
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
                         ring-1 ring-sky-400/20 shadow-lg shadow-sky-900/30"
            />
            <h1 className="min-w-0">
              <img
                src={brandWordmark}
                alt="AutoTrader"
                className="h-6 sm:h-7 w-auto object-contain"
              />
            </h1>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {/* Sign out. Calls the backend so the SESSION is revoked, not just
                the cookie cleared -- clearing only the cookie leaves a live
                session on the server that a copied cookie could still use.

                variant="outline", not "ghost". Ghost renders a borderless
                transparent control, so this sat among four real buttons looking
                like a text label -- and was reported as "there is no sign out
                button on the app". It was there the whole time and did not look
                like it. The only way out of a signed-in app is not the place to
                be subtle. */}
            <Button
              size="sm"
              variant="outline"
              title="Sign out of AutoTrader"
              onClick={async () => {
                await auth.logout()
                window.location.assign(SIGN_IN_PAGE)
              }}
            >
              Sign out
            </Button>
            {/* The way back, so collapsing the panel is never a one-way door. */}
            {page === "backtest" && !configOpen && (
              <Button size="sm" variant="secondary" onClick={() => setConfigOpen(true)}
                      title="Show the config panel">
                Config
              </Button>
            )}
            <Button size="sm" variant={page === "backtest" ? "default" : "secondary"} onClick={() => setPage("backtest")}>
              📊 Backtest
            </Button>
            {/* Market Grid: single visible button (a second one used to live in
                ResultsPage's toolbar, calling this exact same setPage("replay") --
                hidden there, not removed in function, since this one already
                covers every case that one did). Same gap-2 as every other header
                button now, for a balanced/uniform look. Renamed from "Live Replay" --
                the page serves live data and replay both, so "Replay" alone
                undersold it. Route id, folder and API path stay "replay". */}
            <Button size="sm" variant={page === "replay" ? "default" : "secondary"} onClick={() => setPage("replay")}>
              ⚡ Market Grid
            </Button>
            <Button size="sm" variant={page === "export" ? "default" : "secondary"} onClick={() => setPage("export")}>
              📤 Export Data
            </Button>
            {backtestId && (
              <div className="flex items-center gap-1">
                <Select value={reportFormat} onValueChange={setReportFormat}>
                  <SelectTrigger className="w-21 h-8 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {REPORT_FORMATS.map((f) => <SelectItem key={f.id} value={f.id}>{f.label}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Button asChild size="sm" variant="default">
                  <a href={api.reportUrl(backtestId, reportFormat)} download>⬇ Export Report</a>
                </Button>
              </div>
            )}
            {/* Live trading isn't wired up yet (src/broker/rithmic_broker.py is
                still a stub) -- disabled rather than pretending this does
                something, styled to match the reference's premium look. */}
            <Button size="sm" disabled title="Live trading deployment isn't implemented yet">
              🚀 Deploy
            </Button>
          </div>
        </header>
        {/* key={page} remounts this on every switch, which replays the
            entrance. The class goes HERE rather than on a wrapper inside:
            ResultsPage's root is h-full, so it needs a parent with a real
            resolved height. An extra div in between has auto height, h-full
            collapses to content, and the chart loses its flex-1 chain -- which
            is exactly the empty space that appeared under it. */}
        <div key={page} className="flex-1 min-h-0 overflow-y-auto page-swap">
          {page === "backtest" && <ResultsPage />}
          {page === "replay" && <ReplayPage />}
          {page === "export" && <DataExportPage />}
        </div>
      </main>
    </div>
  )
}

export default App
