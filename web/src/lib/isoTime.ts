// Timestamp round-tripping for Plotly date axes.
//
// The API sends bar timestamps as naive wall-clock strings with no timezone
// marker ("2026-08-10T09:30:00"), and most traces hand them to Plotly
// untouched. Anywhere we do arithmetic on a timestamp we have to produce a
// string again, and it MUST use the same convention as the strings it sits
// beside: Plotly reads a trailing "Z" as UTC but a naive string as wall clock,
// so mixing the two silently shifts that trace by the browser's UTC offset.
//
// This is not hypothetical. Serializing resampled candle timestamps with
// new Date(ms).toISOString() placed every candle 5h30m left of the EMA lines
// on a UTC+05:30 machine -- roughly 4,900px outside the plot area -- so the
// price panel rendered with no candles at all while every other trace looked
// correct. getBBox() still reported correct 40px bodies for the clipped
// paths, which is why a geometry-only check did not catch it.
//
// Rule: never call toISOString() on a value derived from a naive timestamp.
// Use formatterFor(sample) so the output matches the input's convention.

const pad2 = (n: number) => String(n).padStart(2, "0")

/** Serialize ms to a naive wall-clock string -- the inverse of parsing one. */
export function toNaiveString(ms: number): string {
  const d = new Date(ms)
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}` +
         `T${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`
}

/**
 * Pick the serializer matching `sample`'s convention, so a derived timestamp
 * lands at the same axis position as the strings it was derived from.
 */
export function formatterFor(sample: string): (ms: number) => string {
  const zoned = /(?:Z|[+-]\d{2}:?\d{2})$/.test(sample)
  return zoned ? (ms: number) => new Date(ms).toISOString() : toNaiveString
}
