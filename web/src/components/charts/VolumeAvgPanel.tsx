// The settings panel behind the VolumeAvg gear: the one input the study has.

import { useEffect, useRef } from "react"
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
        <input type="number" min={1} max={500} step={1} value={length} aria-label="VolumeAvg length"
               onChange={(e) => onLength(clampVolumeAvgLength(e.target.valueAsNumber))}
               className="w-20 rounded border border-[color:var(--hairline-mid)] bg-transparent px-2 py-1 text-right tabular-nums" />
      </label>
      <p className="text-[11px] text-muted-foreground">
        Default {DEFAULT_VOLUME_AVG_LENGTH}. Buyers and sellers are split from each candle's own volume.
      </p>
    </div>
  )
}
