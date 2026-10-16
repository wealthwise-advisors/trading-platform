/**
 * Warm the test API once per run.
 *
 * There is no sign-in any more (removed 2026-10-16), so there is no test
 * account to register. Every request runs as the workspace account, which the
 * API creates on first use; asking for it here makes that happen once, before
 * the specs start, rather than inside whichever spec happens to run first.
 *
 * The database is a throwaway SQLite file recreated by start-api.mjs on every
 * run, so this always starts from empty.
 */

import { E2E_API_PORT } from "../playwright.config"

async function main() {
  const base = `http://localhost:${E2E_API_PORT}`
  const res = await fetch(`${base}/api/auth/me`)
  if (!res.ok) {
    throw new Error(`[e2e] the test API did not answer /api/auth/me: ${res.status} ${await res.text()}`)
  }
}

export default main
