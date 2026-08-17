// Colour picker for the VWAP deviation groups.
//
// Slots, not prices. The tape decides which whole numbers are on screen and
// sorts them ascending; slot 1 colours the lowest group, slot 2 the next, and
// so on. Nothing is stored against a price, so the same choice keeps working
// when the date, symbol, timeframes or sigma levels change.
//
// Presentation only — these values are handed to buildDeviationColorGroups and
// affect the fill of a cell. No calculation reads them.

import { Button } from "@/components/ui/button"
import { paletteCollisions } from "@/lib/deviationColors"
import { EDITABLE_SLOTS, type DeviationPalettes } from "@/lib/deviationColorSettings"

interface Props {
  palettes: DeviationPalettes
  onChange: (next: DeviationPalettes) => void
  onReset: () => void
  /** Whole numbers currently on the tape, ascending — for the live preview. */
  upperGroups: number[]
  lowerGroups: number[]
  savedNote?: string
}

function Row({
  label, colors, groups, onPick,
}: {
  label: string
  colors: string[]
  groups: number[]
  onPick: (slot: number, color: string) => void
}) {
  return (
    <div className="space-y-1">
      <div className="text-xs font-semibold">{label}</div>
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: EDITABLE_SLOTS }, (_, i) => {
          // The group this slot is painting right now, if the tape has one.
          const group = groups[i]
          return (
            <label key={i}
                   className="flex flex-col items-center gap-1"
                   title={group != null
                     ? `Slot ${i + 1} — currently colouring ${group}`
                     : `Slot ${i + 1} — no group on screen`}>
              <input
                type="color"
                aria-label={`${label} colour slot ${i + 1}`}
                value={colors[i]}
                onChange={(e) => onPick(i, e.target.value)}
                className="h-7 w-9 rounded cursor-pointer bg-transparent border border-white/15 p-0"
              />
              <span className={`text-[10px] font-mono ${group != null ? "" : "text-muted-foreground/50"}`}>
                {group != null ? group : `#${i + 1}`}
              </span>
            </label>
          )
        })}
      </div>
    </div>
  )
}

export function DeviationColorSettings({
  palettes, onChange, onReset, upperGroups, lowerGroups, savedNote,
}: Props) {
  const collisions = paletteCollisions(palettes.upper, palettes.lower)

  const pick = (side: "upper" | "lower") => (slot: number, color: string) => {
    const next: DeviationPalettes = { upper: [...palettes.upper], lower: [...palettes.lower] }
    next[side][slot] = color
    onChange(next)
  }

  return (
    <div className="space-y-3 border-t border-white/6 pt-3">
      <div className="flex items-baseline justify-between gap-3">
        <div className="text-xs font-semibold">Deviation group colours</div>
        <div className="text-[11px] text-muted-foreground">
          slot 1 = lowest group on screen
        </div>
      </div>

      <Row label="Upper deviations" colors={palettes.upper}
           groups={upperGroups} onPick={pick("upper")} />
      <Row label="Lower deviations" colors={palettes.lower}
           groups={lowerGroups} onPick={pick("lower")} />

      {/* The choice is not overridden -- the collision is just made visible,
          since a shared colour means upper and lower can no longer be told
          apart at a glance. */}
      {collisions.length > 0 && (
        <p className="text-[11px]" style={{ color: "#e3b341" }}>
          {collisions.length === 1 ? "Colour" : "Colours"}{" "}
          <span className="font-mono">{collisions.join(", ")}</span>{" "}
          {collisions.length === 1 ? "is" : "are"} used on both sides — upper and
          lower cells will look the same. Still applied.
        </p>
      )}

      <div className="flex items-center gap-3">
        <Button size="sm" variant="secondary" onClick={onReset}>
          Reset to default colours
        </Button>
        {savedNote && (
          <span className="text-[11px] text-muted-foreground">{savedNote}</span>
        )}
      </div>
    </div>
  )
}
