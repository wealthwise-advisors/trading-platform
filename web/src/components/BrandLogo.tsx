// The AutoTrader logo (redesigned 2026-11-27, user: "redesign the logo also").
//
// A rising swing (the app's core idea: swings counted leg by leg) in white on a
// blue-to-violet tile, beside the name set in the app's own type. Vector, so it
// stays sharp at 16px and at 64px; the old poster crops blurred below 36px.
// public/favicon.svg is the same mark.

import { cn } from "@/lib/utils"

export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("h-9 w-9 shrink-0", className)} aria-hidden focusable="false">
      <defs>
        <linearGradient id="brand-tile" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2F80FF" />
          <stop offset="1" stopColor="#7C3AED" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="url(#brand-tile)" />
      <path d="M6.5 22 L12 15.5 L16 19 L24.5 9.5" fill="none" stroke="#fff" strokeWidth="2.6"
            strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="24.5" cy="9.5" r="2.4" fill="#fff" />
      <path d="M6.5 26 H25.5" stroke="#fff" strokeOpacity=".35" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
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
