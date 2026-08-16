/**
 * Which VWAP band values agree across timeframes, to the whole number.
 *
 * On the replay tape each row is one timeframe and each band column (Upper
 * +1σ, Lower −1σ, Upper +2σ, …) holds one value per row. When two or more
 * timeframes land on the same price to the left of the decimal, that is a
 * level several timeframes concur on — worth seeing at a glance rather than
 * scanning columns by eye.
 *
 * Only the integer part counts. 7830.28 and 7830.19 agree; 7829.80 does not,
 * despite being nearer to 7830.19 than 7830.28 is to it. That is deliberate:
 * the whole number is the unit being compared against the reference platform,
 * and the same rule is already used for bar-construction parity.
 */

/** Truncate toward zero — "the part before the decimal", literally. */
export function wholePart(value: number): number {
  return Math.trunc(value)
}

/**
 * For each column, map each whole number to the labels of the rows carrying
 * it. A whole number with two or more labels is an agreement.
 *
 * @param rows   one array of column values per row, all the same length
 * @param labels one label per row, positionally matched (the timeframe names)
 */
export function bandAgreement(
  rows: Array<Array<number | null | undefined>>,
  labels: string[],
): Array<Map<number, string[]>> {
  const columns = rows.reduce((n, r) => Math.max(n, r.length), 0)
  const out: Array<Map<number, string[]>> = []

  for (let col = 0; col < columns; col++) {
    const byWhole = new Map<number, string[]>()
    rows.forEach((row, rowIndex) => {
      const v = row[col]
      // null is a band that has not been computed yet (no VWAP on this pane
      // yet); NaN would silently collide with itself as a Map key.
      if (v == null || !Number.isFinite(v)) return
      const w = wholePart(v)
      const seen = byWhole.get(w)
      if (seen) seen.push(labels[rowIndex])
      else byWhole.set(w, [labels[rowIndex]])
    })
    out.push(byWhole)
  }
  return out
}

/**
 * The other rows sharing this cell's whole number, or an empty array when the
 * value stands alone. A single row can never agree with itself, so a tape
 * showing one timeframe never highlights anything.
 */
export function agreeingLabels(
  agreement: Array<Map<number, string[]>>,
  col: number,
  value: number | null | undefined,
  self: string,
): string[] {
  if (value == null || !Number.isFinite(value)) return []
  const group = agreement[col]?.get(wholePart(value))
  if (!group || group.length < 2) return []
  return group.filter((l) => l !== self)
}
