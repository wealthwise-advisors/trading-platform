// The AutoTrader logo: the user's own artwork (2026-11-27, sent on WhatsApp) -- the
// silver "A" with the rising blue arrow over candles. Cropped to its rounded tile,
// so no black corners show in the light theme. The name beside it carries the
// logo's own colours: silver "Auto", blue-to-violet "Trader".
// public/favicon.png and apple-touch-icon.png are the same tile.

import logo from "@/assets/brand-logo.png"
import { cn } from "@/lib/utils"

export function BrandMark({ className }: { className?: string }) {
  return <img src={logo} alt="" aria-hidden className={cn("h-10 w-10 shrink-0 select-none", className)} draggable={false} />
}

/** Mark + name. `tagline` adds the one-line description under the name. */
export function BrandLogo({ tagline = false, className }: { tagline?: boolean; className?: string }) {
  return (
    <span className={cn("flex items-center gap-2.5 min-w-0", className)}>
      <BrandMark />
      <span className="min-w-0 leading-none">
        <span className="brand-name">Auto<span className="brand-name-accent">Trader</span></span>
        {tagline && <span className="brand-tagline">Research. Backtest. Trade Smarter.</span>}
      </span>
    </span>
  )
}
