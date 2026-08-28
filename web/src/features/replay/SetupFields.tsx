// Field wrappers for the setup form.
//
// The date fields come from components/ui/date-field -- master already had one
// by the time this branch built its own, and one of the two had to go.
//
// IconField carries the unit as a symbol beside the money fields, so the label
// does not have to repeat it. TfGlyph is the candlestick inside each pill.

import type { ReactNode } from "react"
import { CalendarDays } from "lucide-react"
import { Label } from "@/components/ui/label"

export function IconField({
  label, Icon, children,
}: {
  label: string
  Icon: typeof CalendarDays
  children: ReactNode
}) {
  return (
    <div className="flex items-start gap-3">
      <span aria-hidden className="mt-6 grid place-items-center h-8 w-8 shrink-0 rounded-lg
                                   bg-white/[0.04] text-violet-300 ring-1 ring-white/8">
        <Icon size={15} strokeWidth={2} />
      </span>
      <div className="min-w-0 flex-1 space-y-1.5">
        <Label className="cfg-h">{label}</Label>
        {children}
      </div>
    </div>
  )
}

/** The candlestick glyph inside every timeframe pill. */
export function TfGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden
         fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round">
      <path d="M6 4v3M6 17v3M12 3v4M12 16v5M18 5v4M18 15v4" opacity="0.75" />
      <rect x="4" y="7" width="4" height="10" rx="1" />
      <rect x="10" y="7" width="4" height="9" rx="1" />
      <rect x="16" y="9" width="4" height="6" rx="1" />
    </svg>
  )
}
