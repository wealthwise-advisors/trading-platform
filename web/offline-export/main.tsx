/**
 * Entry of the OFFLINE copy of the app: the real app (src/App), answered by offlineServer
 * instead of a server, opening on the recorded run (Live Data, its dates, Globex, 5m).
 */
import "./offlineServer"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import "@/index.css"
import App from "@/App.tsx"
import { WorkspaceLoader } from "@/components/WorkspaceLoader"
import { ErrorBoundary } from "@/components/ErrorBoundary"
import { useConfigStore } from "@/store/configStore"
import { useZoneOffset } from "@/lib/sessionZone"

const REC = (window as unknown as { __REC__: { bt: Record<string, { summary: { start_date: string; end_date: string } }> } }).__REC__
const { start_date, end_date } = (REC.bt["5m"] ?? Object.values(REC.bt)[0]).summary
const day = (d: string) => new Date(`${d}T12:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })
document.title = `AutoTrader · /ES · ${day(start_date)} – ${day(end_date)} (offline)`
useConfigStore.setState({
  dataSource: "schwab", symbol: "ES", timeframe: REC.bt["5m"] ? "5m" : Object.keys(REC.bt)[0],
  startDate: start_date, endDate: end_date,
  sessionStart: "18:00", sessionEnd: "17:00", session24h: false,
  backtestId: `OFFLINE-${REC.bt["5m"] ? "5m" : Object.keys(REC.bt)[0]}`, page: "backtest", resultsTab: "price",
})
useZoneOffset.getState().setOffset(-60)   // times in Central, as sir reads them

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <WorkspaceLoader>{(user) => <App user={user} />}</WorkspaceLoader>
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
)
