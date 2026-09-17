/**
 * The header's navigation, symbol search and account menu.
 *
 * EVERY ITEM GOES SOMEWHERE REAL. The reference design shows Chart, Strategy
 * Lab, Analytics and Reports beside Backtest and Market Grid. This app has no
 * separate "Strategy Lab" screen — it has a Strategy Optimizer tab, which is
 * the same thing under another name — so each link opens the view it names
 * rather than existing as decoration. A nav item that does nothing is worse
 * than one that is missing: it teaches the reader the app is broken.
 *
 * The one control from the reference that is NOT here is the light/dark
 * toggle. The palette, every panel surface, the rail cards and the Plotly
 * templates are all written for dark; a switch would produce a half-lit page,
 * and shipping a broken mode is worse than shipping one good one.
 */
import { useEffect, useMemo, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  BarChart3, CandlestickChart, FileText, LineChart, Search, Settings, Zap,
} from "lucide-react"

import { api, auth, SIGN_IN_PAGE, type Me } from "@/lib/api"
import { useConfigStore } from "@/store/configStore"

type Page = "backtest" | "replay" | "export"

interface NavItem {
  label: string
  icon: typeof BarChart3
  page: Page
  /** Results tab to open with it, where the name refers to one. */
  tab?: string
  title: string
}

const NAV: NavItem[] = [
  { label: "Chart", icon: CandlestickChart, page: "backtest", tab: "price",
    title: "The price chart with indicators, swings and trades" },
  { label: "Backtest", icon: BarChart3, page: "backtest",
    title: "Configure and run a backtest" },
  { label: "Market Grid", icon: Zap, page: "replay",
    title: "Replay the market bar by bar across timeframes" },
  { label: "Strategy Lab", icon: Settings, page: "backtest", tab: "optimizer",
    title: "Sweep a strategy's parameter grid and rank the runs" },
  { label: "Analytics", icon: LineChart, page: "backtest", tab: "pnl",
    title: "P&L distribution, monthly returns and the equity curve" },
  { label: "Reports", icon: FileText, page: "export",
    title: "Export raw bars, or download a full backtest report" },
]

/** Initials for the avatar: a person's own, never a placeholder. */
function initials(user: Me): string {
  const source = (user.full_name || user.username || user.email || "").trim()
  const parts = source.split(/[\s@._-]+/).filter(Boolean)
  const letters = parts.length > 1 ? parts[0][0] + parts[1][0] : source.slice(0, 2)
  return letters.toUpperCase()
}

export function HeaderNav() {
  const page = useConfigStore((s) => s.page)
  const resultsTab = useConfigStore((s) => s.resultsTab)
  const goTo = useConfigStore((s) => s.goTo)

  // EXACTLY ONE PILL IS LIT. "Backtest" matches any tab on the results page,
  // so a naive per-item test lit it alongside whichever specific view was
  // open -- two highlighted sections, which answers "where am I" with two
  // answers. The most specific match wins: an item naming a tab beats the
  // one that only names the page.
  const current = NAV.find((n) => n.page === page && n.tab === resultsTab)
    ?? NAV.find((n) => n.page === page && !n.tab)
    ?? NAV.find((n) => n.page === page)

  return (
    <nav className="flex items-center gap-1" aria-label="Sections">
      {NAV.map((n) => (
        <button
          key={n.label}
          type="button"
          title={n.title}
          aria-current={n === current ? "page" : undefined}
          onClick={() => goTo(n.page, n.tab)}
          className={`nav-pill${n === current ? " nav-pill-on" : ""}`}
        >
          <n.icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span className="hidden lg:inline">{n.label}</span>
        </button>
      ))}
    </nav>
  )
}

/**
 * Symbol search. Filters the instruments the CURRENT data source actually
 * serves and selects one — searching a list the backtest cannot run would be
 * a search box that lies.
 */
export function SymbolSearch() {
  const dataSource = useConfigStore((s) => s.dataSource)
  const setField = useConfigStore((s) => s.setField)
  const [q, setQ] = useState("")
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)

  const symbolsQ = useQuery({
    queryKey: ["symbols", dataSource],
    queryFn: () => api.symbols(dataSource),
    staleTime: 5 * 60_000,
  })

  const matches = useMemo(() => {
    const needle = q.trim().toUpperCase()
    if (!needle) return []
    return (symbolsQ.data ?? [])
      .filter((s) => s.symbol.toUpperCase().includes(needle) ||
                     s.name.toUpperCase().includes(needle))
      .slice(0, 8)
  }, [q, symbolsQ.data])

  // Clicking away closes the list; without this it hangs over the chart.
  useEffect(() => {
    const away = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", away)
    return () => document.removeEventListener("mousedown", away)
  }, [])

  const choose = (symbol: string) => {
    setField("symbol", symbol)
    setQ("")
    setOpen(false)
  }

  return (
    <div ref={box} className="relative hidden md:block">
      <Search className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500"
              aria-hidden />
      <input
        value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOpen(false)
          if (e.key === "Enter" && matches.length) choose(matches[0].symbol)
        }}
        placeholder="Search symbol (e.g., ES, NQ)…"
        aria-label="Search for an instrument"
        className="w-56 xl:w-72 rounded-lg border border-white/10 bg-white/[0.04] py-1.5 pl-8 pr-3
                   text-xs text-slate-200 placeholder:text-slate-500 outline-none
                   focus:border-white/25"
      />
      {open && q.trim() && (
        <ul className="absolute z-50 mt-1 w-full overflow-hidden rounded-lg border border-white/10
                       bg-[#12141c] shadow-xl">
          {matches.map((s) => (
            <li key={s.symbol}>
              <button type="button" onClick={() => choose(s.symbol)}
                      className="flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left
                                 text-xs hover:bg-white/5">
                <span className="font-semibold text-slate-100">{s.symbol}</span>
                <span className="truncate text-slate-400">{s.name}</span>
              </button>
            </li>
          ))}
          {!matches.length && (
            <li className="px-3 py-2 text-xs text-slate-500">
              {symbolsQ.isLoading ? "Loading instruments…" : "No instrument matches that."}
            </li>
          )}
        </ul>
      )}
    </div>
  )
}

/** The avatar, and the two things that used to be loose buttons in the bar. */
export function AccountMenu({ user, onOpenAccount }: { user: Me; onOpenAccount: () => void }) {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const away = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", away)
    return () => document.removeEventListener("mousedown", away)
  }, [])

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Account menu for ${user.full_name || user.username}`}
        title={user.email}
        className="grid h-8 w-8 place-items-center rounded-full bg-[linear-gradient(135deg,#9b8afb,#5a49d8)]
                   text-[11px] font-bold text-white ring-1 ring-white/15"
      >
        {initials(user)}
      </button>
      {open && (
        <div role="menu"
             className="absolute right-0 z-50 mt-1 w-52 overflow-hidden rounded-lg border border-white/10
                        bg-[#12141c] py-1 shadow-xl">
          <p className="truncate px-3 py-1.5 text-[11px] text-slate-400" title={user.email}>
            {user.full_name || user.username}
          </p>
          <button type="button" role="menuitem"
                  onClick={() => { setOpen(false); onOpenAccount() }}
                  className="block w-full px-3 py-1.5 text-left text-xs text-slate-200 hover:bg-white/5">
            Account settings
          </button>
          <button type="button" role="menuitem"
                  onClick={async () => { await auth.logout(); window.location.assign(SIGN_IN_PAGE) }}
                  className="block w-full px-3 py-1.5 text-left text-xs text-slate-200 hover:bg-white/5">
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}
