/**
 * A mark identifying a strategy in the picker.
 *
 * Drawn here, like SymbolMark and SourceMark, so nothing is fetched into the
 * render path and every strategy has a mark whether or not anyone drew a logo
 * for it.
 *
 * Each glyph is the strategy's own signal shape rather than a generic chart
 * icon: two lines crossing for the crossover, an oscillator between bands for
 * mean reversion, a break through a channel for Donchian, two lines pulling
 * apart for divergence. That means the list can be read by shape once the
 * names are familiar — which is the point of an icon in a list of five items
 * that all contain the word "RSI" or "trend".
 *
 * Colour is per strategy and stable, so the mark beside "Strategy" in a locked
 * setup panel is recognisable at a glance without reading the label.
 */

import { cn } from "@/lib/utils"

const TONE: Record<string, string> = {
  ma_crossover: "text-amber-400",
  rsi_mean_reversion: "text-violet-400",
  breakout: "text-emerald-400",
  rsi_divergence: "text-blue-400",
  regime_adaptive: "text-slate-300",
}

function Glyph({ id }: { id: string }) {
  const c = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  }

  switch (id) {
    // Two averages crossing — one solid (fast), one dashed (slow).
    case "ma_crossover":
      return (
        <svg viewBox="0 0 24 24" {...c}>
          <path d="M2.5 16.5C7 16.5 8.5 7.5 13 7.5s6 3 8.5 3" />
          <path d="M2.5 7.5C7 7.5 8.5 16.5 13 16.5s6-3 8.5-3" strokeDasharray="2.6 2.4" />
        </svg>
      )
    // An oscillator inside its overbought / oversold bands.
    case "rsi_mean_reversion":
      return (
        <svg viewBox="0 0 24 24" {...c}>
          <path d="M3 3v18h18" strokeWidth={1.5} />
          <path d="M5 7.5h15M5 16.5h15" strokeDasharray="2.4 2.2" strokeWidth={1.3} opacity={0.75} />
          <path d="M5.5 14l2.2-4 2 5.5 2.3-8 2.2 6 2.1-3.4 2.2 2.4" />
        </svg>
      )
    // A break up and out of the channel.
    case "breakout":
      return (
        <svg viewBox="0 0 24 24" {...c}>
          <path d="M3 19.5h17" strokeWidth={1.4} opacity={0.7} />
          <path d="M4 16.5l4-5 3.2 3 3.4-6.2 3.6 5" />
          <path d="M14.6 4.6h4.2v4.2" />
        </svg>
      )
    // Price and oscillator pulling apart — the divergence itself.
    case "rsi_divergence":
      return (
        <svg viewBox="0 0 24 24" {...c}>
          <path d="M3 6.5l6.5 3.2 5.5-2.2" strokeDasharray="2.6 2.2" />
          <path d="M15.2 5.6l3.4 1.6-1.9 2.7" strokeWidth={1.5} />
          <path d="M3.4 13.2l4.2 4.4 3.6-4 4.2 3.6" />
          <path d="M15 15.6l3.6 1.5-1.6 3" strokeWidth={1.5} />
        </svg>
      )
    // Picks its own regime — a gear with a trend inside it.
    case "regime_adaptive":
      return (
        <svg viewBox="0 0 24 24" {...c}>
          <path
            d="M12 2.6l1.5 1.9 2.4-.5.6 2.4 2.3.9-.7 2.3 1.6 1.9-1.6 1.9.7 2.3-2.3.9-.6 2.4-2.4-.5L12 21.4l-1.5-1.9-2.4.5-.6-2.4-2.3-.9.7-2.3L4.3 12.4l1.6-1.9-.7-2.3 2.3-.9.6-2.4 2.4.5Z"
            strokeWidth={1.4}
            opacity={0.85}
          />
          <path d="M8.6 14l2.3-2.6 1.9 1.7 2.7-3.4" strokeWidth={1.6} />
          <path d="M13.4 9.7h2.4v2.4" strokeWidth={1.4} />
        </svg>
      )
    default:
      return (
        <svg viewBox="0 0 24 24" {...c}>
          <path d="M3 17l5-6 4 3.5 4.5-8 4.5 6.5" />
        </svg>
      )
  }
}

export function StrategyMark({ id, size = 20 }: { id: string; size?: number }) {
  return (
    <span
      aria-hidden
      className={cn("shrink-0 grid place-items-center", TONE[id] ?? "text-sky-400")}
      style={{ width: size, height: size }}
    >
      <Glyph id={id} />
    </span>
  )
}
