// The instrument chooser.
//
// A <Select> was fine at five symbols. At twenty-one across futures, metals,
// energy, single names and crypto it stopped being a list you scan and became
// one you hunt through -- so this is a searchable, filterable table instead.
//
// Categories are derived from the symbols actually returned, never hardcoded:
// the set changes per data source (synthetic has 11, Schwab 21, the CSV
// archive 12), and a chip that filters to nothing is worse than no chip. If
// no crypto is present, no Crypto chip is drawn.
//
// Favourites are per browser. They do not change what a run does, so they are
// deliberately NOT part of the config store -- nothing here can alter a
// backtest, only how quickly you find the symbol you meant.

import { useEffect, useMemo, useState } from "react"
import { Search, Star, ArrowUpDown, Check } from "lucide-react"
import { Dialog, DialogContent } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { SymbolMark, assetClassOf, type AssetClass } from "@/components/SymbolMark"
import type { SymbolMeta } from "@/lib/types"
import { cn } from "@/lib/utils"

const FAV_KEY = "instrument-favourites"

function loadFavourites(): string[] {
  try {
    const raw = localStorage.getItem(FAV_KEY)
    const v = raw ? JSON.parse(raw) : []
    return Array.isArray(v) ? v.filter((x) => typeof x === "string") : []
  } catch { return [] }
}

/** Chip definitions. `match` decides membership; a chip with no members is
 *  dropped before render rather than shown empty. */
const CATEGORIES: { id: string; label: string; match: (s: SymbolMeta) => boolean }[] = [
  { id: "indices", label: "Indices", match: (s) => ["index", "micro"].includes(assetClassOf(s.symbol)) },
  { id: "stocks", label: "Stocks", match: (s) => assetClassOf(s.symbol) === "equity" },
  { id: "energy", label: "Energy", match: (s) => assetClassOf(s.symbol) === "energy" },
  { id: "metals", label: "Metals", match: (s) => assetClassOf(s.symbol) === "metal" },
  { id: "crypto", label: "Crypto", match: (s) => assetClassOf(s.symbol) === "crypto" },
  {
    id: "futures", label: "Futures",
    match: (s) => (["index", "micro", "energy", "metal"] as AssetClass[])
      .includes(assetClassOf(s.symbol)),
  },
]

export function InstrumentPicker({
  open, onOpenChange, symbols, value, onSelect, sourceLabel,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  symbols: SymbolMeta[]
  value: string
  onSelect: (symbol: string) => void
  /** Name of the data source this list came from. */
  sourceLabel?: string
}) {
  const [q, setQ] = useState("")
  const [cat, setCat] = useState("all")
  const [favOnly, setFavOnly] = useState(false)
  const [asc, setAsc] = useState(true)
  const [favs, setFavs] = useState<string[]>(loadFavourites)
  // Staged: the row you clicked is not committed until Done, so opening the
  // dialog and closing it cannot change the symbol a run would use.
  const [staged, setStaged] = useState(value)

  useEffect(() => { if (open) { setStaged(value); setQ("") } }, [open, value])

  useEffect(() => {
    try { localStorage.setItem(FAV_KEY, JSON.stringify(favs)) } catch { /* private mode */ }
  }, [favs])

  const chips = useMemo(
    () => CATEGORIES.filter((c) => symbols.some(c.match)),
    [symbols],
  )

  // Each data source serves its own instruments -- synthetic can only model
  // the eleven futures its generator knows, so Apple and Bitcoin are absent
  // there and present under Schwab, Rithmic and the CSV archive. A short list
  // with no explanation reads as a missing instrument rather than a source
  // that does not carry it, so the reason is stated instead of inferred.
  const hasSpot = useMemo(
    () => symbols.some((x) => ["equity", "crypto"].includes(assetClassOf(x.symbol))),
    [symbols],
  )

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    const active = CATEGORIES.find((c) => c.id === cat)
    return symbols
      .filter((s) => (favOnly ? favs.includes(s.symbol) : true))
      .filter((s) => (active ? active.match(s) : true))
      .filter((s) => !needle
        || s.symbol.toLowerCase().includes(needle)
        || (s.name ?? "").toLowerCase().includes(needle)
        || (s.exchange ?? "").toLowerCase().includes(needle))
      .sort((a, b) => (asc ? 1 : -1) * a.symbol.localeCompare(b.symbol))
  }, [symbols, q, cat, favOnly, favs, asc])

  const toggleFav = (sym: string) =>
    setFavs((prev) => prev.includes(sym) ? prev.filter((x) => x !== sym) : [...prev, sym])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Select instrument"
                     description="Search and choose the instrument to run against">
        {/* search */}
        <div className="px-5 pt-4 pb-3 shrink-0">
          <div className="relative">
            <Search size={16} strokeWidth={2}
                    className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
            <Input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search instruments, symbols or markets…"
              aria-label="Search instruments"
              className="pl-10 h-11"
            />
          </div>

          {/* chips */}
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" onClick={() => { setCat("all"); setFavOnly(false) }}
                    aria-pressed={cat === "all" && !favOnly}
                    className={cn("cat-chip", cat === "all" && !favOnly && "cat-chip-on")}>
              All
            </button>
            {chips.map((c) => (
              <button key={c.id} type="button"
                      onClick={() => { setCat(c.id); setFavOnly(false) }}
                      aria-pressed={cat === c.id && !favOnly}
                      className={cn("cat-chip", cat === c.id && !favOnly && "cat-chip-on")}>
                {c.label}
              </button>
            ))}
            <button type="button" onClick={() => { setFavOnly((v) => !v); setCat("all") }}
                    aria-pressed={favOnly}
                    title={favs.length ? "Show only starred instruments" : "Star an instrument to build this list"}
                    className={cn("cat-chip ml-auto", favOnly && "cat-chip-on")}>
              <Star size={13} strokeWidth={2.2}
                    fill={favOnly ? "currentColor" : "none"} />
            </button>
          </div>
        </div>

        {sourceLabel && (
          <p className="px-5 pb-3 -mt-1 text-[11.5px] text-slate-500 shrink-0">
            Showing what <b className="text-slate-300 font-semibold">{sourceLabel}</b> can serve.
            {!hasSpot && " Equities and crypto come from Schwab, Rithmic or your CSV archive."}
          </p>
        )}

        {/* table */}
        <div className="flex-1 min-h-0 overflow-y-auto border-y border-white/8">
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10 bg-[#0d1526] text-slate-400">
              <tr>
                <th className="text-left py-2.5 pl-5 pr-2 font-bold text-[10.5px]
                               uppercase tracking-[0.08em] w-[150px]">
                  <button type="button" onClick={() => setAsc((v) => !v)}
                          className="inline-flex items-center gap-1.5 hover:text-slate-100
                                     transition-colors duration-150"
                          title={`Sort ${asc ? "Z to A" : "A to Z"}`}>
                    Symbol <ArrowUpDown size={12} strokeWidth={2.2} />
                  </button>
                </th>
                <th className="text-left py-2.5 px-2 font-bold text-[10.5px] uppercase tracking-[0.08em]">
                  Instrument
                </th>
                <th className="text-left py-2.5 px-2 font-bold text-[10.5px] uppercase tracking-[0.08em] w-[110px]">
                  Exchange
                </th>
                <th className="w-[54px]"><span className="sr-only">Favourite</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => {
                const on = staged === s.symbol
                const fav = favs.includes(s.symbol)
                return (
                  <tr
                    key={s.symbol}
                    onClick={() => setStaged(s.symbol)}
                    onDoubleClick={() => { onSelect(s.symbol); onOpenChange(false) }}
                    aria-selected={on}
                    className={cn("instr-row", on && "instr-row-on")}
                  >
                    <td className="py-2.5 pl-5 pr-2">
                      <span className="flex items-center gap-3">
                        <SymbolMark symbol={s.symbol} />
                        <span className="font-bold tabular-nums">{s.symbol}</span>
                      </span>
                    </td>
                    <td className="py-2.5 px-2 text-slate-300">{s.name}</td>
                    <td className="py-2.5 px-2">
                      {s.exchange && (
                        <span className={cn("exch-tag", on && "exch-tag-on")}>{s.exchange}</span>
                      )}
                      {!s.has_spec && (
                        <span className="ml-1.5 rounded px-1 py-px text-[9.5px] font-bold
                                         bg-amber-500/12 text-amber-400 ring-1 ring-amber-400/25"
                              title="No contract economics configured — P&L falls back to E-mini defaults">
                          NO SPEC
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 pr-4 text-right">
                      <button
                        type="button"
                        aria-label={`${fav ? "Unstar" : "Star"} ${s.symbol}`}
                        aria-pressed={fav}
                        onClick={(e) => { e.stopPropagation(); toggleFav(s.symbol) }}
                        className={cn("fav-btn", fav && "fav-btn-on")}
                      >
                        <Star size={17} strokeWidth={2} fill={fav ? "currentColor" : "none"} />
                      </button>
                    </td>
                  </tr>
                )
              })}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-12 text-center text-slate-500 text-[13px]">
                    Nothing matches {q ? <b className="text-slate-300">“{q}”</b> : "that filter"}.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* footer */}
        <div className="flex items-center gap-3 px-5 py-3.5 shrink-0">
          <span className="text-[11.5px] font-bold uppercase tracking-[0.08em] text-slate-500 tabular-nums">
            {rows.length} of {symbols.length} instruments
          </span>
          <Button variant="secondary" className="ml-auto"
                  onClick={() => { setQ(""); setCat("all"); setFavOnly(false) }}>
            Clear filters
          </Button>
          <Button onClick={() => { onSelect(staged); onOpenChange(false) }}>
            <Check size={15} strokeWidth={2.4} /> Done
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
