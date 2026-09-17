"use client"

import * as React from "react"
import { Slider as SliderPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

function Slider({
  className,
  defaultValue,
  value,
  min = 0,
  max = 100,
  // THE NAME HAS TO REACH THE THUMB.
  // `role="slider"` is on the thumb, not the root, so an aria-label spread onto
  // the root names an element that has no role to be named -- and a screen
  // reader announces the control as just "slider". Pulled out of props here and
  // put on each thumb instead. axe reported this as aria-input-field-name on
  // five thumbs in the backtest panel, every one of which already passed a
  // label in.
  "aria-label": ariaLabel,
  "aria-labelledby": ariaLabelledBy,
  ...props
}: React.ComponentProps<typeof SliderPrimitive.Root>) {
  const _values = React.useMemo(
    () =>
      Array.isArray(value)
        ? value
        : Array.isArray(defaultValue)
          ? defaultValue
          : [min, max],
    [value, defaultValue, min, max]
  )

  return (
    <SliderPrimitive.Root
      data-slot="slider"
      defaultValue={defaultValue}
      value={value}
      min={min}
      max={max}
      className={cn(
        "relative flex w-full touch-none items-center select-none data-disabled:opacity-50 data-vertical:h-full data-vertical:min-h-40 data-vertical:w-auto data-vertical:flex-col",
        className
      )}
      {...props}
    >
      <SliderPrimitive.Track
        data-slot="slider-track"
        className="relative grow overflow-hidden rounded-full bg-[color:var(--raise-4)] data-horizontal:h-1.5 data-horizontal:w-full data-vertical:h-full data-vertical:w-1"
      >
        <SliderPrimitive.Range
          data-slot="slider-range"
          className="absolute rounded-full bg-[var(--primary)] shadow-[0_0_10px_color-mix(in_srgb,var(--primary)_55%,transparent)] select-none data-horizontal:h-full data-vertical:w-full"
        />
      </SliderPrimitive.Track>
      {Array.from({ length: _values.length }, (_, index) => (
        <SliderPrimitive.Thumb
          data-slot="slider-thumb"
          key={index}
          // A range slider's two thumbs would otherwise share one name, leaving
          // them indistinguishable in a screen reader's list of controls.
          aria-label={
            ariaLabel && _values.length > 1 ? `${ariaLabel} ${index + 1}` : ariaLabel
          }
          aria-labelledby={ariaLabelledBy}
          className="relative block size-4 shrink-0 rounded-full border-2 border-[var(--accent)] bg-white ring-[var(--accent)]/40 shadow-[0_0_12px_color-mix(in_srgb,var(--primary)_70%,transparent)] transition-[color,box-shadow] select-none after:absolute after:-inset-2 hover:ring-3 focus-visible:ring-3 focus-visible:outline-hidden active:ring-3 disabled:pointer-events-none disabled:opacity-50"
        />
      ))}
    </SliderPrimitive.Root>
  )
}

export { Slider }
