/**
 * A small mark identifying an instrument in the symbol picker.
 *
 * WHY DRAWN RATHER THAN FETCHED
 * -----------------------------
 * The obvious approach is a logo service keyed on the ticker. Three problems:
 * futures have no company behind them, so ES/NQ/CL/GC would fall back to a blank
 * every time; it puts a third-party host in the render path of a trading screen
 * that has to work when the network is unhappy; and it means shipping other
 * companies' trademarked artwork in a commercial product.
 *
 * So these are drawn here. Every instrument gets a mark, nothing is fetched, and
 * the whole set costs a few hundred bytes in the bundle.
 *
 * The colour carries the asset class, which is the thing worth seeing at a glance
 * in a list of twenty-one: index futures read as one family, metals as another.
 * The glyph is the instrument's own shorthand -- a bull for the Dow, a droplet for
 * crude -- with the ticker itself alongside in the row, so the mark supports
 * recognition rather than replacing the name.
 */

export type AssetClass =
  | "index" | "micro" | "energy" | "metal" | "crypto" | "equity" | "other"

/** Which family an instrument belongs to. Order matters: MES/MNQ before ES/NQ. */
export function assetClassOf(symbol: string): AssetClass {
  const s = symbol.toUpperCase()
  if (["MES", "MNQ", "MYM", "M2K"].includes(s)) return "micro"
  if (["ES", "NQ", "YM", "RTY"].includes(s)) return "index"
  if (["CL", "NG", "RB", "HO"].includes(s)) return "energy"
  if (["GC", "SI", "HG", "PL", "PA"].includes(s)) return "metal"
  if (["BTC", "ETH", "SOL"].includes(s)) return "crypto"
  // Anything left with a letter-only ticker of 1-5 chars is an equity here;
  // the contract list is futures, metals, crypto and US single names.
  if (/^[A-Z]{1,5}$/.test(s)) return "equity"
  return "other"
}

/**
 * A stable hue per equity ticker.
 *
 * Nine single names sharing one teal would defeat the point of the mark: the row
 * for NVDA would look exactly like the row for TSLA. Futures earn their colour from
 * their asset class, but equities are all one class, so the ticker itself picks the
 * hue. Deterministic, so a symbol keeps the same colour between sessions.
 *
 * The band avoids 100-160deg, which is where the green of a rising candle lives --
 * a mark should not read as a price direction.
 */
function equityHue(symbol: string): number {
  let h = 0
  for (let i = 0; i < symbol.length; i++) h = (h * 31 + symbol.charCodeAt(i)) % 360
  const span = 360 - 60
  const v = (h / 360) * span
  return v < 100 ? v : v + 60
}

const PALETTE: Record<AssetClass, { fg: string; bg: string; ring: string }> = {
  index:  { fg: "#8b5cf6", bg: "rgba(139,92,246,.12)",  ring: "rgba(139,92,246,.45)" },
  micro:  { fg: "#10b981", bg: "rgba(16,185,129,.12)",  ring: "rgba(16,185,129,.42)" },
  energy: { fg: "#f59e0b", bg: "rgba(245,158,11,.12)",  ring: "rgba(245,158,11,.45)" },
  // Gold's amber. Silver and copper override it below -- three metals sharing one
  // colour made GC, SI and HG a single block in the list.
  metal:  { fg: "#fbbf24", bg: "rgba(251,191,36,.10)",  ring: "rgba(251,191,36,.40)" },
  crypto: { fg: "#a78bfa", bg: "rgba(167,139,250,.12)", ring: "rgba(167,139,250,.45)" },
  equity: { fg: "#2dd4bf", bg: "rgba(45,212,191,.12)",  ring: "rgba(45,212,191,.42)" },
  other:  { fg: "#94a3b8", bg: "rgba(148,163,184,.12)", ring: "rgba(148,163,184,.35)" },
}

/**
 * The glyph inside the mark, drawn on a 24x24 grid.
 *
 * Deliberately simple shapes: at 22px on screen anything detailed turns to mush,
 * and the ticker text beside it is doing the identifying work anyway.
 */
function glyph(symbol: string, fg: string) {
  const s = symbol.toUpperCase()

  // Index futures — a rising bar chart, one per index's character.
  if (s === "ES" || s === "MES")
    return <path d="M6 16.5h2.6v3.2H6zM10.7 12h2.6v7.7h-2.6zM15.4 7.5H18v12.2h-2.6z" fill={fg} />
  if (s === "NQ" || s === "MNQ")
    return <path d="M6 19.5 10.2 12l3.4 4.2L18 5.4l1.6 1-5 12-3.5-4.3L7 20z" fill={fg} />
  if (s === "YM" || s === "MYM")   // the Dow: an ascending step, thirty names
    return <path d="M5 19.5h3.4V14H5zm4.9 0h3.4V9.5H9.9zm4.9 0h3.4V5h-3.4z" fill={fg} />
  if (s === "RTY" || s === "M2K")  // small caps: many small blocks
    return <path d="M5 15h3v5H5zm4.5-3h3v8h-3zM14 16.5h3V20h-3zm4.5-8h3V20h-3z" fill={fg} />

  // Energy
  if (s === "CL")                  // crude: a droplet
    return <path d="M12 3.5c3.4 4.2 5.6 7 5.6 9.8A5.6 5.6 0 0 1 12 19a5.6 5.6 0 0 1-5.6-5.7c0-2.8 2.2-5.6 5.6-9.8z" fill={fg} />
  if (s === "NG")                  // natural gas: a flame
    return <path d="M12 3c.6 3.1 3.9 4.3 3.9 8.2A3.9 3.9 0 0 1 12 15a3.9 3.9 0 0 1-3.9-3.8C8.1 8.6 9.6 8 10 5.9c.9.9 1.4 2 1.4 3.2C12.6 8 12.4 5.4 12 3z" fill={fg} />

  // Metals — a stack of bars, heavier for the denser metal.
  if (s === "GC")
    return <path d="M4 15.5h7l1.2 4H5.2zm9 0h7l1 4h-7.8zM8.5 10h7l1.2 4H9.7z" fill={fg} />
  if (s === "SI")
    return <path d="M5 16h6l1 3.5H6zm8 0h6l1 3.5h-6.9zM9 11h6l1 3.5h-6.9z" fill={fg} />
  if (s === "HG")                  // copper: wire wound into a coil
    return (
      <g fill="none" stroke={fg} strokeWidth="2" strokeLinecap="round">
        <circle cx="12" cy="12" r="6.4" />
        <circle cx="12" cy="12" r="2.6" />
      </g>
    )

  // Crypto
  if (s === "BTC")
    return <path d="M10 5h1.9v2H14a3.4 3.4 0 0 1 2 6 3.6 3.6 0 0 1-1.9 6.4V21h-1.9v-1.5h-1.3V21H9v-1.5H6.5v-2H8V7.5H6.5v-2H9V5h1zm0 4.5v3h3.4a1.5 1.5 0 0 0 0-3zm0 5v3.2h3.9a1.6 1.6 0 0 0 0-3.2z" fill={fg} />
  if (s === "ETH")
    return <path d="M12 3 6.5 12.2 12 15.4l5.5-3.2zM6.5 13.5 12 21l5.5-7.5L12 16.7z" fill={fg} />

  return null   // handled as a lettered badge by SymbolMark
}

/** Families drawn as a filled circle carrying the ticker, rather than a glyph. */
function isLettered(cls: AssetClass): boolean {
  return cls === "index" || cls === "micro" || cls === "equity" || cls === "other"
}

/** Ticker text scaled so four characters still fit inside the circle. */
function tickerSize(len: number): number {
  if (len <= 2) return 9.5
  if (len === 3) return 8
  return 6.6
}

interface Props {
  symbol: string
  /** Rendered size in px. 22 suits a select row; 28 suits a header. */
  size?: number
  className?: string
}

export function SymbolMark({ symbol, size = 22, className }: Props) {
  const s = symbol.toUpperCase()
  const cls = assetClassOf(symbol)
  let { fg, bg, ring } = PALETTE[cls]
  const lettered = isLettered(cls)
  // Per-instrument overrides where one class colour is not enough.
  if (s === "SI") {          // silver, not gold
    fg = "#cbd5e1"; bg = "rgba(203,213,225,.12)"; ring = "rgba(203,213,225,.40)"
  } else if (s === "HG") {   // copper
    fg = "#fb923c"; bg = "rgba(251,146,60,.12)"; ring = "rgba(251,146,60,.42)"
  }
  // The design gives each index its own disc colour rather than one blue for the
  // family, so ES, NQ, YM and RTY are told apart before the ticker is read.
  const DISC: Record<string, string> = {
    ES: "#8b5cf6", NQ: "#3b82f6", YM: "#eab308", RTY: "#a855f7",
    MES: "#10b981", MNQ: "#14b8a6",
  }
  if (DISC[s]) fg = DISC[s]
  if (cls === "equity") {
    const h = equityHue(s)
    fg = `hsl(${h} 78% 66%)`
    bg = `hsl(${h} 78% 66% / .12)`
    ring = `hsl(${h} 78% 66% / .42)`
  }
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24"
      className={className}
      role="img"
      aria-label={`${symbol} (${cls})`}
      style={{ flexShrink: 0 }}
    >
      {lettered ? (
        <>
          {/* Solid disc, ticker in white. An index future is known by its ticker;
              a glyph would be an extra step between reading and recognising. */}
          <circle cx="12" cy="12" r="11.25" fill={fg} />
          <text x="12" y="12" textAnchor="middle" dominantBaseline="central"
                fill="#0b0f17" fontSize={tickerSize(s.length)} fontWeight="800"
                letterSpacing="-0.2"
                fontFamily="ui-sans-serif, system-ui, -apple-system, sans-serif">
            {s.slice(0, 4)}
          </text>
        </>
      ) : (
        <>
          <circle cx="12" cy="12" r="11.25" fill={bg} stroke={ring} strokeWidth="1.5" />
          {glyph(s, fg)}
        </>
      )}
    </svg>
  )
}
