// The settings panel behind each oscillator's gear.
//
// Read-only for now, and says so: it lists the inputs and level lines the
// chart actually draws. Making them editable waits on the open decisions about
// the RSI levels and StochRSI; MFI says plainly that it is not built. A panel
// of dead inputs would suggest otherwise.

import { useEffect, useRef } from "react"
import { OSC_STUDIES, type OscKey } from "@/lib/oscillatorStudies"
import { cn } from "@/lib/utils"

export function OscillatorStudyPanel({
  study, onClose, className,
}: {
  study: OscKey
  onClose: () => void
  className?: string
}) {
  const info = OSC_STUDIES[study]
  const closeRef = useRef<HTMLButtonElement>(null)

  // Focus the panel's own control on open, so a keyboard user who pressed the
  // gear lands inside the thing they opened.
  useEffect(() => { closeRef.current?.focus() }, [study])

  return (
    <div
      role="dialog"
      aria-label={`${info.label} settings`}
      onKeyDown={(e) => { if (e.key === "Escape") onClose() }}
      className={cn("w-64 rounded-lg border border-white/12 bg-[#14151c] p-3 shadow-xl space-y-3", className)}
    >
      <div className="flex items-center justify-between">
        <span className="font-semibold text-sm">{info.label} settings</span>
        <button ref={closeRef} type="button" onClick={onClose} aria-label="Close"
                className="text-muted-foreground hover:text-foreground">✕</button>
      </div>

      {info.available ? (
        <>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
            {info.inputs.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted-foreground">{k}</dt>
                <dd className="tabular-nums">{v}</dd>
              </div>
            ))}
            {info.levels && (
              <>
                <div className="contents">
                  <dt className="text-muted-foreground">overbought</dt>
                  <dd className="tabular-nums">{info.levels.overbought}</dd>
                </div>
                <div className="contents">
                  <dt className="text-muted-foreground">oversold</dt>
                  <dd className="tabular-nums">{info.levels.oversold}</dd>
                </div>
              </>
            )}
          </dl>
          <p className="text-[11px] text-muted-foreground">
            These are the values drawn on the chart, shown read-only until the levels are confirmed.
          </p>
        </>
      ) : (
        <p className="text-muted-foreground">{info.pending}</p>
      )}
    </div>
  )
}
