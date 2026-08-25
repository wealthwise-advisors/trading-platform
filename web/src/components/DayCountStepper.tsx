// "Number of Days" stepper, shared by Live Replay and Backtest.
//
// Presents the span of the existing inclusive start/end range and writes an end
// date back when changed. It holds no state of its own: the value shown is
// derived from the dates on every render, so editing a date field directly
// updates the number, and the two can never disagree.

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { daysInRange, MIN_RANGE_DAYS, MAX_RANGE_DAYS } from "@/lib/dayRange"

interface Props {
  startDate: string
  endDate: string
  /**
   * Applies a relative change. A DELTA, not an absolute date: the parent reads
   * the live end date when applying it, so a burst of clicks composes instead
   * of every click recomputing from the same rendered value.
   */
  onStep: (delta: number) => void
  disabled?: boolean
  /** Reason the control is locked, surfaced as a tooltip. */
  disabledReason?: string
  /**
   * Drop the built-in caption. For callers that already label the control in
   * their own layout -- Market Grid captions it alongside "Date range" so the
   * two groups match -- where rendering this too would show the words twice.
   * The number keeps its own aria-label, so nothing is lost to a screen reader.
   */
  hideLabel?: boolean
}

export function DayCountStepper({
  startDate, endDate, onStep, disabled, disabledReason, hideLabel,
}: Props) {
  // null when either date is mid-edit and unparseable; the stepper then shows a
  // dash rather than inventing a number and rewriting the other field.
  const days = daysInRange(startDate, endDate)
  const known = days != null

  const step = (delta: number) => {
    if (days == null) return
    onStep(delta)
  }

  const atMin = known && days <= MIN_RANGE_DAYS
  const atMax = known && days >= MAX_RANGE_DAYS

  return (
    <div className="space-y-1" title={disabled ? disabledReason : undefined}>
      {!hideLabel && <Label className="text-xs">Number of Days</Label>}
      <div className="flex items-center gap-1">
        <Button
          type="button" size="sm" variant="secondary"
          className="px-2 font-mono"
          aria-label="one day fewer"
          disabled={disabled || !known || atMin}
          onClick={() => step(-1)}
        >
          &minus;
        </Button>
        <span
          className="min-w-[2.5rem] text-center font-mono text-sm tabular-nums"
          aria-live="polite"
          aria-label="number of days"
        >
          {known ? days : "—"}
        </span>
        <Button
          type="button" size="sm" variant="secondary"
          className="px-2 font-mono"
          aria-label="one day more"
          disabled={disabled || !known || atMax}
          onClick={() => step(1)}
        >
          +
        </Button>
      </div>
      <p className="text-[11px] text-muted-foreground">
        {atMax
          ? `${MAX_RANGE_DAYS} is the furthest intraday history the provider serves`
          : "calendar days, both dates included"}
      </p>
    </div>
  )
}
