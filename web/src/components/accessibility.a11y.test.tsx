// @vitest-environment jsdom
//
// Per-file rather than via the config's environmentMatchGlobs, which this
// vitest version ignores -- the suite ran under the node environment and every
// render failed with "document is not defined". A docblock is read by the
// runner directly and cannot drift from the file it applies to.
/**
 * Accessibility, MEASURED rather than asserted.
 *
 * The audit that prompted this counted aria- attributes and called the result
 * "partial", which was the honest verdict available at the time: a count of
 * attributes says nothing about whether a control has an accessible name, a
 * label points at a field that exists, or a colour pair is readable. axe-core
 * checks the rendered DOM against the actual WCAG rules, so this file is
 * evidence instead of an inference.
 *
 * SCOPE, AND WHAT IT DOES NOT COVER
 * ---------------------------------
 * These are the account-lifecycle screens added by the readiness work, which
 * are plain forms and text and therefore genuinely testable in jsdom. The
 * dashboard is not here: it is four Plotly canvases, and Plotly does not render
 * in jsdom. Charts remain unverified by machine and are recorded as such -- see
 * docs/BETA_TESTING.md's known issues.
 *
 * jsdom also cannot compute colour contrast (no layout, no painted pixels), so
 * the colour-contrast rule is disabled here rather than silently passing. That
 * one needs a real browser.
 */
import { describe, expect, it, afterEach } from "vitest"
import { cleanup, render } from "@testing-library/react"
import axe from "axe-core"

import { ErrorBoundary } from "./ErrorBoundary"
import { VerifyEmailNotice } from "./VerifyEmailNotice"
import { Onboarding } from "./Onboarding"
import { OfflineBanner } from "./OfflineBanner"
import type { Me } from "@/lib/api"

afterEach(cleanup)

const USER: Me = {
  username: "trader",
  full_name: "A Trader",
  email: "trader@example.com",
  country: "IN",
  email_verified: false,
  verification_required: true,
  onboarded: false,
}

/** Rules jsdom genuinely cannot decide, disabled rather than faked. */
const UNDECIDABLE_IN_JSDOM = {
  // Needs painted pixels and a layout engine.
  "color-contrast": { enabled: false },
  // Both are page-level rules; these are fragments mounted into a bare div.
  "page-has-heading-one": { enabled: false },
  "landmark-one-main": { enabled: false },
  region: { enabled: false },
}

async function violationsIn(container: HTMLElement) {
  const results = await axe.run(container, {
    rules: UNDECIDABLE_IN_JSDOM,
    resultTypes: ["violations"],
  })
  return results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length})`)
}

describe("accessibility (axe-core)", () => {
  it("the error boundary's recovery screen has no violations", async () => {
    // A component that throws on first render, so the boundary shows its
    // fallback -- which is the state worth auditing. Nobody reads the happy
    // path of an error screen.
    function Explodes(): never {
      throw new Error("boom")
    }
    const { container } = render(
      <ErrorBoundary>
        <Explodes />
      </ErrorBoundary>,
    )
    expect(await violationsIn(container)).toEqual([])
  })

  it("the confirm-your-address screen has no violations", async () => {
    const { container } = render(<VerifyEmailNotice user={USER} />)
    expect(await violationsIn(container)).toEqual([])
  })

  it("the onboarding screen has no violations", async () => {
    const { container } = render(<Onboarding user={USER} onDone={() => {}} />)
    expect(await violationsIn(container)).toEqual([])
  })

  it("the offline banner has no violations", async () => {
    // navigator.onLine is read once on mount, so force the offline branch --
    // the online branch renders nothing and would audit an empty div.
    Object.defineProperty(window.navigator, "onLine", {
      configurable: true, value: false,
    })
    const { container } = render(<OfflineBanner />)
    expect(await violationsIn(container)).toEqual([])
  })
})

describe("keyboard and screen-reader affordances", () => {
  it("every control on the verify screen has an accessible name", () => {
    const { container } = render(<VerifyEmailNotice user={USER} />)
    // A button whose only content is an icon reads as "button" and nothing
    // else. axe catches the empty case; this catches the whitespace one.
    for (const el of container.querySelectorAll("button")) {
      const name = el.getAttribute("aria-label") ?? el.textContent ?? ""
      expect(name.trim().length).toBeGreaterThan(0)
    }
  })

  it("the offline banner announces itself politely", () => {
    Object.defineProperty(window.navigator, "onLine", {
      configurable: true, value: false,
    })
    const { container } = render(<OfflineBanner />)
    const status = container.querySelector('[role="status"]')
    // Losing the network must be ANNOUNCED, not merely drawn -- a sighted user
    // sees the strip appear, and without a live region nobody else does.
    expect(status).not.toBeNull()
    expect(status?.getAttribute("aria-live")).toBe("polite")
  })

  it("the error screen is announced as an alert", () => {
    function Explodes(): never {
      throw new Error("boom")
    }
    const { container } = render(
      <ErrorBoundary>
        <Explodes />
      </ErrorBoundary>,
    )
    expect(container.querySelector('[role="alert"]')).not.toBeNull()
  })

  it("the error screen never puts a stack trace on the page", () => {
    function Explodes(): never {
      const e = new Error("boom")
      e.stack = "Error: boom\n    at /srv/app/secret/path.tsx:12:3"
      throw e
    }
    const { container } = render(
      <ErrorBoundary>
        <Explodes />
      </ErrorBoundary>,
    )
    // Not an aesthetic rule: a stack names internal paths to whoever is
    // looking at the screen, and is not something a user can act on.
    expect(container.textContent).not.toContain("/srv/app/secret/path.tsx")
    expect(container.textContent).toContain("boom")
  })
})
