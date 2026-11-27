// The oscillators, worked out in the browser so their lengths can be changed in the
// Studies panel (user, 2026-11-27). Same formulas as src/analysis/indicators.py --
// calc_rsi, calc_stochrsi, calc_mfi -- and oscCalc.test.ts holds them to its values.
// At the default lengths the chart keeps using the server's series.

type Num = number | null

/** pandas ewm(alpha=1/n, adjust=False, min_periods=n).mean(): Wilder's smoothing. */
function wilder(xs: readonly Num[], n: number): Num[] {
  const a = 1 / n
  let y: number | null = null, seen = 0
  return xs.map((x) => {
    if (x == null) return seen >= n ? y : null
    y = y == null ? x : (1 - a) * y + a * x
    seen += 1
    return seen >= n ? y : null
  })
}

/** pandas rolling(w).<fn>(): null unless all w values in the window are present. */
function rolling(xs: readonly Num[], w: number, fn: (win: number[]) => number): Num[] {
  return xs.map((_, i) => {
    if (i + 1 < w) return null
    const win = xs.slice(i + 1 - w, i + 1)
    return win.every((v) => v != null) ? fn(win as number[]) : null
  })
}
const sum = (w: number[]) => w.reduce((s, v) => s + v, 0)

export function rsi(close: readonly number[], n: number): Num[] {
  const d: Num[] = close.map((c, i) => (i === 0 ? null : c - close[i - 1]))
  const gain = wilder(d.map((v) => (v == null ? null : Math.max(v, 0))), n)
  const loss = wilder(d.map((v) => (v == null ? null : Math.max(-v, 0))), n)
  return gain.map((g, i) => {
    const l = loss[i]
    if (g == null || l == null) return null
    return 100 - 100 / (1 + g / (l === 0 ? 1e-10 : l))
  })
}

/** FullK and FullD: thinkorswim's StochRSI(rsiLength, …, kPeriod, dPeriod, slowing). */
export function stochRsi(close: readonly number[], rsiLength: number, kPeriod: number,
                         dPeriod: number, slowing = 1): { k: Num[]; d: Num[] } {
  const r = rsi(close, rsiLength)
  const lo = rolling(r, kPeriod, (w) => Math.min(...w))
  const hi = rolling(r, kPeriod, (w) => Math.max(...w))
  const raw: Num[] = r.map((v, i) => {
    const l = lo[i], h = hi[i]
    return v == null || l == null || h == null || h - l === 0 ? null : (100 * (v - l)) / (h - l)
  })
  const k = rolling(raw, slowing, (w) => sum(w) / w.length)
  return { k, d: rolling(k, dPeriod, (w) => sum(w) / w.length) }
}

/** thinkorswim's MoneyFlowIndex: positive flow over ALL flow, last `n` bars. */
export function mfi(bars: readonly { h: number; l: number; c: number; v: number }[], n: number): Num[] {
  const tp = bars.map((b) => (b.h + b.l + b.c) / 3)
  const flow = bars.map((b, i) => tp[i] * (b.v || 0))
  const pos: Num[] = flow.map((f, i) => (i === 0 ? null : tp[i] > tp[i - 1] ? f : 0))
  const all: Num[] = flow.map((f, i) => (i === 0 ? null : f))
  const ps = rolling(pos, n, sum), ts = rolling(all, n, sum)
  return ps.map((p, i) => {
    const t = ts[i]
    return p == null || t == null || t === 0 ? null : (100 * p) / t
  })
}
