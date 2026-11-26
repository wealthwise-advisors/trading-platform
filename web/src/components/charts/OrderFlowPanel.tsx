// Sir's three order-flow studies (2026-11-26) behind one chip's gear, like VolumeAvg's.
import { useEffect, useRef } from "react"
import { cn } from "@/lib/utils"

export interface OrderFlowToggles { delta: boolean; cvd: boolean; divergence: boolean }

const ROWS: { key: keyof OrderFlowToggles; label: string; note: string }[] = [
  { key: "delta", label: "Volume Delta", note: "Buyers − sellers per candle. Blue / orange past ±60 %." },
  { key: "cvd", label: "Cumulative Volume Delta", note: "Running total; restarts 6 PM, midnight, 8 AM ET." },
  { key: "divergence", label: "CVD Divergence",
    note: "Price vs CVD at consecutive 10 Leg highs / lows. Under 1.5 not shown, over 3 strong." },
]

export function OrderFlowPanel({ value, onChange, onClose, className }: {
  value: OrderFlowToggles
  onChange: (next: OrderFlowToggles) => void
  onClose: () => void
  className?: string
}) {
  const closeRef = useRef<HTMLButtonElement>(null)
  useEffect(() => { closeRef.current?.focus() }, [])
  return (
    <div role="dialog" aria-label="Order Flow settings"
         onKeyDown={(e) => { if (e.key === "Escape") onClose() }}
         className={cn("w-72 rounded-lg border border-[color:var(--hairline-mid)] bg-[var(--surface-1)] p-3 shadow-xl space-y-3", className)}>
      <div className="flex items-center justify-between">
        <span className="font-semibold text-sm">Order Flow settings</span>
        <button ref={closeRef} type="button" onClick={onClose} aria-label="Close"
                className="text-muted-foreground hover:text-foreground">✕</button>
      </div>
      {ROWS.map((r) => (
        <label key={r.key} className="flex items-start gap-2 cursor-pointer">
          <input type="checkbox" className="mt-0.5" checked={value[r.key]} aria-label={`Show ${r.label}`}
                 onChange={(e) => onChange({ ...value, [r.key]: e.target.checked })} />
          <span>
            <span className="text-sm">{r.label}</span>
            <span className="block text-[11px] text-muted-foreground">{r.note}</span>
          </span>
        </label>
      ))}
      <p className="text-[11px] text-muted-foreground">
        Estimated from where each candle closes in its range: Schwab gives no bid/ask volume.
      </p>
    </div>
  )
}
