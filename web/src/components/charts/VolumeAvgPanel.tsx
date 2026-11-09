// The settings panel behind the VolumeAvg gear: the one input the study has.

import { useEffect, useRef, useState } from "react"
import { DEFAULT_VOLUME_AVG_LENGTH, clampVolumeAvgLength } from "@/lib/volumeAverage"
import { cn } from "@/lib/utils"

export function VolumeAvgPanel({
  length, onLength, onClose, className,
}: {
  length: number
  onLength: (n: number) => void
  onClose: () => void
  className?: string
}) {
  const closeRef = useRef<HTMLButtonElement>(null)
  useEffect(() => { closeRef.current?.focus() }, [])
  // What is being typed. An emptied box stays empty until a number arrives,
  // rather than snapping back under the cursor.
  const [draft, setDraft] = useState(String(length))
  useEffect(() => { setDraft(String(length)) }, [length])

  return (
    <div
      role="dialog"
      aria-label="VolumeAvg settings"
      onKeyDown={(e) => { if (e.key === "Escape") onClose() }}
      className={cn("w-64 rounded-lg border border-[color:var(--hairline-mid)] bg-[var(--surface-1)] p-3 shadow-xl space-y-3", className)}
    >
      <div className="flex items-center justify-between">
        <span className="font-semibold text-sm">VolumeAvg settings</span>
        <button ref={closeRef} type="button" onClick={onClose} aria-label="Close"
                className="text-muted-foreground hover:text-foreground">✕</button>
      </div>
      <label className="flex items-center justify-between gap-3">
        <span className="text-muted-foreground">length</span>
        <input type="number" min={1} max={500} step={1} value={draft} aria-label="VolumeAvg length"
               onChange={(e) => {
                 setDraft(e.target.value)
                 if (Number.isFinite(e.target.valueAsNumber)) onLength(clampVolumeAvgLength(e.target.valueAsNumber))
               }}
               onBlur={() => setDraft(String(length))}
               className="w-20 rounded border border-[color:var(--hairline-mid)] bg-transparent px-2 py-1 text-right tabular-nums" />
      </label>
      <p className="text-[11px] text-muted-foreground">
        Default {DEFAULT_VOLUME_AVG_LENGTH}. Buyers and sellers are estimated from where each candle closes
        in its range, applied to its own volume.
      </p>
    </div>
  )
}
