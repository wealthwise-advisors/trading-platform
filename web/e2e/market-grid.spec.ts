/**
 * Market Grid: the circled "i" explanations, the setup disclosure, and the
 * panel chrome.
 *
 * Split into two describes because they need different states -- one before a
 * session is loaded, one after -- and loading takes long enough that it is
 * worth doing once rather than per test.
 */

import { expect, test, type Page } from "@playwright/test"
import { goToMarketGrid, loadAndPlay, openApp, widenRsiWindow } from "./helpers"

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
    await openApp(page)
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
    await openApp(page)
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

  /**
   * The timeframe pills live on Live state, and ONLY there.
   *
   * They used to sit in the Consolidated tape's jump bar, which is the wrong
   * place twice over: the tape has a row per BAR, while Live state has a row
   * per TIMEFRAME, and offering the control in both read as two filters that
   * mysteriously moved together. It is one selection.
   */
  test("the timeframe pills sit on Live state, not in the tape", async () => {
    await expect(
      page.locator("button[aria-label^='jump timeframe']"),
      "the tape kept a second copy of the timeframe pills",
    ).toHaveCount(0)
    await expect(page.locator("button[aria-label^='live timeframe']").first()).toBeVisible()

    // Live state is the first panel, so its bar is the first .tape-bar; the
    // tape's own bar keeps Jump and loses the pills.
    const bars = page.locator("div.tape-bar")
    await expect(bars.first().locator("button.tape-pill").first()).toBeVisible()
    await expect(
      bars.nth(1).locator("button.tape-pill"),
      "pills are still rendering inside the tape's jump bar",
    ).toHaveCount(0)
    // exact: the time field's steppers are labelled "Jump time hour up" and
    // friends, so a loose name matches six buttons.
    await expect(bars.nth(1).getByRole("button", { name: "Jump", exact: true })).toBeVisible()
  })

  test("Reset rewinds, and Change Setup unlocks the fields", async () => {
    await page.getByRole("button", { name: /^↺?\s*Reset$/ }).first().click()
    await expect(page.getByTestId("replay-ticks")).toHaveAttribute("data-processed", "0")

    await page.getByRole("button", { name: "Change Setup" }).first().click()
    await expect(page.locator("input[aria-label='Initial capital in dollars']").first()).toBeEnabled()
    await expect(page.getByRole("button", { name: /LOCKED FOR THIS SESSION/ })).toHaveCount(0)
  })
})

/**
 * POC Match and POC vs Avg, as sir specified them on 2026-10-11.
 *
 * Asserted against the RULE rather than against fixed numbers, so it holds
 * whatever POCs the shipped session produces: every row's colour is checked
 * against its own POC, the average printed in the header, and the other rows.
 * Its own page because it needs several timeframes switched on.
 */
test("POC Match groups by whole number, POC vs Avg is green above / red below", async ({ browser }) => {
  test.setTimeout(360_000)
  const page = await browser.newPage()
  await openApp(page)
  await goToMarketGrid(page)
  await widenRsiWindow(page)
  for (const tf of ["10m", "15m", "20m", "30m"]) {
    const pill = page.locator("button.tf-pill", { hasText: new RegExp(`^${tf}$`) }).first()
    if (await pill.count() && !((await pill.getAttribute("class")) ?? "").includes("tf-pill-on")) await pill.click()
  }
  await loadAndPlay(page)

  const table = page.locator("table.grid-table").first()
  const headers = (await table.locator("thead th").allInnerTexts()).map((h) => h.trim())
  const iPoc = headers.findIndex((h) => /^POC$/i.test(h))
  const iMatch = headers.findIndex((h) => /^POC MATCH/i.test(h))
  const iAvg = headers.findIndex((h) => /^POC VS AVG/i.test(h))
  expect(iMatch, `no POC Match column in ${JSON.stringify(headers)}`).toBeGreaterThan(-1)
  expect(iAvg, "no POC vs Avg column").toBeGreaterThan(-1)
  const average = Number(/\(([\d.]+)\)/.exec(headers[iAvg])?.[1])
  expect(Number.isFinite(average), `no average in the header: ${headers[iAvg]}`).toBe(true)

  const rows = await table.locator("tbody tr").evaluateAll((trs, [a, b, c]) => trs.map((tr) => {
    const td = tr.querySelectorAll("td")
    return {
      poc: Number((td[a] as HTMLElement).innerText.trim()),
      matchColor: getComputedStyle(td[b]).color,
      matchText: (td[b] as HTMLElement).innerText.trim(),
      avgColor: getComputedStyle(td[c]).color,
    }
  }), [iPoc, iMatch, iAvg])
  const live = rows.filter((r) => Number.isFinite(r.poc))
  expect(live.length).toBeGreaterThan(1)

  // The header's average IS the mean of the POCs on screen.
  const mean = live.reduce((s, r) => s + r.poc, 0) / live.length
  expect(average).toBeCloseTo(mean, 1)

  // Green above, red below -- read the theme's own tokens rather than
  // hard-coding a shade.
  const [green, red] = await page.evaluate(() => {
    const probe = document.createElement("span")
    document.body.appendChild(probe)
    probe.style.color = "var(--gain)"; const g = getComputedStyle(probe).color
    probe.style.color = "var(--loss)"; const r = getComputedStyle(probe).color
    probe.remove()
    return [g, r]
  })
  for (const r of live) {
    if (r.poc > mean + 1e-6) expect(r.avgColor, `${r.poc} is above ${mean} but not green`).toBe(green)
    if (r.poc < mean - 1e-6) expect(r.avgColor, `${r.poc} is below ${mean} but not red`).toBe(red)
  }

  // Same whole number <-> same symbol AND colour; different numbers differ in
  // at least one of them (colour alone repeats after six -- the symbol is the
  // cue for a reader who cannot tell the colours apart). The cell shows the
  // symbol and the level and nothing else -- a "6/7" count was removed.
  const cue = (r: { matchText: string; matchColor: string }) => `${r.matchText.split(/\d/)[0]}|${r.matchColor}`
  for (const a of live) {
    expect(a.matchText).toMatch(/^\S\s*\d+$/)
    expect(a.matchText.replace(/^\S\s*/, "")).toBe(`${Math.trunc(a.poc)}`)
    for (const b of live) {
      if (Math.trunc(a.poc) === Math.trunc(b.poc)) expect(cue(b)).toBe(cue(a))
      else expect(cue(b)).not.toBe(cue(a))
    }
  }
  await page.close()
})

/**
 * The same two POC columns on the Consolidated tape -- the PAST of the Live
 * state table. Requested 2026-10-26.
 *
 * Every tape row is measured against ONE common average -- the one the Live
 * state table prints in its header, printed in the tape's header too
 * (specified 2026-10-26). Asserted by invariant, not by fixed numbers:
 *   - both headers carry the same average, and every row's POC minus its
 *     printed difference equals it;
 *   - ▲ is always green and ▼ always red;
 *   - a level is the same colour on the tape as in the Live state table.
 */
test("the Consolidated tape carries POC Match and POC vs Avg, against the Live table's common average", async ({ browser }) => {
  test.setTimeout(360_000)
  const page = await browser.newPage()
  await openApp(page)
  await goToMarketGrid(page)
  await widenRsiWindow(page)
  for (const tf of ["10m", "15m", "20m", "30m"]) {
    const pill = page.locator("button.tf-pill", { hasText: new RegExp(`^${tf}$`) }).first()
    if (await pill.count() && !((await pill.getAttribute("class")) ?? "").includes("tf-pill-on")) await pill.click()
  }
  await loadAndPlay(page)

  const readTable = async (idx: number) => {
    const table = page.locator("table.grid-table").nth(idx)
    const headers = (await table.locator("thead th").allInnerTexts()).map((h) => h.trim())
    const ix = (re: RegExp) => headers.findIndex((h) => re.test(h))
    const cols = { close: 0, poc: ix(/^POC$/i), match: ix(/^POC MATCH/i), avg: ix(/^POC VS AVG/i) }
    expect(cols.match, `no POC Match column in ${JSON.stringify(headers)}`).toBeGreaterThan(-1)
    expect(cols.avg, "no POC vs Avg column").toBeGreaterThan(-1)
    const average = Number(/\(([\d.]+)\)/.exec(headers[cols.avg])?.[1])
    const rows = await table.locator("tbody tr").evaluateAll((trs, c) => trs.map((tr) => {
      const td = tr.querySelectorAll("td")
      const cell = (i: number) => td[i] as HTMLElement
      return {
        close: cell(c.close).innerText.split("\n")[0].trim(),
        poc: Number(cell(c.poc).innerText.trim()),
        matchText: cell(c.match).innerText.trim(),
        matchColor: getComputedStyle(cell(c.match)).color,
        avgText: cell(c.avg).innerText.trim(),
        avgColor: getComputedStyle(cell(c.avg)).color,
      }
    }), cols)
    return { average, rows }
  }
  const { average: liveAvg, rows: live } = await readTable(0)
  const { average: tapeAvg, rows: tapeRows } = await readTable(1)
  expect(Number.isFinite(liveAvg), "no average in the Live header").toBe(true)
  expect(tapeAvg, "the tape header must print the Live table's common average").toBe(liveAvg)
  const tape = tapeRows.filter((r) => Number.isFinite(r.poc) && /[▲▼=]/.test(r.avgText))
  expect(tape.length, "no tape rows carry the POC columns").toBeGreaterThan(5)

  const [green, red] = await page.evaluate(() => {
    const p = document.createElement("span"); document.body.appendChild(p)
    p.style.color = "var(--gain)"; const g = getComputedStyle(p).color
    p.style.color = "var(--loss)"; const r = getComputedStyle(p).color
    p.remove(); return [g, r]
  })

  const liveColor = new Map(live.filter((r) => Number.isFinite(r.poc))
    .map((r) => [Math.trunc(r.poc), `${r.matchText.split(/\d/)[0]}|${r.matchColor}`]))
  for (const r of tape) {
    // Match: the level, with the same symbol and colour the Live table gives it.
    expect(r.matchText).toMatch(/^\S\s*\d+$/)
    expect(r.matchText.replace(/^\S\s*/, "")).toBe(`${Math.trunc(r.poc)}`)
    const lc = liveColor.get(Math.trunc(r.poc))
    if (lc) expect(`${r.matchText.split(/\d/)[0]}|${r.matchColor}`, `level ${Math.trunc(r.poc)} differs between tables`).toBe(lc)

    // vs Avg: arrow and colour agree.
    if (r.avgText.startsWith("▲")) expect(r.avgColor).toBe(green)
    if (r.avgText.startsWith("▼")) expect(r.avgColor).toBe(red)

    // The cell prints only the difference, measured from the common average.
    const m = /^[▲▼=]\s*([+-]?[\d.]+)$/.exec(r.avgText)
    expect(m, `POC vs Avg cell is not a signed difference: ${r.avgText}`).not.toBeNull()
    const diff = Number(m![1])
    expect(Math.abs(r.poc - diff - liveAvg), `${r.avgText} does not add up for POC ${r.poc}`).toBeLessThan(0.02)
  }
  await page.close()
})
