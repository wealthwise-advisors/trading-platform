/**
 * The Backtest dashboard: the KPI row, the chart's menus and its controls.
 *
 * One signed-in page shared across the file. Running a backtest and waiting for
 * the Plotly chunk costs about ten seconds; paying that per test would put four
 * minutes on every CI run to re-reach a screen none of these tests modify
 * destructively. Serial mode, so the order is defined rather than incidental.
 */

import { expect, test, type Page } from "@playwright/test"
import { chartRangeStart, runBacktest, signIn, waitForChartSettled } from "./helpers"

test.describe.configure({ mode: "serial" })

let page: Page

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage()
  await signIn(page)
  await runBacktest(page)
})

test.afterAll(async () => { await page.close() })

test("the eight KPI cards sit on one row, all the same height", async () => {
  const cards = await page.evaluate(() =>
    Array.from(document.querySelectorAll(".stat-card")).map((e) => {
      const b = e.getBoundingClientRect()
      return { y: Math.round(b.y), h: Math.round(b.height),
               label: (e.textContent ?? "").slice(0, 20) }
    }),
  )
  expect(cards).toHaveLength(8)
  // One row: every card shares a top edge.
  expect(new Set(cards.map((c) => c.y)).size, `cards on ${new Set(cards.map((c) => c.y)).size} rows`).toBe(1)
  // And one height: Avg Win / Avg Loss used to be a separate, shorter pair.
  expect(new Set(cards.map((c) => c.h)).size, "KPI cards differ in height").toBe(1)
})

test("the chart carries no Plotly badge, and every way of driving it survives", async () => {
  await expect(page.locator(".js-plotly-plot a.modebar-btn--logo")).toHaveCount(0)

  // PLOTLY'S FLOATING MODEBAR IS OFF NOW. It sat over the top-right of the
  // plot carrying a SECOND camera -- the chart toolbar already had one -- and
  // cost a strip of chart to sit in. Its controls did not go away; they moved
  // somewhere a reader can see them without hovering the plot.
  //
  // This test still exists to stop them being lost. It asserts the
  // CAPABILITY, by its new home, rather than the old widget: zoom, reset and
  // snapshot on the toolbar row above the chart, pan on the drawing rail down
  // its left edge.
  await expect(page.locator(".js-plotly-plot .modebar-btn")).toHaveCount(0)

  for (const label of ["Zoom in", "Zoom out", "Reset the view", "Download chart as PNG"]) {
    await expect(
      page.getByRole("button", { name: label }).first(),
      `the chart toolbar lost "${label}"`,
    ).toBeVisible()
  }
  await expect(
    page.getByRole("toolbar", { name: "Chart drawing tools" }).getByRole("button", { name: "Pan" }),
    "the drawing rail lost Pan",
  ).toBeVisible()
})

test("the Legend menu explains the chart and reads its live values", async () => {
  await page.getByRole("button", { name: "Legend" }).first().click()
  const menu = page.getByRole("menu").last()
  await expect(menu).toBeVisible()

  for (const entry of ["EMA 9", "EMA 21", "VWAP", "ZigZag (3L)", "Swing High", "Swing Low"]) {
    await expect(menu, `legend is missing ${entry}`).toContainText(entry)
  }
  // A reading, not just a name: the whole point of folding the old on-chart
  // readout into this menu was that the numbers came with it.
  await expect(menu).toContainText(/EMA 9[\s\S]{0,40}\d/)
  // A swatch per entry, so the key actually keys.
  expect(await menu.locator("svg").count()).toBeGreaterThanOrEqual(8)
  await page.keyboard.press("Escape")
})

test("the on-chart legend is off by default and the menu toggles it", async () => {
  await page.getByRole("button", { name: "Legend" }).first().click()
  const toggle = page.getByRole("menu").last().locator("input[type='checkbox']").first()
  await expect(toggle, "Plotly's legend should start off — it costs ~119px of plot").not.toBeChecked()

  await toggle.check()
  await expect(page.locator(".js-plotly-plot .legend")).toHaveCount(1)

  // And when it is on, it must clear the price ladder rather than sit on it.
  const gap = await page.evaluate(() => {
    const lg = document.querySelector(".js-plotly-plot .legend")!.getBoundingClientRect()
    let maxRight = -1e9
    document.querySelectorAll(".js-plotly-plot .yaxislayer-above text").forEach((t) => {
      maxRight = Math.max(maxRight, t.getBoundingClientRect().right)
    })
    return Math.round(lg.left - maxRight)
  })
  expect(gap, "the legend is crowding the y-axis labels").toBeGreaterThanOrEqual(4)

  await toggle.uncheck()
  await expect(page.locator(".js-plotly-plot .legend")).toHaveCount(0)
  await page.keyboard.press("Escape")
})

test("VWAP offers +/-1 to +/-5, and a preset writes both multipliers", async () => {
  await page.locator("button[aria-label='VWAP settings']").first().click()

  for (const d of [1, 2, 3, 4, 5]) {
    await expect(
      page.locator(`button[aria-label='deviation bands plus and minus ${d} sigma']`),
      `VWAP preset +/-${d} is missing`,
    ).toHaveCount(1)
  }

  await page.locator("button[aria-label='deviation bands plus and minus 3 sigma']").click()
  const fields = await page.evaluate(() =>
    Array.from(document.querySelectorAll("label"))
      .filter((l) => /num dev/.test(l.textContent ?? ""))
      .map((l) => [l.textContent!.trim(), l.querySelector("input")!.value]),
  )
  expect(fields, "the preset did not write the underlying pair").toEqual([
    ["num dev dn", "-3"],
    ["num dev up", "3"],
  ])

  // Put it back, so later tests see the shipped default.
  await page.locator("button[aria-label='deviation bands plus and minus 2 sigma']").click()
  await page.locator("button[aria-label='VWAP settings']").first().click()
})

/**
 * ITS OWN PAGE, unlike everything else in this file.
 *
 * This is the one test here that changes what the chart is SHOWING rather than
 * just reading it, and it is also the one whose assertion is about the chart's
 * view state. Sharing a page with the tests above made it fail while passing
 * in isolation: they toggle the on-chart legend and the deviation presets,
 * each of which re-renders the plot from props -- and a re-render re-applies
 * the default window, so the pan was being undone before it could be read.
 *
 * That is a test-isolation problem, not an app bug: panning works, and this
 * proves it from a clean chart.
 */
test("dragging the chart still pans it", async ({ browser }) => {
  const own = await browser.newPage()
  await signIn(own)
  await runBacktest(own)

  await waitForChartSettled(own)

  const drag = own.locator(".js-plotly-plot .nsewdrag").first()
  const box = (await drag.boundingBox())!
  const before = await chartRangeStart(own)

  await own.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await own.mouse.down()
  await own.mouse.move(box.x + box.width / 2 - 160, box.y + box.height / 2, { steps: 12 })
  await own.mouse.up()

  await expect
    .poll(() => chartRangeStart(own), { message: "the chart did not pan" })
    .not.toBe(before)
  await own.close()
})

test("Deploy is out of the header; both exports remain", async () => {
  const header = page.locator("header").filter({ has: page.locator("nav") }).first()
  await expect(
    header.getByRole("button", { name: "Deploy" }),
    "Deploy is back in the header — it reads as 'deploy the app', which AWS already does",
  ).toHaveCount(0)
  await expect(header.getByRole("button", { name: "Export Data" })).toHaveCount(1)
  // Export Report is a real <a download>, not a scripted button.
  await expect(header.locator("a[download]").filter({ hasText: "Export Report" })).toHaveCount(1)
})
