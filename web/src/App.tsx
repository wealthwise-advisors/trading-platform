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
import { api } from "@/lib/api"

const REPORT_FORMATS = [
  { id: "html", label: "HTML" },
  { id: "csv", label: "CSV" },
  { id: "xlsx", label: "Excel" },
  { id: "pdf", label: "PDF" },
  { id: "docx", label: "Word" },
]

function App() {
  const page = useConfigStore((s) => s.page)
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
    <div className="h-screen bg-background text-foreground flex flex-col md:flex-row overflow-hidden">
      {page === "backtest" && (
        <aside className="w-full md:w-80 shrink-0 border-b md:border-b-0 md:border-r border-white/6 p-4 overflow-y-auto md:h-screen md:sticky md:top-0"
               style={{ background: "linear-gradient(180deg, #0b1325 0%, #060b18 100%)" }}>
          <ConfigForm />
        </aside>
      )}
      <main className="flex-1 min-w-0 h-screen flex flex-col overflow-hidden">
        <header className="p-3 pb-0 flex flex-wrap items-center justify-between gap-3 shrink-0">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold">📈 AutoTrader</h1>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Button size="sm" variant={page === "backtest" ? "default" : "secondary"} onClick={() => setPage("backtest")}>
              📊 Backtest
            </Button>
            {/* Live Replay: single visible button (a second one used to live in
                ResultsPage's toolbar, calling this exact same setPage("replay") --
                hidden there, not removed in function, since this one already
                covers every case that one did). Same gap-2 as every other header
                button now, for a balanced/uniform look. */}
            <Button size="sm" variant={page === "replay" ? "default" : "secondary"} onClick={() => setPage("replay")}>
              ⚡ Live Replay
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
        <div className="flex-1 min-h-0 overflow-y-auto">
          {page === "backtest" && <ResultsPage />}
          {page === "replay" && <ReplayPage />}
          {page === "export" && <DataExportPage />}
        </div>
      </main>
    </div>
  )
}

export default App
