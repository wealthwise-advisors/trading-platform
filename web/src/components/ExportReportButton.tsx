/**
 * Export Report, with its formats behind the button rather than beside it.
 *
 * The action row used to carry a separate format dropdown reading "HTML" next
 * to this button. The reference has one button and no dropdown -- and the
 * dropdown was an odd control anyway: a select whose value only ever mattered
 * at the moment you pressed the thing next to it. All five formats are still
 * here; pressing the button downloads HTML, and the caret opens the rest.
 *
 * Each entry is a real <a download> pointing at the same reportUrl the old
 * pair built, so the request, the chart settings sent with it, and the
 * filename are all unchanged.
 */

import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import type { ChartExportSettings } from "@/lib/chartExportSettings"
import { ChevronDown, Download } from "lucide-react"

const REPORT_FORMATS = [
  { id: "html", label: "HTML" },
  { id: "csv", label: "CSV" },
  { id: "xlsx", label: "Excel" },
  { id: "pdf", label: "PDF" },
  { id: "docx", label: "Word" },
]

export function ExportReportButton({
  backtestId, chartSettings,
}: { backtestId: string; chartSettings: ChartExportSettings }) {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const away = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", away)
    return () => document.removeEventListener("mousedown", away)
  }, [])

  return (
    <div ref={box} className="relative flex items-center">
      {/* The default. HTML is the full report with the charts drawn in it, and
          it is what the other four are variations on. */}
      <Button asChild size="sm" variant="default" className="rounded-r-none">
        <a href={api.reportUrl(backtestId, "html", chartSettings)} download>
          <Download className="h-3.5 w-3.5" aria-hidden /> Export Report
        </a>
      </Button>
      <Button
        type="button"
        size="sm"
        variant="default"
        className="rounded-l-none border-l border-[color:var(--hairline-firm)] px-1.5"
        aria-haspopup="menu"
        aria-expanded={open}
        title="Other report formats"
        onClick={() => setOpen((v) => !v)}
      >
        <ChevronDown className="h-3.5 w-3.5" aria-hidden />
        <span className="sr-only">Other report formats</span>
      </Button>
      {open && (
        <div role="menu"
             className="absolute right-0 top-9 z-50 w-40 overflow-hidden rounded-lg
                        border border-[color:var(--hairline-mid)] bg-[var(--surface-1)] py-1 shadow-xl">
          {REPORT_FORMATS.map((f) => (
            <a
              key={f.id}
              role="menuitem"
              href={api.reportUrl(backtestId, f.id, chartSettings)}
              download
              onClick={() => setOpen(false)}
              className="block px-3 py-1.5 text-xs text-foreground hover:bg-[color:var(--raise-3)]"
            >
              {f.label}
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
