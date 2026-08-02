// Shows only the interpretive notes worth surfacing to someone reading this
// chart. Warnings and alternate counts are dropped entirely (too much
// developer-facing signal, too little trader-facing signal). Any internal
// leg-hierarchy debug line -- always prefixed "Primary Wave ..." by
// wave_analysis.py's nesting step (see leg_label in _nested_minor_wave_sequence)
// -- is filtered out before display, since it explains detection internals,
// not the current chart. Renders nothing when there's nothing worth saying.

import { Info } from "lucide-react"
import { NEUTRAL } from "@/components/cards/StatCard"

const MAX_NOTES = 3

function meaningfulNotes(notes: string[]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const note of notes) {
    if (note.startsWith("Primary Wave")) continue
    if (seen.has(note)) continue
    seen.add(note)
    out.push(note)
    if (out.length >= MAX_NOTES) break
  }
  return out
}

export function WaveNotesCard({ notes }: { notes: string[] }) {
  const items = meaningfulNotes(notes)
  if (!items.length) return null
  return (
    <div className="flex items-start gap-2 px-1 py-1 text-xs text-foreground/70">
      <Info size={13} style={{ color: NEUTRAL }} className="mt-0.5 shrink-0" />
      <ul className="space-y-0.5">
        {items.map((text, i) => (
          <li key={i} className="leading-snug">{text}</li>
        ))}
      </ul>
    </div>
  )
}
