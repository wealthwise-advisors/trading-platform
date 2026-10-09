/**
 * The in-panel timeframe toggles.
 *
 * Shared by the Consolidated tape and the Live state table. Both ask the same
 * question -- "which timeframes is this panel answering for?" -- and both used
 * to be answerable only from the selector at the top of the page, which means
 * scrolling away from the table you are reading to change what it shows.
 *
 * One component rather than two copies because they must stay identical: these
 * are the SAME selection, not two filters. Ticking 15m here adds the 15m pane
 * everywhere, and a second copy that drifted would read as two independent
 * controls that mysteriously move together.
 *
 * Keeps the `tape-pill` class it shipped under. The class is styling, not a
 * statement about which panel it belongs to, and renaming it would ripple into
 * the light-theme contrast test that pins `.tape-pill` by name -- a rename
 * with no behaviour behind it is not worth a red suite.
 */

export function TimeframePills({
  all,
  selected,
  onToggle,
  refetchReason,
  ariaPrefix,
  describe,
}: {
  all: readonly string[]
  selected: readonly string[]
  onToggle: (tf: string) => void
  /** Why ticking this timeframe costs a refetch, or null when it is free. */
  refetchReason: (tf: string) => string | null
  /** Distinguishes the two panels' buttons for the accessibility tree. */
  ariaPrefix: string
  /** The tooltip for a pill, given whether it is currently on. */
  describe: (tf: string, on: boolean) => string
}) {
  return (
    <div className="flex flex-wrap gap-1">
      {all.map((tf) => {
        const on = selected.includes(tf)
        const refetch = refetchReason(tf)
        return (
          <button
            key={tf}
            type="button"
            className={`tape-pill${on ? " tape-pill-on" : ""}`}
            aria-pressed={on}
            aria-label={`${ariaPrefix} ${tf}`}
            title={refetch ?? describe(tf, on)}
            onClick={() => onToggle(tf)}
          >
            {tf}
            {/* A refetch is a real cost -- it goes back to the source for bars
                the loaded set cannot be built from -- so it is marked before
                the click, not explained after it. */}
            {refetch && <span className="ml-0.5 opacity-60">↻</span>}
          </button>
        )
      })}
    </div>
  )
}
