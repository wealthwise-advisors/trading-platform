/**
 * Create the account every spec signs in as, once per run.
 *
 * Through the real registration endpoint rather than by writing rows: that way
 * the suite's own fixture is proof the sign-up path still works, and it cannot
 * drift from whatever the schema becomes. The database is thrown away and
 * recreated by start-api.mjs on every run, so this always registers into an
 * empty one.
 *
 * The credentials below are a LOCAL TEST FIXTURE against a throwaway SQLite
 * file on a port that is not exposed. They are not a secret, they unlock
 * nothing, and no real credential should ever be put here -- see the note in
 * e2e/README.md.
 */

import { E2E_API_PORT } from "../playwright.config"

export const E2E_USER = "e2e.check"
export const E2E_PASSWORD = "Correct-Horse-99-Battery"

async function main() {
  const base = `http://localhost:${E2E_API_PORT}`
  const body = {
    username: E2E_USER,
    password: E2E_PASSWORD,
    email: "e2e.check@example.invalid",
    full_name: "E2E Check",
    country: "IN",
    accept_terms: true,
  }

  const res = await fetch(`${base}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Origin: base },
    body: JSON.stringify(body),
  })

  // 409 means a previous run on a reused server already made it, which is fine
  // and is the normal path when reuseExistingServer is on locally.
  if (!res.ok && res.status !== 409) {
    throw new Error(
      `[e2e] could not create the test account: ${res.status} ${await res.text()}`,
    )
  }
}

export default main
