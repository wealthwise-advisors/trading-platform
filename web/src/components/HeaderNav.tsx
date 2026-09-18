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
  BarChart2, BarChart3, CandlestickChart, FileText, LineChart, Search, Settings, Zap,
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
    title: "P&L distribution across the trades" },
  // THE SECOND "Analytics". The reference header carries the name twice, with
  // a line-chart icon and a bar-chart one, and this is the bar-chart half. It
  // opens Monthly Returns -- a real tab that no other section named, and the
  // one the bar-chart icon fits. The label is duplicated on purpose; the
  // titles are what tell the two apart on hover, and `current` keys on the
  // ITEM rather than on its label, so two items sharing a name cannot make
  // two pills light at once.
  { label: "Analytics", icon: BarChart2, page: "backtest", tab: "monthly",
    title: "Monthly returns, month by month" },
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
  const navSection = useConfigStore((s) => s.navSection)
  const goTo = useConfigStore((s) => s.goTo)

  // EXACTLY ONE PILL IS LIT, and it is the one you pressed.
  //
  // This used to be derived from (page, tab) alone, most-specific-wins. That
  // is right when you arrive somewhere by clicking a RESULTS tab, but wrong
  // when you click a SECTION: "Backtest" selects the results page without
  // naming a tab, so with resultsTab still "price" the derived rule lit
  // "Chart" instead -- pressing Backtest lit a different button, and Backtest
  // could never light at all while the price chart was open. The reference has
  // Backtest lit with the Chart tab active, which the derived rule cannot
  // produce.
  //
  // So an explicit choice wins while it still describes where we are, and the
  // derivation is the fallback for arriving by any other route.
  const navKey = (n: NavItem) => `${n.label}-${n.tab ?? n.page}`
  const chosen = NAV.find((n) => navKey(n) === navSection)
  const chosenStillFits = chosen
    && chosen.page === page
    && (chosen.tab === undefined || chosen.tab === resultsTab)
  const current = (chosenStillFits ? chosen : undefined)
    ?? NAV.find((n) => n.page === page && n.tab === resultsTab)
    ?? NAV.find((n) => n.page === page && !n.tab)
    ?? NAV.find((n) => n.page === page)

  return (
    <nav className="flex items-center gap-0.5 min-w-0 overflow-x-auto tabs-scroll" aria-label="Sections">
      {NAV.map((n) => (
        <button
          key={navKey(n)}
          type="button"
          title={n.title}
          aria-current={n === current ? "page" : undefined}
          onClick={() => goTo(n.page, n.tab, navKey(n))}
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
      <Search className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground/75"
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
        className="w-40 xl:w-52 rounded-lg border border-[color:var(--hairline-mid)] bg-[color:var(--raise-2)] py-1.5 pl-8 pr-3
                   text-xs text-foreground placeholder:text-muted-foreground/75 outline-none
                   focus:border-[color:var(--hairline-focus)]"
      />
      {open && q.trim() && (
        <ul className="absolute z-50 mt-1 w-full overflow-hidden rounded-lg border border-[color:var(--hairline-mid)]
                       bg-[var(--surface-1)] shadow-xl">
          {matches.map((s) => (
            <li key={s.symbol}>
              <button type="button" onClick={() => choose(s.symbol)}
                      className="flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left
                                 text-xs hover:bg-[color:var(--raise-3)]">
                <span className="font-semibold text-foreground">{s.symbol}</span>
                <span className="truncate text-muted-foreground">{s.name}</span>
              </button>
            </li>
          ))}
          {!matches.length && (
            <li className="px-3 py-2 text-xs text-muted-foreground/75">
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
        className="grid h-8 w-8 place-items-center rounded-full bg-[linear-gradient(135deg,var(--accent),#5a49d8)]
                   text-[11px] font-bold text-white ring-1 ring-[color:var(--hairline-firm)]"
      >
        {initials(user)}
      </button>
      {open && (
        <div role="menu"
             className="absolute right-0 z-50 mt-1 w-52 overflow-hidden rounded-lg border border-[color:var(--hairline-mid)]
                        bg-[var(--surface-1)] py-1 shadow-xl">
          <p className="truncate px-3 py-1.5 text-[11px] text-muted-foreground" title={user.email}>
            {user.full_name || user.username}
          </p>
          <button type="button" role="menuitem"
                  onClick={() => { setOpen(false); onOpenAccount() }}
                  className="block w-full px-3 py-1.5 text-left text-xs text-foreground hover:bg-[color:var(--raise-3)]">
            Account settings
          </button>
          <button type="button" role="menuitem"
                  onClick={async () => { await auth.logout(); window.location.assign(SIGN_IN_PAGE) }}
                  className="block w-full px-3 py-1.5 text-left text-xs text-foreground hover:bg-[color:var(--raise-3)]">
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}
