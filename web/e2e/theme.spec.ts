/**
 * The light theme, measured rather than eyeballed.
 *
 * Every tinted thing on these pages is built with `color-mix(... , transparent)`
 * over a themed surface. That composes beautifully on a dark ground and can
 * wash out to nothing on a light one, and the failure is invisible unless you
 * open the light theme and look -- which is exactly how `.tape-pill` shipped
 * with `#8ea3bd` on `#111c30` hardcoded, rendering near-black on a white page.
 *
 * WCAG AA wants 4.5:1 for body text and 3:1 for user-interface components.
 * Icon-only buttons are judged at 3, text at 4.5.
 */

import { expect, test, type Page } from "@playwright/test"
import { contrastOf, expectContrast, goToMarketGrid, signIn, useLightTheme } from "./helpers"

const UI = 3.0
const TEXT = 4.5

test.describe("light theme", () => {
  test.describe.configure({ mode: "serial" })
  let page: Page

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage()
    await signIn(page)
    await useLightTheme(page)
    await goToMarketGrid(page)
  })
  test.afterAll(async () => { await page.close() })

  test("the information buttons are legible", async () => {
    await expectContrast(page.locator("button.info-dot").first(), UI,
      "the circled 'i' has faded into its own button")
  })

  test("panel headings and section labels are legible", async () => {
    for (const [what, locator] of [
      ["section heading", page.locator("h2").first()],
      ["field label", page.locator("label").first()],
    ] as const) {
      const box = await locator.boundingBox()
      if (!box) continue
      await expectContrast(locator, TEXT, `${what} is too faint on a light ground`)
    }
  })

  test("the timeframe pills follow the palette, both states", async () => {
    const off = page.locator("button.tf-pill:not(.tf-pill-on)").first()
    const on = page.locator("button.tf-pill.tf-pill-on").first()

    // The bug this exists for: a pill whose background is a dark literal
    // rather than a token reads as a hole punched in a white page.
    const offBg = await off.evaluate((el) => getComputedStyle(el).backgroundColor)
    const pageBg = await page.evaluate(() => {
      for (let e: Element | null = document.querySelector("main"); e; e = e.parentElement) {
        const c = getComputedStyle(e).backgroundColor
        if (c && !/rgba\(0, 0, 0, 0\)|transparent/.test(c)) return c
      }
      return "rgb(255,255,255)"
    })
    const lum = (c: string) => {
      const [r, g, b] = (c.match(/\d+/g) ?? ["0", "0", "0"]).slice(0, 3).map(Number)
      return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    }
    expect(
      Math.abs(lum(offBg) - lum(pageBg)),
      `an unselected pill (${offBg}) is nothing like the page (${pageBg}) — `
      + "it is probably using a hardcoded dark colour instead of a theme token",
    ).toBeLessThan(0.35)

    await expectContrast(off, TEXT, "unselected pill label")
    await expectContrast(on, UI, "selected pill label")
  })

  test("the tape's own pills follow it too", async () => {
    // Same rule, different component: .tape-pill is a separate class that had
    // its own hardcoded pair.
    const pill = page.locator("button.tape-pill").first()
    if (await pill.count() === 0) test.skip(true, "tape pills only exist once a session is loaded")
    await expectContrast(pill, TEXT, "tape pill label")
  })

  test("dark theme still reads, so the tokens work both ways", async () => {
    await page.getByRole("button", { name: "Switch to the dark theme" }).first().click()
    await expect(page.locator("html")).not.toHaveAttribute("data-theme", "light")

    await expectContrast(page.locator("button.tf-pill:not(.tf-pill-on)").first(), TEXT,
      "unselected pill label in dark")
    await expectContrast(page.locator("button.info-dot").first(), UI,
      "the circled 'i' in dark")
  })
})
