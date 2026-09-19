/**
 * Getting to the screen under test, without sleeping.
 *
 * NO ARBITRARY WAITS ANYWHERE IN THIS SUITE. Every step below waits for the
 * thing it actually needs -- a field to exist, a heading to appear, a counter
 * to reach its total. A `waitForTimeout` is a guess about someone else's
 * machine: too short and it is flaky on a loaded CI box, too long and it is
 * dead time on every run forever. Playwright's assertions already retry until
 * a deadline, so waiting for the condition is both faster and more honest.
 */

import { expect, type Locator, type Page } from "@playwright/test"
import { E2E_PASSWORD, E2E_USER } from "./global-setup"

/** Sign in and land on the dashboard. */
export async function signIn(page: Page) {
  await page.goto("/")
  const user = page.locator("input[name='username'], #username")
  await expect(user).toBeVisible()
  await user.fill(E2E_USER)
  await page.locator("input[type='password']").fill(E2E_PASSWORD)
  await page.locator("button[type='submit']").first().click()

  // A brand-new account lands on onboarding, which is right for a person and
  // in the way of a test. Skip is on every step of it by design, so this takes
  // the same way out a user has.
  //
  // WAIT FOR EITHER, THEN DECIDE. Asking `isVisible()` straight after the
  // click reads the page before the sign-in response has rendered anything:
  // it answers false, the skip never happens, and the run then fails fifteen
  // seconds later on a nav that was never going to appear. `.or()` waits until
  // one of the two is actually on screen before anything is decided.
  const skip = page.getByRole("button", { name: "Skip" })
  const nav = page.getByRole("button", { name: "Market Grid" })
  await expect(skip.or(nav).first()).toBeVisible({ timeout: 30_000 })
  if (await skip.isVisible()) {
    await skip.click()
  }

  // The nav only exists once authenticated, so it is the signal that the
  // session cookie was accepted -- not merely that the POST returned.
  await expect(nav).toBeVisible()
}

/** The Backtest dashboard, with a finished synthetic run on screen. */
export async function runBacktest(page: Page) {
  await page.getByRole("button", { name: "Run Backtest" }).first().click()
  // The KPI row is the first thing that only exists once results have arrived.
  await expect(page.getByText("Total Return").first()).toBeVisible({ timeout: 150_000 })
  // The chart is lazy-loaded behind a dynamic import; without waiting for it,
  // any assertion about plot geometry races the chunk.
  await expect(page.locator(".js-plotly-plot").first()).toBeVisible({ timeout: 60_000 })
}

export async function goToMarketGrid(page: Page) {
  await page.getByRole("button", { name: "Market Grid" }).first().click()
  await expect(page.getByText("Instrument & strategy", { exact: false }).first()).toBeVisible()
}

/**
 * Load a Market Grid session and play it to the end.
 *
 * Waits on the tick counter reaching its own total rather than on the word
 * "Complete" appearing, because the counter carries the numbers and so says
 * what it is waiting for when it times out.
 */
export async function loadAndPlay(page: Page) {
  await page.getByRole("button", { name: "Load Data" }).first().click()
  await expect(page.getByText("Summary for")).toBeVisible({ timeout: 180_000 })

  const play = page.getByRole("button", { name: "Play" }).first()
  await expect(play).toBeEnabled()
  await play.click()

  const ticks = page.getByTestId("replay-ticks")
  await expect(ticks).toHaveAttribute("data-total", /^[1-9]/, { timeout: 30_000 })
  const total = await ticks.getAttribute("data-total")
  await expect(ticks).toHaveAttribute("data-processed", total!, { timeout: 180_000 })
}

/**
 * Widen the RSI window so the strategy actually trades.
 *
 * With the shipped defaults (overbought 94, oversold 2) a short synthetic
 * session can close zero trades, and the Recent trades panel does not render
 * at all when there are none. Home/End on the sliders is the keyboard path a
 * user has, so this exercises it rather than writing state directly.
 */
export async function widenRsiWindow(page: Page) {
  const over = page.locator("[role='slider'][aria-label='RSI Overbought']").first()
  await over.click()
  await over.press("Home")
  const under = page.locator("[role='slider'][aria-label='RSI Oversold']").first()
  await under.click()
  await under.press("End")
}

/** The chart's current x-axis start, as a string, for comparison. */
export function chartRangeStart(page: Page): Promise<string> {
  return page.evaluate(() => String(
    (document.querySelector(".js-plotly-plot") as unknown as
      { layout: { xaxis: { range: unknown[] } } }).layout.xaxis.range[0],
  ))
}

/**
 * Wait until the chart has stopped re-rendering.
 *
 * Not a sleep -- it waits for a CONDITION: the x-axis range reading the same
 * twice in a row. The chart is mounted before all of its data has arrived
 * (zigzag and trades are separate queries), and each arrival rebuilds the plot
 * from props, which re-applies the default window. A drag performed during
 * that window is silently undone, which is exactly the flake this removes:
 * the pan test failed on its first attempt and passed on the retry.
 */
export async function waitForChartSettled(page: Page) {
  let previous: string | null = null
  await expect
    .poll(async () => {
      const now = await chartRangeStart(page)
      const settled = previous !== null && now === previous
      previous = now
      return settled
    }, { message: "the chart never stopped re-rendering", timeout: 30_000 })
    .toBe(true)
}

/** The element that actually scrolls the page's content. */
export function scrollHost(page: Page) {
  return page.evaluate(() => {
    const host = Array.from(document.querySelectorAll("div")).find((e) => {
      const cs = getComputedStyle(e)
      return cs.overflowY === "auto" || cs.overflowY === "scroll"
    })
    if (!host) return null
    return {
      scrollHeight: host.scrollHeight,
      clientHeight: host.clientHeight,
      overflow: host.scrollHeight - host.clientHeight,
    }
  })
}

/**
 * Contrast of an element's text against what is ACTUALLY painted behind it.
 *
 * The naive version of this -- walk up until you find a background-color that
 * is not transparent -- is wrong here and was quietly giving false readings.
 * These panels are built from translucent `--raise-*` tints stacked over a
 * surface, and the app shell paints with a background IMAGE. So the walk found
 * nothing opaque, fell through to a hardcoded white, and reported a legible
 * dark-theme icon at 2.92 against a white page that was never there.
 *
 * This composites instead: collect every background layer from the element
 * upward, stop at the first fully opaque one, then blend back down. That is
 * what the compositor does, so the number matches what a reader sees.
 *
 * It also parses `color(srgb r g b)`, which is what color-mix() computes to in
 * this browser -- the old parser read those 0-to-1 components as 0-to-255 and
 * returned nonsense with total confidence.
 */
function contrastScript() {
  return (el: Element) => {
    type Rgba = { r: number; g: number; b: number; a: number }

    const parse = (c: string): Rgba | null => {
      if (!c || c === "none" || c === "transparent") return null
      // color(srgb 0.59 0.6 0.63 / 0.5)
      const srgb = c.match(/color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\)/i)
      if (srgb) {
        return { r: +srgb[1] * 255, g: +srgb[2] * 255, b: +srgb[3] * 255, a: srgb[4] ? +srgb[4] : 1 }
      }
      if (c.startsWith("#")) {
        const h = c.slice(1)
        const w = h.length >= 6
        const at = (i: number) => w
          ? parseInt(h.slice(i * 2, i * 2 + 2), 16)
          : parseInt(h[i] + h[i], 16)
        const a = w && h.length === 8 ? parseInt(h.slice(6, 8), 16) / 255 : 1
        return { r: at(0), g: at(1), b: at(2), a }
      }
      const n = c.match(/[\d.]+/g)
      if (!n || n.length < 3) return null
      return { r: +n[0], g: +n[1], b: +n[2], a: n.length > 3 ? +n[3] : 1 }
    }

    /** src over dst. */
    const over = (src: Rgba, dst: Rgba): Rgba => {
      const a = src.a + dst.a * (1 - src.a)
      if (a === 0) return { r: 0, g: 0, b: 0, a: 0 }
      const mix = (s: number, d: number) => (s * src.a + d * dst.a * (1 - src.a)) / a
      return { r: mix(src.r, dst.r), g: mix(src.g, dst.g), b: mix(src.b, dst.b), a }
    }

    const lum = (c: Rgba) => {
      const f = (v: number) => {
        const n = v / 255
        return n <= 0.03928 ? n / 12.92 : Math.pow((n + 0.055) / 1.055, 2.4)
      }
      return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b)
    }

    // Every background layer from the element up to the first opaque one.
    const layers: Rgba[] = []
    for (let e: Element | null = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e)
      const img = cs.backgroundImage
      if (img && img !== "none") {
        // A gradient's lightest stop: the worst case for pale text over it.
        const stops = (img.match(/rgba?\([^)]+\)|color\(srgb[^)]+\)|#[0-9a-f]{3,8}/gi) ?? [])
          .map(parse)
          .filter((c): c is Rgba => !!c && c.a > 0)
        if (stops.length) {
          layers.push(stops.reduce((a, b) => (lum(a) > lum(b) ? a : b)))
        }
      }
      const bg = parse(cs.backgroundColor)
      if (bg && bg.a > 0) {
        layers.push(bg)
        if (bg.a >= 1) break
      }
    }
    // Nothing opaque anywhere: the canvas is what shows through.
    const canvas = parse(getComputedStyle(document.documentElement).backgroundColor)
    const base: Rgba = layers.length && layers[layers.length - 1].a >= 1
      ? layers.pop()!
      : (canvas && canvas.a >= 1 ? canvas : { r: 255, g: 255, b: 255, a: 1 })

    let bg = base
    for (let i = layers.length - 1; i >= 0; i--) bg = over(layers[i], bg)

    const fgRaw = parse(getComputedStyle(el).color) ?? { r: 0, g: 0, b: 0, a: 1 }
    const fg = fgRaw.a >= 1 ? fgRaw : over(fgRaw, bg)

    const lf = lum(fg), lb = lum(bg)
    const [hi, lo] = lf > lb ? [lf, lb] : [lb, lf]
    return Number((((hi + 0.05) / (lo + 0.05))).toFixed(2))
  }
}

/** Contrast of an element's text against its real, composited backdrop. */
export async function contrastOf(target: Locator): Promise<number> {
  return target.evaluate(contrastScript())
}

/**
 * Assert a contrast ratio, on the SETTLED value.
 *
 * Two steps, and the order matters. These controls carry
 * `transition: background 180ms, color 180ms`, so a reading taken straight
 * after a theme switch catches the colours mid-sweep. Polling until the
 * assertion merely passes would be worse than useless here: a value that
 * starts fine and ends bad would pass on its first sample. So this waits for
 * two consecutive readings to agree -- the transition has finished -- and only
 * then judges the number.
 */
export async function expectContrast(target: Locator, min: number, what: string) {
  let previous = -1
  let current = -1
  await expect
    .poll(async () => {
      previous = current
      current = await contrastOf(target)
      return previous === current
    }, { message: `${what}: the colour never stopped changing` })
    .toBe(true)

  expect(current, `${what}: contrast ${current} is below ${min}`).toBeGreaterThanOrEqual(min)
}

/** Switch to the light theme and wait for it to actually apply. */
export async function useLightTheme(page: Page) {
  await page.getByRole("button", { name: "Switch to the light theme" }).first().click()
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light")
}
