/**
 * The same page at a range of desktop widths.
 *
 * Not a screenshot diff. Pixel comparison across widths is a maintenance tax
 * that fires on every intentional change and says nothing about what broke.
 * These are claims that must hold at every size, each of which corresponds to
 * something that has actually gone wrong here before: cards overlapping by
 * 65px, five of seven nav sections silently scrolled out of reach, a popover
 * opening off the edge of the window.
 *
 * WIDE TABLES ARE EXPECTED TO OVERFLOW. Live state and the tape carry twenty-odd
 * columns and scroll sideways on purpose, so "past the right edge" only counts
 * when nothing between the element and the viewport can scroll.
 */

import { expect, test, type Page } from "@playwright/test"
import { goToMarketGrid, runBacktest, signIn } from "./helpers"

const WIDTHS = [
  { width: 1280, height: 800 },
  { width: 1440, height: 900 },
  { width: 1536, height: 864 },
  { width: 1670, height: 941 },
  { width: 1920, height: 1080 },
]

/** Elements past the right edge that nothing is scrolling. */
function escapees(page: Page) {
  return page.evaluate(() => {
    const de = document.documentElement
    let n = 0
    document.querySelectorAll("body *").forEach((el) => {
      const b = el.getBoundingClientRect()
      if (!(b.width > 0 && b.right > de.clientWidth + 2)) return
      for (let p = el.parentElement; p; p = p.parentElement) {
        const ox = getComputedStyle(p).overflowX
        if (ox === "auto" || ox === "scroll" || ox === "hidden") return
      }
      n++
    })
    return { escaped: n, pageScrollX: de.scrollWidth - de.clientWidth }
  })
}

test.describe("the backtest dashboard holds its shape", () => {
  test.describe.configure({ mode: "serial" })
  let page: Page

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage()
    await signIn(page)
    await runBacktest(page)
  })
  test.afterAll(async () => { await page.close() })

  for (const size of WIDTHS) {
    test(`at ${size.width}x${size.height}`, async () => {
      await page.setViewportSize(size)

      const state = await page.evaluate(() => {
        const cards = Array.from(document.querySelectorAll(".stat-card"))
          .map((e) => e.getBoundingClientRect())
        let overlaps = 0
        for (let i = 0; i < cards.length; i++) {
          for (let j = i + 1; j < cards.length; j++) {
            const a = cards[i], b = cards[j]
            if (a.left < b.right - 1 && b.left < a.right - 1
                && a.top < b.bottom - 1 && b.top < a.bottom - 1) overlaps++
          }
        }
        const nav = document.querySelector("header nav")
        return {
          cards: cards.length,
          overlaps,
          heights: Array.from(new Set(cards.map((c) => Math.round(c.height)))),
          navItems: nav ? nav.children.length : 0,
          navHidden: nav ? nav.scrollWidth - nav.clientWidth : 0,
          plotlyLogo: document.querySelectorAll(".js-plotly-plot a.modebar-btn--logo").length,
        }
      })

      expect(state.cards, "not eight KPI cards").toBe(8)
      expect(state.overlaps, "KPI cards are overlapping").toBe(0)
      expect(state.heights, "KPI cards differ in height").toHaveLength(1)
      expect(state.navItems, "the nav lost a section").toBe(7)
      expect(state.navHidden,
        "part of the nav is scrolled out of reach — it should wrap, not shrink").toBeLessThanOrEqual(2)
      expect(state.plotlyLogo, "a Plotly badge appeared").toBe(0)

      const over = await escapees(page)
      expect(over.pageScrollX, "the page scrolls sideways").toBeLessThanOrEqual(2)
      expect(over.escaped, "something is past the right edge with nothing scrolling it").toBe(0)
    })
  }
})

test.describe("market grid holds its shape", () => {
  test.describe.configure({ mode: "serial" })
  let page: Page

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage()
    await signIn(page)
    await goToMarketGrid(page)
  })
  test.afterAll(async () => { await page.close() })

  for (const size of WIDTHS) {
    test(`at ${size.width}x${size.height}`, async () => {
      await page.setViewportSize(size)

      const state = await page.evaluate(() => {
        const pills = Array.from(document.querySelectorAll("button.tf-pill"))
        const row = pills.length ? pills[0].parentElement : null
        const cards = Array.from(document.querySelectorAll(".preset-card, .custom-session"))
          .map((e) => e.getBoundingClientRect())
        let overlaps = 0
        for (let i = 0; i < cards.length; i++) {
          for (let j = i + 1; j < cards.length; j++) {
            const a = cards[i], b = cards[j]
            if (a.left < b.right - 1 && b.left < a.right - 1
                && a.top < b.bottom - 1 && b.top < a.bottom - 1) overlaps++
          }
        }
        return {
          pills: pills.length,
          pillsHidden: row ? row.scrollWidth - row.clientWidth : 0,
          overlaps,
          infoDots: document.querySelectorAll("button.info-dot").length,
        }
      })

      expect(state.pills, "a timeframe went missing").toBe(13)
      expect(state.pillsHidden, "timeframes are out of reach").toBeLessThanOrEqual(2)
      expect(state.overlaps, "session cards are overlapping").toBe(0)
      expect(state.infoDots, "an information button went missing").toBe(12)

      const over = await escapees(page)
      expect(over.pageScrollX, "the page scrolls sideways").toBeLessThanOrEqual(2)
      expect(over.escaped, "something is past the right edge with nothing scrolling it").toBe(0)

      // A popover near the right edge must stay on screen. This is the one
      // that used to open half off the window.
      const dot = page.locator("button[aria-label='About Speed']")
      await dot.scrollIntoViewIfNeeded()
      await dot.click()
      const dialog = page.getByRole("dialog")
      await expect(dialog).toBeVisible()
      const box = (await dialog.boundingBox())!
      expect(box.x, "a popover opened off the left edge").toBeGreaterThanOrEqual(0)
      expect(box.x + box.width, "a popover opened off the right edge")
        .toBeLessThanOrEqual(size.width + 1)
      await page.keyboard.press("Escape")
      await expect(dialog).toHaveCount(0)
    })
  }
})
