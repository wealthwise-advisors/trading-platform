import { ConfigForm } from "@/features/backtest/ConfigForm"
import { ResultsPage } from "@/features/backtest/ResultsPage"
import { ReplayPage } from "@/features/replay/ReplayPage"
import { useConfigStore } from "@/store/configStore"
import { Button } from "@/components/ui/button"

function App() {
  const page = useConfigStore((s) => s.page)
  const setPage = useConfigStore((s) => s.setPage)

  return (
    // Stack sidebar above content on small screens; side-by-side from md up.
    // Sidebar stays fixed-width and sticky on desktop; content column uses
    // min-w-0 so a wide chart can never force the whole page to overflow
    // horizontally (the classic flexbox "child ignores parent width" bug).
    <div className="min-h-screen bg-background text-foreground flex flex-col md:flex-row">
      {page === "backtest" && (
        <aside className="w-full md:w-80 shrink-0 border-b md:border-b-0 md:border-r border-white/6 p-4 overflow-y-auto md:h-screen md:sticky md:top-0"
               style={{ background: "linear-gradient(180deg, #0b1120 0%, #060b18 100%)" }}>
          <ConfigForm />
        </aside>
      )}
      <main className="flex-1 min-w-0 overflow-y-auto">
        <header className="p-3 pb-0 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold">📈 AutoTrader</h1>
            <p className="text-sm text-muted-foreground">Analyze. Optimize. Execute with confidence.</p>
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant={page === "backtest" ? "default" : "secondary"} onClick={() => setPage("backtest")}>
              📊 Backtest
            </Button>
            <Button size="sm" variant={page === "replay" ? "default" : "secondary"} onClick={() => setPage("replay")}>
              ⚡ Live Replay
            </Button>
            {/* Live trading isn't wired up yet (src/broker/rithmic_broker.py is
                still a stub) -- disabled rather than pretending this does
                something, styled to match the reference's premium look. */}
            <Button size="sm" disabled title="Live trading deployment isn't implemented yet">
              🚀 Deploy
            </Button>
          </div>
        </header>
        {page === "backtest" ? <ResultsPage /> : <ReplayPage />}
      </main>
    </div>
  )
}

export default App
