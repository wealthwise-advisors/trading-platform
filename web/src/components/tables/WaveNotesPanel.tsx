// Surfaces WaveAnalysis.warnings / notes / alternates for one degree. Split
// into two cards so a genuine "this count is incomplete, here's why" signal
// (warnings) never gets lost among routine interpretive commentary (notes):
//   - Warnings & Notes: warnings first (amber, AlertTriangle) -- currently
//     only emitted by wave_numbering.py when Wave 5 couldn't be confirmed
//     because momentum divergence was unevaluable (RSI unavailable) -- then
//     general notes (neutral, Info) below.
//   - Alternate Counts: competing reads of the same structure (blue, GitBranch).
// Each card renders nothing (returns null) when its list is empty, so the
// tab stays clean when there's nothing to say -- no empty boxes.

import type { ReactNode } from "react"
import { AlertTriangle, Info, GitBranch } from "lucide-react"
import { Card } from "@/components/ui/card"
import { NEUTRAL } from "@/components/cards/StatCard"

const WARNING = "#f0a020"
const INFO = NEUTRAL
const ALT = "#4cc9f0"

function ListSection({ icon, color, items }: { icon: ReactNode; color: string; items: string[] }) {
  if (!items.length) return null
  return (
    <ul className="space-y-1.5">
      {items.map((text, i) => (
        <li key={i} className="flex items-start gap-2 text-sm leading-snug">
          <span className="mt-0.5 shrink-0" style={{ color }}>{icon}</span>
          <span className="text-foreground/90">{text}</span>
        </li>
      ))}
    </ul>
  )
}

export function WaveWarningsCard({ notes, warnings }: { notes: string[]; warnings: string[] }) {
  if (!notes.length && !warnings.length) return null
  return (
    <Card className="p-4 border border-white/6 w-full">
      <div className="flex items-center gap-2 mb-3 text-sm font-medium">
        <AlertTriangle size={15} style={{ color: WARNING }} />
        <span>Warnings & Notes</span>
        {warnings.length > 0 && (
          <span className="ml-auto rounded-full px-2 py-0.5 text-[0.7rem] font-medium"
                style={{ background: `color-mix(in srgb, ${WARNING} 20%, transparent)`, color: WARNING }}>
            {warnings.length} unconfirmed
          </span>
        )}
      </div>
      <div className="space-y-3">
        <ListSection icon={<AlertTriangle size={14} />} color={WARNING} items={warnings} />
        {warnings.length > 0 && notes.length > 0 && <div className="border-t border-white/6" />}
        <ListSection icon={<Info size={14} />} color={INFO} items={notes} />
      </div>
    </Card>
  )
}

export function AlternateCountsCard({ alternates }: { alternates: string[] }) {
  if (!alternates.length) return null
  return (
    <Card className="p-4 border border-white/6 w-full">
      <div className="flex items-center gap-2 mb-3 text-sm font-medium">
        <GitBranch size={15} style={{ color: ALT }} />
        <span>Alternate Counts</span>
      </div>
      <ListSection icon={<GitBranch size={14} />} color={ALT} items={alternates} />
    </Card>
  )
}
