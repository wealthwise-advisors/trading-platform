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
 * the whole set costs a few hundred bytes in the bundle. Nothing here imitates a
 * real exchange's or index provider's logo; each glyph depicts what the contract
 * IS -- a bullion stack for gold, a droplet for crude, a columned facade for the
 * Dow's industrials -- which is the honest version of the same recognition cue.
 *
 * WHY A SOLID DISC AND A KNOCKED-OUT GLYPH
 * ----------------------------------------
 * The first version tinted the disc to 12% opacity and drew the glyph in the
 * accent colour. On a near-black panel, at the size a select row actually gives
 * it, that renders as a faint grey smudge: the shape is present but nothing
 * reads. A saturated disc with the glyph knocked out of it is what every trading
 * terminal uses, for the reason that it survives being small.
 *
 * Light discs (gold, silver) take a dark glyph instead; see `markStyle`.
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
 * for NVDA would look exactly like the row for TSLA. Futures earn their colour
 * from the table below, but equities are one undifferentiated class, so the
 * ticker picks the hue. Deterministic, so a symbol keeps its colour between
 * sessions.
 *
 * The band 95-170deg is excluded, because that is where the green of a rising
 * candle lives and a mark must never read as a price direction. The first cut
 * excluded 100-160 and a ticker landed on exactly 160 -- hsl(160 70% 52%) is a
 * spring green, which is the colour this rule exists to avoid. The bound is a
 * little wider than the eye needs, on the principle that the cost of a slightly
 * cyan mark is nothing and the cost of a green one is a misread.
 */
const GREEN_BAND_START = 95
const GREEN_BAND_END = 170

function equityHue(symbol: string): number {
  let h = 0
  for (let i = 0; i < symbol.length; i++) h = (h * 31 + symbol.charCodeAt(i)) % 360
  const excluded = GREEN_BAND_END - GREEN_BAND_START
  const v = (h / 360) * (360 - excluded)
  return v < GREEN_BAND_START ? v : v + excluded
}

/**
 * The disc colour, per instrument rather than per family.
 *
 * Per-FAMILY colour was the defect worth naming: ES, NQ, YM and RTY are four
 * different contracts and all four drew the same violet disc, so the mark said
 * "index future" -- which the section heading already said -- and nothing more.
 * Eleven rows resolved to six colours. Each contract now owns one.
 *
 * The palette stays restrained: the blue family for the S&P/NASDAQ complex, the
 * commodity's real-world colour for the commodities, one indigo. Nothing sits in
 * the rising-candle green band, for the reason given in `equityHue`.
 */
const DISC: Record<string, string> = {
  // Equity index futures
  ES:  "#2563eb",   // S&P 500
  NQ:  "#0891b2",   // NASDAQ 100
  YM:  "#b45309",   // Dow Jones
  RTY: "#6366f1",   // Russell 2000
  // Micros: their parent's neighbour on the wheel, so a pair reads as related
  // without the two being confusable.
  MES: "#0d9488",
  MNQ: "#0ea5e9",
  MYM: "#a16207",
  M2K: "#8b5cf6",
  // Energy
  CL:  "#1e293b",   // crude: near-black, as the barrel is
  NG:  "#3b82f6",
  RB:  "#dc2626",
  HO:  "#78350f",
  // Metals: the metal's own colour, which is the entire point of these three
  GC:  "#eab308",
  SI:  "#94a3b8",
  HG:  "#c2703f",
  PL:  "#64748b",
  PA:  "#475569",
  // Crypto
  BTC: "#f7931a",
  ETH: "#627eea",
  SOL: "#14b8a6",
}

/** Fallback disc when the ticker is not in the table. */
const CLASS_DISC: Record<AssetClass, string> = {
  index: "#2563eb", micro: "#0d9488", energy: "#b45309", metal: "#eab308",
  crypto: "#f7931a", equity: "#2dd4bf", other: "#64748b",
}

const DARK_INK = "#0b1220"

/** Discs light enough that a white glyph would disappear into them. */
const LIGHT_DISCS = new Set(["SI", "GC"])

export interface MarkStyle {
  /** The filled circle. */
  disc: string
  /** The glyph knocked out of it. */
  ink: string
}

/**
 * Resolved colours for one instrument.
 *
 * Exported so a test can assert that no two contracts collide. The defect this
 * file was rewritten to fix -- four indices sharing one disc -- is invisible to a
 * render test and trivial to catch here.
 */
export function markStyle(symbol: string): MarkStyle {
  const s = symbol.toUpperCase()
  const cls = assetClassOf(s)
  const disc = DISC[s]
    ?? (cls === "equity" ? `hsl(${equityHue(s)} 70% 52%)` : CLASS_DISC[cls])
  return { disc, ink: LIGHT_DISCS.has(s) ? DARK_INK : "#ffffff" }
}

/**
 * The glyph, drawn on a 24x24 grid in a single colour.
 *
 * Deliberately simple silhouettes. At the size a select row gives this, anything
 * with interior detail turns to mush, and the ticker beside it is doing the
 * identifying work anyway -- the glyph only has to say what KIND of thing it is.
 *
 * `disc` is passed for the few glyphs that cut a gap in themselves (the copper
 * coins, the tower windows) rather than draw a line.
 */
function glyph(symbol: string, ink: string, disc: string) {
  const s = symbol.toUpperCase()

  // -- Equity index futures ------------------------------------------------
  // S&P 500: three ascending columns.
  if (s === "ES" || s === "MES")
    return (
      <g fill={ink}>
        <rect x="5.4" y="13.8" width="3.7" height="5.8" rx="1.1" />
        <rect x="10.15" y="10.2" width="3.7" height="9.4" rx="1.1" />
        <rect x="14.9" y="6.2" width="3.7" height="13.4" rx="1.1" />
      </g>
    )
  // NASDAQ 100: a bold zigzag, the shape of a tech tape.
  if (s === "NQ" || s === "MNQ")
    return (
      <path d="M5.2 17.6 9.7 10.4l3.6 4.4 5.5-8.6" fill="none" stroke={ink}
            strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    )
  // Dow Jones: a columned facade. Thirty industrials, the oldest index here.
  if (s === "YM" || s === "MYM")
    return (
      <g fill={ink}>
        <path d="M12 4.6 20.4 9.4H3.6z" />
        <rect x="4.4" y="10.4" width="15.2" height="1.5" rx=".5" />
        <rect x="6.3" y="12.6" width="2.3" height="5" rx=".4" />
        <rect x="10.85" y="12.6" width="2.3" height="5" rx=".4" />
        <rect x="15.4" y="12.6" width="2.3" height="5" rx=".4" />
        <rect x="3.9" y="18.2" width="16.2" height="1.9" rx=".6" />
      </g>
    )
  // Russell 2000: many thin bars. Small caps, and a lot of them.
  if (s === "RTY" || s === "M2K")
    return (
      <g fill={ink}>
        {([
          [4.7, 4.4], [7.0, 7.2], [9.3, 5.4], [11.6, 9.6],
          [13.9, 6.6], [16.2, 11.4], [18.5, 8.2],
        ] as const).map(([x, h]) => (
          <rect key={x} x={x} y={19.6 - h} width="1.75" height={h} rx=".55" />
        ))}
      </g>
    )

  // -- Energy --------------------------------------------------------------
  if (s === "CL")   // crude: a droplet
    return (
      <path d="M12 3.6c3.5 4.3 5.7 7.2 5.7 10A5.7 5.7 0 0 1 12 19.4 5.7 5.7 0 0 1 6.3 13.6c0-2.8 2.2-5.7 5.7-10z"
            fill={ink} />
    )
  // Natural gas: a flame. The first cut was a smooth teardrop, which rendered as
  // a near-copy of the crude droplet one row above it -- two energy contracts,
  // one silhouette. A flame needs the shoulder kink on the left AND the inner
  // cut-out; with only the outline it reverts to a droplet at this size.
  if (s === "NG")
    return (
      <g>
        <path d="M12 2.8c.7 3.2 3.2 4.7 4.4 6.9a7 7 0 0 1 1 3.5 5.4 5.4 0 0 1-10.8 0c0-2 1-3.8 2.6-5.5.2 1.1.7 1.9 1.4 2.4C10.2 7.6 11 5.2 12 2.8z"
              fill={ink} />
        <path d="M12 11.7c1.5 1.7 2.3 2.7 2.3 3.8a2.3 2.3 0 0 1-4.6 0c0-1.1.8-2.1 2.3-3.8z"
              fill={disc} />
      </g>
    )
  if (s === "RB" || s === "HO")   // refined products: a drop above a base
    return (
      <g fill={ink}>
        <path d="M12 4c2.9 3.6 4.7 6 4.7 8.3A4.7 4.7 0 0 1 12 17a4.7 4.7 0 0 1-4.7-4.7C7.3 10 9.1 7.6 12 4z" />
        <rect x="6" y="18.4" width="12" height="1.8" rx=".7" />
      </g>
    )

  // -- Metals --------------------------------------------------------------
  // Gold: the bullion stack, three bars pyramided.
  //
  // The gap between the rows is 1.8 units, not the 1.0 it started at. One unit
  // is 0.9px at the size a select row gives this, so the bars fused into a
  // single lump and the stack stopped being a stack. Same for silver below.
  if (s === "GC" || s === "PL" || s === "PA")
    return (
      <g fill={ink}>
        <path d="M8.4 11.2 9.2 6.9h5.6l.8 4.3z" />
        <path d="M4.0 17.1 4.9 12.8h5.6l.9 4.3z" />
        <path d="M13.0 17.1l.9-4.3h5.6l.9 4.3z" />
      </g>
    )
  // Silver: two bars, centred. A different silhouette from gold on purpose -- if
  // the only difference were the colour then GC and SI, one row apart, would be
  // identical to anyone who cannot separate yellow from grey.
  if (s === "SI")
    return (
      <g fill={ink}>
        {/* The top bar sits left of centre. Stacked symmetrically the two
            trapezoids read as a capital A, which is what the first cut looked
            like -- an offset is what makes a stack look stacked. */}
        <path d="M6.1 11.3 7.0 6.9h6.2l.9 4.4z" />
        <path d="M6.4 17.3 7.4 12.9h9.2l1 4.4z" />
      </g>
    )
  // Copper: a stack of coins, cut apart with the disc colour rather than a
  // stroke, so the separation holds at any size.
  if (s === "HG")
    return (
      <g fill={ink} stroke={disc} strokeWidth="1.1">
        <ellipse cx="12" cy="16.1" rx="6.5" ry="2.4" />
        <ellipse cx="12" cy="12.5" rx="6.5" ry="2.4" />
        <ellipse cx="12" cy="8.9" rx="6.5" ry="2.4" />
      </g>
    )

  // -- Crypto --------------------------------------------------------------
  if (s === "BTC")
    return <path d="M10 5h1.9v2H14a3.4 3.4 0 0 1 2 6 3.6 3.6 0 0 1-1.9 6.4V21h-1.9v-1.5h-1.3V21H9v-1.5H6.5v-2H8V7.5H6.5v-2H9V5h1zm0 4.5v3h3.4a1.5 1.5 0 0 0 0-3zm0 5v3.2h3.9a1.6 1.6 0 0 0 0-3.2z" fill={ink} />
  if (s === "ETH")
    return <path d="M12 3 6.5 12.2 12 15.4l5.5-3.2zM6.5 13.5 12 21l5.5-7.5L12 16.7z" fill={ink} />
  if (s === "SOL")
    return (
      <g fill={ink}>
        <path d="M6.4 7.4h11.8l-2.7 2.7H3.7z" />
        <path d="M6.4 10.7h11.8l-2.7 2.7H3.7z" />
        <path d="M6.4 14h11.8l-2.7 2.7H3.7z" />
      </g>
    )

  // -- Equities ------------------------------------------------------------
  // A corporate skyline. No company mark is used -- see the note at the top of
  // this file about trademarked artwork -- and the per-ticker hue is what tells
  // one single name from another.
  return (
    <g fill={ink}>
      <path d="M4.6 20.1V10.2h6V20.1z" />
      <path d="M11.9 20.1V4.9h7.5V20.1z" />
      <g fill={disc}>
        <rect x="6.2" y="12" width="1.5" height="1.5" rx=".3" />
        <rect x="6.2" y="15" width="1.5" height="1.5" rx=".3" />
        <rect x="13.6" y="7" width="1.6" height="1.6" rx=".3" />
        <rect x="16.4" y="7" width="1.6" height="1.6" rx=".3" />
        <rect x="13.6" y="10.4" width="1.6" height="1.6" rx=".3" />
        <rect x="16.4" y="10.4" width="1.6" height="1.6" rx=".3" />
        <rect x="13.6" y="13.8" width="1.6" height="1.6" rx=".3" />
        <rect x="16.4" y="13.8" width="1.6" height="1.6" rx=".3" />
      </g>
    </g>
  )
}

/**
 * Only an unrecognised ticker falls back to letters.
 *
 * The disc used to carry the ticker, which was fine while the row showed the
 * instrument name alone. The row now spells the ticker out -- "ES - E-mini S&P
 * 500" -- so a lettered disc beside it rendered "ES  ES - E-mini S&P 500". A
 * glyph says what KIND of instrument it is; the text says which one.
 */
function isLettered(cls: AssetClass): boolean {
  return cls === "other"
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
  const cls = assetClassOf(s)
  const { disc, ink } = markStyle(s)
  // A micro is its parent's glyph drawn small inside the same disc, which is
  // what the contract is. It also means the pair differ in more than hue, so
  // MES/ES stay apart for anyone who cannot separate the two colours.
  const micro = cls === "micro"
  // Unique per symbol: two marks on one screen sharing a gradient id would have
  // the second silently adopt the first.
  const gid = `sm-${s.replace(/[^A-Z0-9]/g, "")}`

  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24"
      className={className}
      role="img"
      aria-label={`${symbol} (${cls})`}
      // Inline, not a class: the select row applies `size-4` to any svg lacking a
      // size- class, which silently shrank this mark to 16px and was most of why
      // it read as a generic blob. An inline style outranks the utility.
      style={{ width: size, height: size, flexShrink: 0 }}
    >
      <defs>
        {/* A top-down sheen. Enough that the disc is not flat paper, far too
            little to read as a gradient in its own right. */}
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffffff" stopOpacity=".22" />
          <stop offset="55%" stopColor="#ffffff" stopOpacity="0" />
        </linearGradient>
      </defs>

      <circle cx="12" cy="12" r="11.3" fill={disc} />
      <circle cx="12" cy="12" r="11.3" fill={`url(#${gid})`} />

      {isLettered(cls) ? (
        <text x="12" y="12" textAnchor="middle" dominantBaseline="central"
              fill={ink} fontSize={tickerSize(s.length)} fontWeight="800"
              letterSpacing="-0.2"
              fontFamily="ui-sans-serif, system-ui, -apple-system, sans-serif">
          {s.slice(0, 4)}
        </text>
      ) : micro ? (
        <g transform="translate(12 12) scale(.72) translate(-12 -12)">
          {glyph(s, ink, disc)}
        </g>
      ) : (
        glyph(s, ink, disc)
      )}

      {/* A hairline rim INSIDE the disc, so a dark disc (crude) still has an
          edge against the panel and a light one (silver) does not glare.
          Straddling the edge at r=11.3 put half the stroke on the panel, where
          white at 22% over near-black reads as a dark halo -- it looked like a
          heavy border rather than a rim. */}
      <circle cx="12" cy="12" r="10.85" fill="none"
              stroke="rgba(255,255,255,.28)" strokeWidth=".9" />
    </svg>
  )
}

/**
 * One row of the symbol picker: mark, ticker, then the instrument name.
 *
 * Shared because the two pickers had already drifted -- the backtest panel drew
 * "ES - E-mini S&P 500" while the replay panel drew "ES E-mini S&P 500" with no
 * separator. Same list, same component, two different rows. One component now,
 * so they cannot disagree again.
 *
 * The ticker is what the eye looks for, so it carries the weight; the name is
 * support, so it recedes. The dash is muted further still, being punctuation.
 */
export function SymbolRow({ symbol, name }: { symbol: string; name?: string }) {
  const showName = name && name !== symbol
  return (
    <span className="flex min-w-0 items-center gap-2.5">
      <SymbolMark symbol={symbol} />
      <span className="font-semibold tracking-tight text-foreground">{symbol}</span>
      {showName && (
        <>
          <span aria-hidden className="text-muted-foreground/50">&mdash;</span>
          <span className="truncate text-muted-foreground">{name}</span>
        </>
      )}
    </span>
  )
}
