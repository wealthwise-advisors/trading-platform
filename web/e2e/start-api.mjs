/**
 * Start the API for an end-to-end run, on its own throwaway database.
 *
 * A wrapper rather than a command string in playwright.config.ts because of
 * the database. The API defaults to data/autotrader.db -- the developer's real
 * dev database, with their account and their saved configurations in it. A
 * test run must not read it and must certainly not write to it, so this points
 * AUTOTRADER_DB_PATH at a scratch file that is deleted and recreated on every
 * run. A suite whose results depend on what happens to be in your dev database
 * is a suite that passes on your machine.
 *
 * AUTOTRADER_INSECURE_COOKIE is set because the session cookie is Secure by
 * default and the suite runs over plain http on localhost; without it the
 * browser accepts the sign-in response and then sends no cookie, and every
 * test fails at the first authenticated request.
 */

import { spawn } from "node:child_process"
import { existsSync, mkdirSync, rmSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, "..", "..")
const tmpDir = resolve(here, ".tmp")
const dbPath = resolve(tmpDir, "e2e.db")
const port = process.env.E2E_API_PORT ?? "8188"

// A fresh database every run: no leftover users, no leftover backtests, and
// no test that only passes because a previous run left something behind.
rmSync(tmpDir, { recursive: true, force: true })
mkdirSync(tmpDir, { recursive: true })

// Windows ships `py`; CI and most POSIX boxes have `python3` or `python`.
const candidates = process.platform === "win32"
  ? [["py", ["-3.12", "-m", "uvicorn"]], ["python", ["-m", "uvicorn"]]]
  : [["python3", ["-m", "uvicorn"]], ["python", ["-m", "uvicorn"]]]

const [cmd, baseArgs] = candidates.find(([c]) => {
  try {
    // `which`/`where` rather than running it: starting a Python just to see if
    // it exists is slow and noisy in the log.
    const probe = process.platform === "win32" ? "where" : "which"
    const r = spawn(probe, [c])
    return r != null
  } catch {
    return false
  }
}) ?? candidates[0]

if (!existsSync(resolve(repoRoot, "api", "main.py"))) {
  console.error(`[e2e] cannot find api/main.py under ${repoRoot}`)
  process.exit(1)
}

const child = spawn(
  cmd,
  [...baseArgs, "api.main:app", "--port", String(port), "--log-level", "warning"],
  {
    cwd: repoRoot,
    stdio: "inherit",
    env: {
      ...process.env,
      AUTOTRADER_DB_PATH: dbPath,
      AUTOTRADER_CONFIG_DIR: resolve(tmpDir, "config"),
      AUTOTRADER_INSECURE_COOKIE: "1",
      AUTOTRADER_DEV_MAIL_SINK: "1",
    },
  },
)

child.on("exit", (code) => process.exit(code ?? 0))
for (const sig of ["SIGINT", "SIGTERM"]) {
  process.on(sig, () => { child.kill(sig); process.exit(0) })
}
