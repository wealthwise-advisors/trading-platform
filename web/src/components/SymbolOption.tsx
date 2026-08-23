// One row of the symbol picker, with the two facts SymbolRow does not carry.
//
// SymbolRow (components/SymbolMark) already draws the mark, the ticker and the
// instrument name, so this composes it rather than redrawing the same three
// spans -- both branches grew a version of that row while the other was
// unpushed, and one of them had to go.
//
// What it adds:
//
//   exchange  ES and MES are both "E-mini S&P 500" at a glance and differ only
//             in contract size; YM sits on CBOT while its siblings sit on CME.
//             Showing the venue makes that visible at the moment of choosing
//             rather than after a run priced on the wrong contract.
//
//   NO SPEC   without real contract economics the engine falls back to the
//             E-mini defaults and the resulting P&L is not the instrument's.
//             Better said in the list than left to be quietly wrong.

import { SymbolRow } from "@/components/SymbolMark"
import type { SymbolMeta } from "@/lib/types"

export function SymbolOption({ s }: { s: SymbolMeta }) {
  return (
    <span className="flex items-center gap-2 w-full min-w-0">
      <SymbolRow symbol={s.symbol} name={s.name} />

      {!s.has_spec && (
        <span
          className="shrink-0 rounded px-1 py-px text-[9.5px] font-bold tracking-wide
                     bg-amber-500/12 text-amber-400 ring-1 ring-amber-400/25"
          title="No contract economics configured — P&L falls back to E-mini defaults"
        >
          NO SPEC
        </span>
      )}

      {s.exchange && (
        <span className="ml-auto shrink-0 pl-3 text-[10.5px] font-semibold
                         tracking-[0.06em] text-slate-500">
          {s.exchange}
        </span>
      )}
    </span>
  )
}
