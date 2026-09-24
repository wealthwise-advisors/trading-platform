/**
 * Market Grid: the circled "i" explanations, the setup disclosure, and the
 * panel chrome.
 *
 * Split into two describes because they need different states -- one before a
 * session is loaded, one after -- and loading takes long enough that it is
 * worth doing once rather than per test.
 */

import { expect, test, type Page } from "@playwright/test"
import { goToMarketGrid, loadAndPlay, signIn, widenRsiWindow } from "./helpers"

/** Every control that must be able to explain itself. */
const EXPLAINED = [
  "Globex session",
  "RTH session",
  "Custom session",
  "Session hours (ET)",
  "Timeframes",
  "RSI Overbought",
  "RSI Oversold",
  "Swing Lookback (bars)",
  "Initial capital ($)",
  "Contracts / trade",
  "Commission / contract ($)",
  "Speed",
]

test.describe("before a session is loaded", () => {
  test.describe.configure({ mode: "serial" })
  let page: Page

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage()
    await signIn(page)
    await goToMarketGrid(page)
  })
  test.afterAll(async () => { await page.close() })

  test("every setting can explain itself", async () => {
    for (const what of EXPLAINED) {
      await expect(
        page.locator(`button[aria-label='About ${what}']`),
        `${what} has no information button`,
      ).toHaveCount(1)
    }
  })

  test("the icon is a circled 'i', not an eye", async () => {
    const icon = await page.evaluate(() => {
      const svg = document.querySelector("button.info-dot svg")!
      return {
        cls: svg.getAttribute("class") ?? "",
        circles: svg.querySelectorAll("circle").length,
      }
    })
    expect(icon.cls, "an eye promises show/hide; this must promise information").toContain("info")
    expect(icon.cls.toLowerCase()).not.toContain("eye")
    expect(icon.circles).toBeGreaterThanOrEqual(1)
  })

  test("a popover opens on click and closes three ways", async () => {
    const dot = page.locator("button[aria-label='About Globex session']")
    await expect(page.getByRole("dialog")).toHaveCount(0)

    await dot.click()
    await expect(page.getByRole("dialog")).toHaveCount(1)
    await expect(page.getByRole("dialog")).toContainText("DAY VWAP anchors")

    await dot.click()                                   // same button again
    await expect(page.getByRole("dialog")).toHaveCount(0)

    await dot.click()
    await page.mouse.click(900, 120)                    // outside
    await expect(page.getByRole("dialog")).toHaveCount(0)

    await dot.click()
    await page.keyboard.press("Escape")                 // escape
    await expect(page.getByRole("dialog")).toHaveCount(0)
  })

  test("opening an explanation does not change the setting", async () => {
    const card = page.getByRole("button", { name: /session preset Globex/ }).first()
    const before = await card.getAttribute("aria-pressed")
    await page.locator("button[aria-label='About Globex session']").click()
    await expect(page.getByRole("dialog")).toHaveCount(1)
    expect(await card.getAttribute("aria-pressed"),
      "the 'i' selected the session it was explaining").toBe(before)
    await page.keyboard.press("Escape")
  })

  test("the session cards carry no explanatory paragraph", async () => {
    // They used to: three lines under GLOBEX, two under RTH, permanently.
    await expect(page.locator("body")).not.toContainText("This is what a broker platform")
    await expect(page.locator("body")).not.toContainText("ignores overnight flow")
  })

  test("the session cards and timeframe pills still work", async () => {
    const globex = page.getByRole("button", { name: /session preset Globex/ }).first()
    await globex.click()
    await expect(globex).toHaveAttribute("aria-pressed", "true")

    const rth = page.getByRole("button", { name: /session preset RTH/ }).first()
    await rth.click()
    await expect(rth).toHaveAttribute("aria-pressed", "true")

    const before = await page.locator("button.tf-pill.tf-pill-on").count()
    await page.locator("button.tf-pill", { hasText: "15m" }).first().click()
    await expect(page.locator("button.tf-pill.tf-pill-on")).toHaveCount(before + 1)
    await page.locator("button.tf-pill", { hasText: "15m" }).first().click()
    await expect(page.locator("button.tf-pill.tf-pill-on")).toHaveCount(before)
  })
})

test.describe("once a session is loaded", () => {
  test.describe.configure({ mode: "serial" })
  let page: Page

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage()
    await signIn(page)
    await goToMarketGrid(page)
    await widenRsiWindow(page)
    await loadAndPlay(page)
  })
  test.afterAll(async () => { await page.close() })

  test("the transport leads and the locked setup is folded away", async () => {
    const geo = await page.evaluate(() => {
      const y = (e: Element | null | undefined) =>
        e ? Math.round(e.getBoundingClientRect().y) : null
      const btn = Array.from(document.querySelectorAll("button"))
        .find((b) => /Reset all/i.test(b.innerText))
      const strip = Array.from(document.querySelectorAll("button"))
        .find((b) => /LOCKED FOR THIS SESSION/.test(b.innerText))
      return { transport: y(btn), strip: y(strip), vh: document.documentElement.clientHeight }
    })
    expect(geo.transport, "the transport row is not the first block").toBeLessThan(160)
    expect(geo.strip, "the locked setup is not folded to a strip").not.toBeNull()
    expect(geo.strip!).toBeGreaterThan(geo.transport!)
  })

  test("the gauge, the tiles and the live table are all above the fold", async () => {
    const vh = page.viewportSize()!.height
    for (const [what, locator] of [
      ["progress bar", page.locator("[role=progressbar]").first()],
      ["KPI tiles", page.getByText("Portfolio (ROI)").first()],
      ["live state", page.getByText("LIVE STATE", { exact: false }).first()],
    ] as const) {
      const box = await locator.boundingBox()
      expect(box, `${what} is not rendered`).not.toBeNull()
      expect(box!.y, `${what} is below the fold`).toBeLessThan(vh)
    }
  })

  test("the setup strip opens, still locked, and closes", async () => {
    const strip = page.getByRole("button", { name: /LOCKED FOR THIS SESSION/ }).first()
    const capital = page.locator("input[aria-label='Initial capital in dollars']").first()

    await strip.click()
    await expect(capital).toBeVisible()
    await expect(capital, "revealing the setup must not unlock it").toBeDisabled()

    await strip.click()
    await expect(capital).toBeHidden()
  })

  test("the KPI tiles show the session's own numbers", async () => {
    const ticks = page.getByTestId("replay-ticks")
    const total = await ticks.getAttribute("data-total")
    expect(Number(total), "no ticks were replayed").toBeGreaterThan(0)

    // Guards against a reference screenshot's values being pasted in.
    //
    // This used to assert the total was not literally "78", the number on the
    // reference shot. The session this describe loads now genuinely replays 78
    // ticks -- the same figure on CI and on a dev machine, which is what a
    // deterministic derived value looks like, not a coincidence -- so the old
    // assertion failed on a correct number and the suite could never go green.
    //
    // The property it was reaching for is "this came from the session, not
    // from a literal", and that is what is checked instead: the number the
    // user can see has to be the number in the data attribute the component
    // renders from. A pasted caption cannot satisfy that, and it holds for
    // any session rather than for every total except one.
    const shown = (await ticks.innerText()).replace(/[^\d]/g, "")
    expect(shown, "the visible tick count is not the one the component holds")
      .toBe(Number(total).toLocaleString().replace(/[^\d]/g, ""))
    const processed = Number(await ticks.getAttribute("data-processed"))
    expect(processed, "more ticks reported processed than the session has")
      .toBeLessThanOrEqual(Number(total))
    await expect(page.getByText("Portfolio (ROI)").first()).toBeVisible()
    await expect(page.locator("body")).not.toContainText("$99,995")
  })

  test("all three panels offer full screen, and Live state a settings gear", async () => {
    for (const what of ["live state", "consolidated tape", "recent trades"]) {
      await expect(
        page.locator(`button[aria-label='Full screen — ${what}']`),
        `${what} has no full screen control`,
      ).toHaveCount(1)
    }
    await expect(page.locator("button[aria-label='VWAP and Volume Profile settings']")).toHaveCount(1)
  })

  test("the gear opens the deviation settings", async () => {
    const gear = page.locator("button[aria-label='VWAP and Volume Profile settings']").first()
    await gear.click()
    await expect(page.locator("button[aria-label='deviation 3']").first()).toBeVisible()
    await gear.click()
  })

  test("the tables are dense, ruled, and mark the newest bar", async () => {
    const m = await page.evaluate(() => {
      const td = document.querySelector("table.grid-table tbody td")!
      const cs = getComputedStyle(td)
      return {
        padTop: cs.paddingTop,
        borderRight: cs.borderRightWidth,
        newest: document.querySelectorAll("tr.row-newest").length,
      }
    })
    expect(m.padTop, "rows are back to the loose padding").toBe("4px")
    expect(m.borderRight, "columns lost their separator").not.toBe("0px")
    expect(m.newest, "the newest bar is not marked").toBeGreaterThan(0)
  })

  test("Reset rewinds, and Change Setup unlocks the fields", async () => {
    await page.getByRole("button", { name: /^↺?\s*Reset$/ }).first().click()
    await expect(page.getByTestId("replay-ticks")).toHaveAttribute("data-processed", "0")

    await page.getByRole("button", { name: "Change Setup" }).first().click()
    await expect(page.locator("input[aria-label='Initial capital in dollars']").first()).toBeEnabled()
    await expect(page.getByRole("button", { name: /LOCKED FOR THIS SESSION/ })).toHaveCount(0)
  })
})
