/**
 * End-to-end tests, against a BUILT app.
 *
 * WHY THESE EXIST ALONGSIDE 518 UNIT TESTS. The unit suite runs in jsdom, which
 * has no layout engine: it cannot tell you that an element is 260px below the
 * fold, that a scroll container does not scroll, or that one stylesheet's rules
 * beat another's. Every bug this suite was written from was invisible to it:
 *
 *   1. `.sr-only` is position:absolute, so inside an UNPOSITIONED scroll
 *      container it escaped and stretched the document -- 260px of page scroll
 *      leading to nothing but blank space.
 *   2. a panel's scroll container reported `overflowY: visible` while
 *      `overflow-auto` sat in its class list. A scroll container that does not
 *      scroll fails silently -- the rows just run past the bottom of the panel.
 *   3. `.tape-bar { display: flex }` beat Tailwind's `.hidden` -- this
 *      stylesheet is emitted after Tailwind's utilities, so at equal
 *      specificity it wins -- and folding a panel left its toolbar on screen.
 *
 * ON (2), AN HONEST CORRECTION. That was first written up as the same
 * layer-ordering problem as (3). It is not: reintroducing it against a
 * production build does NOT reproduce, because `.overflow-auto{overflow:auto}`
 * is generated and applies correctly. The symptom was real but was only ever
 * observed on the dev server, so the likeliest cause is the dev-mode class
 * scanner not having picked the class up at that moment. The test below stays
 * because "this container scrolls and its header sticks" is worth asserting on
 * its own; it is just not a regression test for a cascade bug.
 *
 * BUILT, not dev-served, deliberately. (3) is a cascade-ordering bug, and the
 * built CSS is the only place the real ordering exists.
 *
 * NO LIVE DATA. Everything runs on the app's own synthetic source, which
 * generates bars server-side with no credentials. Nothing here needs a Schwab
 * token, and nothing here should ever be given one.
 */

import { defineConfig, devices } from "@playwright/test"

/** Ports chosen away from the usual dev ones so a running `npm run dev`
 *  (5173/8000) is never disturbed by a test run. */
export const E2E_WEB_PORT = 4188
export const E2E_API_PORT = 8188
export const BASE_URL = `http://localhost:${E2E_WEB_PORT}`

export default defineConfig({
  testDir: "./e2e",
  // Serial. These drive one API holding one replay session; two workers would
  // be two browsers fighting over the same server-side state, and the failures
  // would read as flakiness rather than as the contention they are.
  workers: 1,
  fullyParallel: false,
  // One retry: enough to absorb a genuinely transient hiccup, few enough that
  // a real intermittent bug still shows up as a retry in the report rather
  // than being buried.
  retries: 1,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI
    ? [["list"], ["html", { open: "never" }]]
    : [["list"]],
  use: {
    baseURL: BASE_URL,
    // Kept only for failures. A trace per passing test is hundreds of
    // megabytes of artifact nobody opens.
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    // The reference viewport these were all measured at.
    viewport: { width: 1536, height: 900 },
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  globalSetup: "./e2e/global-setup.ts",
  webServer: [
    {
      // A throwaway API with its own database file, so a run can never read or
      // write the developer's own dev.db.
      command: "node e2e/start-api.mjs",
      port: E2E_API_PORT,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      command: `npm run build && npx vite preview --port ${E2E_WEB_PORT} --strictPort`,
      port: E2E_WEB_PORT,
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
      env: { E2E_API_TARGET: `http://localhost:${E2E_API_PORT}` },
      stdout: "pipe",
      stderr: "pipe",
    },
  ],
})
