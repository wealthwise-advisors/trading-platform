/**
 * A mark identifying a data source in the picker.
 *
 * Drawn here for the same reasons SymbolMark is (see that file): no network in
 * the render path of a trading screen, no third-party artwork, and a stable
 * mark for sources that have no logo to fetch in the first place.
 *
 * The glyph says what KIND of data it is, which is the distinction that
 * actually matters when choosing: a cylinder for generated rows, a file for
 * your own CSVs, an aerial for a streaming account feed, candles for a real
 * market download. Colour reinforces the same split — green is the only live
 * account feed, so only that one is green.
 */

import { cn } from "@/lib/utils"

type SourceKind = "synthetic" | "file" | "live" | "market" | "other"

/** Maps a source id to its family. Substring-matched so a renamed id like
 *  "schwab_live" still lands on the right mark rather than the fallback. */
export function sourceKindOf(id: string): SourceKind {
  const s = id.toLowerCase()
  if (s.includes("synthetic") || s.includes("sample")) return "synthetic"
  if (s.includes("csv") || s.includes("file") || s.includes("external")) return "file"
  if (s.includes("schwab")) return "live"
  if (s.includes("rithmic")) return "market"
  return "other"
}

const TONE: Record<SourceKind, string> = {
  synthetic: "text-blue-400",
  file: "text-slate-300",
  live: "text-emerald-400",
  market: "text-sky-400",
  other: "text-slate-400",
}

function Glyph({ kind }: { kind: SourceKind }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  }

  switch (kind) {
    // Generated rows -- a database cylinder.
    case "synthetic":
      return (
        <svg viewBox="0 0 24 24" {...common}>
          <ellipse cx="12" cy="6" rx="7" ry="3" />
          <path d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6" />
          <path d="M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6" />
        </svg>
      )
    // Your own files -- a document with a folded corner.
    case "file":
      return (
        <svg viewBox="0 0 24 24" {...common}>
          <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z" />
          <path d="M14 3v5h5" />
          <path d="M8.5 15.5h2M13 13.5v4M15.5 13.5h2" strokeWidth={1.4} />
        </svg>
      )
    // A streaming account feed -- an aerial.
    case "live":
      return (
        <svg viewBox="0 0 24 24" {...common}>
          <path d="M12 10.5 8.5 21M12 10.5 15.5 21M9.6 17h4.8" />
          <circle cx="12" cy="8.5" r="1.6" />
          <path d="M8.4 5.2a5 5 0 0 0 0 6.6M15.6 5.2a5 5 0 0 1 0 6.6" />
          <path d="M6.1 2.8a8.4 8.4 0 0 0 0 11.4M17.9 2.8a8.4 8.4 0 0 1 0 11.4"
                strokeWidth={1.3} opacity={0.65} />
        </svg>
      )
    // A real market download -- price bars.
    case "market":
      return (
        <svg viewBox="0 0 24 24" {...common}>
          <path d="M6 4v3.5M6 16.5V20M17 4v5M17 18v2M11.5 3v4M11.5 17v4" strokeWidth={1.4} />
          <rect x="3.8" y="7.5" width="4.4" height="9" rx="1.1" />
          <rect x="14.8" y="9" width="4.4" height="9" rx="1.1" />
          <rect x="9.3" y="7" width="4.4" height="10" rx="1.1" opacity={0.55} />
        </svg>
      )
    default:
      return (
        <svg viewBox="0 0 24 24" {...common}>
          <circle cx="12" cy="12" r="8" />
          <path d="M12 8v4l2.5 2.5" />
        </svg>
      )
  }
}

export function SourceMark({ id, size = 20 }: { id: string; size?: number }) {
  const kind = sourceKindOf(id)
  return (
    <span
      aria-hidden
      className={cn("shrink-0 grid place-items-center", TONE[kind])}
      style={{ width: size, height: size }}
    >
      <Glyph kind={kind} />
    </span>
  )
}
