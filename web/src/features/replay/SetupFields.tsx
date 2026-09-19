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
  label, Icon, children, info,
}: {
  label: string
  Icon: typeof CalendarDays
  children: ReactNode
  /** The circled "i" for this field. Sits on the label row, so it cannot
   *  change the input's height or push the row wider. */
  info?: ReactNode
}) {
  return (
    <div className="flex items-start gap-3">
      <span aria-hidden className="mt-6 grid place-items-center h-8 w-8 shrink-0 rounded-lg
                                   bg-[color:var(--raise-2)] text-violet-800 dark:text-violet-300 ring-1 ring-[color:var(--hairline-mid)]">
        <Icon size={15} strokeWidth={2} />
      </span>
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="flex items-center gap-1.5">
          <Label className="cfg-h">{label}</Label>
          {info}
        </div>
        {children}
      </div>
    </div>
  )
}

/** The glyph inside every timeframe pill.
 *
 *  Three plain bars of increasing height -- the same shape the nav's chart
 *  icons use. What was here before drew a candlestick: three boxes with wicks
 *  above and below, at 13px, which at that size resolves into a smear of
 *  strokes rather than anything recognisable, and read as noise beside the
 *  label it was meant to support. A timeframe is a bar width, so a bar chart
 *  is the honest picture of it. */
export function TfGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden
         fill="currentColor">
      <rect x="4" y="13" width="4" height="7" rx="1" />
      <rect x="10" y="9" width="4" height="11" rx="1" />
      <rect x="16" y="5" width="4" height="15" rx="1" />
    </svg>
  )
}
