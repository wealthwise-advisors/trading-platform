// Standalone raw-OHLC-data export tool -- pick a symbol, timeframe, date
// range, and data source, then download it as CSV/Excel/PDF/Word. Doesn't
// run a backtest; hits GET /api/data/export directly (api/routers/data_export.py).

import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { FileText, FileSpreadsheet, FileType, FileCode, Download } from "lucide-react"

const FORMATS = [
  { id: "csv", label: "CSV", icon: <FileText className="h-3.5 w-3.5 shrink-0" /> },
  { id: "xlsx", label: "Excel", icon: <FileSpreadsheet className="h-3.5 w-3.5 shrink-0" /> },
  { id: "pdf", label: "PDF", icon: <FileType className="h-3.5 w-3.5 shrink-0" /> },
  { id: "docx", label: "Word", icon: <FileCode className="h-3.5 w-3.5 shrink-0" /> },
]

const TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h"]
// Symbols come from /api/symbols per data source -- see the note in
// features/replay/ReplayPage.tsx. Hardcoding them here meant this page could
// not export the gold, bitcoin or equity samples that ship in data/sample.

function defaultDateRange() {
  const today = new Date()
  const day = today.getDay()
  const back = day === 0 ? 2 : day === 6 ? 1 : 1
  const d = new Date(today)
  d.setDate(d.getDate() - back)
  const iso = d.toISOString().slice(0, 10)
  return { start: iso, end: iso }
}

export function DataExportPage() {
  const { start, end } = defaultDateRange()
  const [symbol, setSymbol] = useState("ES")
  const [timeframe, setTimeframe] = useState("1h")
  const [startDate, setStartDate] = useState(start)
  const [endDate, setEndDate] = useState(end)
  const [dataSource, setDataSource] = useState("synthetic")

  const { data: dataSources } = useQuery({ queryKey: ["data-sources"], queryFn: api.dataSources })
  const { data: symbols } = useQuery({
    queryKey: ["symbols", dataSource],
    queryFn: () => api.symbols(dataSource),
  })

  // A symbol valid for one source may not exist in another (NQ has no CSV).
  useEffect(() => {
    if (!symbols || symbols.length === 0) return
    if (!symbols.some((s) => s.symbol === symbol)) setSymbol(symbols[0].symbol)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbols, symbol])

  const url = api.dataExportUrl({
    symbol, timeframe, start: startDate, end: endDate, dataSource, format: "csv",
  })
  const valid = !!(symbol && timeframe && startDate && endDate)

  return (
    <div className="p-4 max-w-2xl mx-auto space-y-4">
      <div>
        <h2 className="text-lg font-bold flex items-center gap-2">
          <Download className="h-4 w-4" aria-hidden /> Export Data</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Download raw OHLC price data for any symbol and date range — no backtest needed.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Data Selection</CardTitle>
          <CardDescription>Choose what to export</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Symbol</Label>
              <Select value={symbol} onValueChange={setSymbol}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(symbols ?? [{ symbol: "ES", name: "E-mini S&P 500", has_spec: true }]).map((s) => (
                    <SelectItem key={s.symbol} value={s.symbol}>
                      {s.symbol}
                      {s.name && s.name !== s.symbol && (
                        <span className="text-muted-foreground"> — {s.name}</span>
                      )}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Timeframe</Label>
              <Select value={timeframe} onValueChange={setTimeframe}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TIMEFRAMES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Start Date</Label>
              <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>End Date</Label>
              <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Data Source</Label>
            <Select value={dataSource} onValueChange={setDataSource}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                {(dataSources ?? []).map((ds) => (
                  <SelectItem key={ds.id} value={ds.id} disabled={!ds.available}>
                    {ds.label}{!ds.available ? " (unavailable)" : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Download</CardTitle>
          <CardDescription>Pick a file format</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {FORMATS.map((f) => (
              <Button key={f.id} asChild variant="secondary" disabled={!valid}>
                <a
                  href={api.dataExportUrl({ symbol, timeframe, start: startDate, end: endDate, dataSource, format: f.id })}
                  download
                >
                  {f.icon} {f.label}
                </a>
              </Button>
            ))}
          </div>
          {!valid && <p className="text-xs text-muted-foreground mt-2">Fill in every field above to enable downloads.</p>}
        </CardContent>
      </Card>

      {/* Debug/preview helper -- shows the exact request URL that'll be hit */}
      <p className="text-xs text-muted-foreground break-all">
        {valid ? url : ""}
      </p>
    </div>
  )
}
