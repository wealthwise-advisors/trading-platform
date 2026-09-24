/**
 * The three bugs this suite was written from.
 *
 * All three shipped. All three passed 518 unit tests, `tsc`, `oxlint` and a
 * clean production build on the way out, because none of those has a layout
 * engine. Each test below fails if its bug comes back.
 */

import { expect, test } from "@playwright/test"
import { goToMarketGrid, loadAndPlay, runBacktest, scrollHost, signIn } from "./helpers"

test.describe("regressions that reached production", () => {
  /**
   * BUG 1 — visually hidden text stretched the document.
   *
   * `.sr-only` is `position: absolute`, and an absolutely positioned box is
   * clipped by an ancestor's `overflow` only when that ancestor is its
   * containing block -- that is, only when the ancestor is itself positioned.
   * The four scroll containers were all `position: static`, so every hidden
   * label inside them escaped, was laid out at its static position far below
   * the fold, and dragged the document down to reach it.
   *
   * Measured at the time: scrollHeight 1092 against an 832px viewport. 260px
   * of scrolling that led to nothing but blank space, which is exactly what it
   * looked like on screen.
   *
   * The assertion is on the page, not on `position: relative`, so it keeps
   * holding if the fix is later done some other way.
   */
  test("the page does not scroll past its own content", async ({ page }) => {
    await signIn(page)
    await runBacktest(page)

    const host = await scrollHost(page)
    expect(host, "no scroll container found — the page shell changed").not.toBeNull()
    expect(
      host!.overflow,
      `the dashboard scrolls ${host!.overflow}px past its content. `
      + "Something absolutely positioned has escaped a scroll container — "
      + "check that every overflow:auto ancestor is also position:relative.",
    ).toBeLessThanOrEqual(2)

    // And nothing reaches below the fold that nothing can see.
    //
    // "That nothing can see" is the operative part. This used to flag ANY
    // element below the fold, which was true enough while nothing on the page
    // scrolled internally past it. The market rail does now -- four stacked
    // panels are taller than a short viewport by design, and the rail scrolls
    // them -- so the check has to tell "unreachable" from "further down a
    // scroll container", which are not the same thing.
    //
    // The discriminator is the container's own scrollHeight, NOT merely
    // having a scrolling ancestor: an escaped element is still a DOM
    // descendant of the container it escaped, so that weaker test would wave
    // BUG 1 straight through. A normal child was measured by its container,
    // so its offset inside the scrollable content falls within scrollHeight.
    // An absolutely positioned box whose ancestor is not its containing block
    // was never measured or clipped by it, lands beyond scrollHeight, and is
    // still reported.
    //
    // Both halves verified against a synthetic DOM before this was changed:
    // 80 rows in a 300px scroller are not flagged, and a position:absolute
    // child at top:4000px inside a position:static overflow:auto parent -- the
    // exact shape of BUG 1 -- still is.
    const stragglers = await page.evaluate(() => {
      const vh = document.documentElement.clientHeight
      const reachableByScrolling = (el: Element) => {
        const b = el.getBoundingClientRect()
        for (let p = el.parentElement; p; p = p.parentElement) {
          const oy = getComputedStyle(p).overflowY
          if (oy !== "auto" && oy !== "scroll") continue
          const pb = p.getBoundingClientRect()
          return b.top - pb.top + p.scrollTop <= p.scrollHeight + 2
        }
        return false
      }
      return Array.from(document.querySelectorAll("body *"))
        .filter((el) => {
          const b = el.getBoundingClientRect()
          return b.height > 0 && b.top > vh + 200 && !reachableByScrolling(el)
        })
        .map((el) => `${el.tagName}.${String(el.className).slice(0, 40)}`)
        .slice(0, 5)
    })
    expect(stragglers, "elements laid out far below the fold").toEqual([])
  })

  /**
   * BUG 2 — a scroll container that did not scroll.
   *
   * Observed on the dev server: `overflow-auto` in the class list, computed
   * `overflowY: visible`. The failure is silent -- the rows simply run past
   * the bottom of the panel and the header stops being sticky, with nothing in
   * the console.
   *
   * IT DOES NOT REPRODUCE against a production build. Putting the original
   * code back and running this test passes, because
   * `.overflow-auto{overflow:auto}` is generated and applies. So this is not
   * the cascade bug it was first written up as -- most likely the dev-mode
   * class scanner had not picked the class up yet. Kept anyway: "the table
   * scrolls and its header sticks" is a property worth holding on every run,
   * whatever once broke it.
   */
  test("the Market Grid tables really scroll, and their headers stay put", async ({ page }) => {
    await signIn(page)
    await goToMarketGrid(page)
    await loadAndPlay(page)

    const panels = await page.evaluate(() =>
      Array.from(document.querySelectorAll("table.grid-table")).map((t) => {
        const host = t.parentElement!
        const cs = getComputedStyle(host)
        const th = t.querySelector("thead th")
        return {
          overflowY: cs.overflowY,
          headerPosition: th ? getComputedStyle(th).position : null,
        }
      }),
    )
    expect(panels.length, "no grid tables rendered").toBeGreaterThan(0)
    for (const p of panels) {
      expect(
        p.overflowY,
        "a table's container is not scrollable, so its rows run off the "
        + "bottom of the panel and the sticky header has nothing to stick to.",
      ).toMatch(/auto|scroll/)
      expect(p.headerPosition, "the column header is not sticky").toBe("sticky")
    }
  })

  /**
   * BUG 3 — `display: flex` beat the class that was supposed to hide it.
   *
   * Folding the consolidated tape hid its rows and left its jump toolbar on
   * screen: `.tape-bar { display: flex }` is emitted after Tailwind's
   * utilities, so at equal specificity it beats `.hidden`.
   *
   * REPRODUCED AND CAUGHT, but only in its original form. Restoring just the
   * missing CSS rule is not enough, because the fix also swapped the Tailwind
   * class for the `hidden` ATTRIBUTE -- and Chrome's UA stylesheet hides that
   * with `display: none !important`, which no ordinary author rule can lose
   * to. That is worth knowing on its own: the attribute is robust against this
   * whole class of mistake and the utility class is not.
   */
  test("folding a panel hides all of it, toolbar included", async ({ page }) => {
    await signIn(page)
    await goToMarketGrid(page)
    await loadAndPlay(page)

    const jumpToDate = page.getByText("Jump to date", { exact: false }).first()
    await expect(jumpToDate).toBeVisible()

    await page.getByRole("button", { name: /^Hide Consolidated tape/ }).click()
    await expect(
      jumpToDate,
      "the tape folded but its toolbar stayed. A component rule setting "
      + "`display` is beating whatever hides it — note that the hidden "
      + "ATTRIBUTE survives this (the UA rule is `display:none !important`) "
      + "while Tailwind's `.hidden` class does not.",
    ).toBeHidden()

    await page.getByRole("button", { name: /^Show Consolidated tape/ }).click()
    await expect(jumpToDate).toBeVisible()
  })
})
