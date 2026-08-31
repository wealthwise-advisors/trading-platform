# Beta Testing

**No beta test has been run yet.** This document describes the process; it is
not a record that anything has happened. Nothing here should be read as
evidence that the flows below have been exercised by real people. Fill in
"Results" at the bottom when they have.

---

## 1. Test accounts

Six accounts, because six different things break. Create them with
[`scripts/manage_users.py`](../scripts/manage_users.py) on the host.

| Account | Convention | Created by | Exercises |
|---|---|---|---|
| `beta.normal` | verified, has run backtests | `add` then `verify` | The ordinary path |
| `beta.new` | verified, zero data | `add` then `verify` | Every empty state, onboarding |
| `beta.unverified` | real address, never confirmed | `add` only | The confirmation gate |
| `beta.verified` | confirmed by clicking a real link | `add`, then the emailed link | That the link itself works |
| `beta.oauth` | created by signing in with Google | the sign-in page | `has_password = 0`, closing without a password |
| `beta.edge` | no email, long name, unicode | `add --name "Ünïcödé Nâme"` | Address-less accounts, layout under long strings |

```bash
py -3.12 scripts/manage_users.py add beta.new --email you+beta.new@yourdomain
py -3.12 scripts/manage_users.py verify beta.new
py -3.12 scripts/manage_users.py list
```

**Rules that are not negotiable:**

- **No credentials in this repository, ever** — not here, not in a fixture, not
  in a comment. Passwords are prompted for, twice, with no echo, and go in
  whatever the team already uses for shared secrets.
- **`beta.*` is a reserved prefix.** It is how a cleanup pass tells a test
  account from a real one, now that registration is open and real people have
  accounts on the same box.
- **Use `+tag` addresses** on one real inbox rather than six inboxes.
- **Never grant `is_owner`.** It is the Schwab entitlement, it reaches a live
  brokerage, and no test needs it. Nothing in the codebase sets it.
- **Delete them afterwards**, with `manage_users.py delete beta.new`, which now
  removes their backtests too.

---

## 2. Critical flows

Fifteen. Each is pass/fail, and a failure needs the report in §3.

| # | Flow | Passes when |
|---|---|---|
| 1 | Registration | Confirmation email arrives. You are **not** signed in — confirm-first means no session exists until the link is clicked. The same answer comes back whether or not the address is already registered |
| 2 | Email verification | The link works once; a second click is refused; an expired one explains itself |
| 3 | Login | Correct password in; wrong password gives one generic message; six wrong ones throttle |
| 4 | Logout | Session revoked server-side — the back button does not restore the dashboard |
| 5 | Password reset | Link arrives, sets a new password, revokes every existing session |
| 6 | OAuth | All four providers land back signed in; an existing address links rather than duplicating |
| 7 | Backtest | Runs, shows results, double-clicking Run does not start two |
| 8 | Results | Charts, trades, equity, monthly returns all render |
| 9 | Replay | Socket connects, steps bar by bar, survives a pause |
| 10 | Export | CSV/JSON download; buttons are genuinely dead until the form is valid |
| 11 | Settings | Account dialog opens, shows the right state, downloads the data export |
| 12 | Account deletion | Closes, revokes sessions, removes backtests, blocks re-login |
| 13 | Network failure | Offline strip appears, no false logout, recovery works |
| 14 | Empty account | Every screen explains itself rather than looking broken |
| 15 | Error recovery | A forced error shows the boundary, and "Try again" recovers |

### Flows worth extra attention

- **12 (deletion) is irreversible and has no undo.** Test it on `beta.new`
  first, then on an account that owns backtests — the second is the case that
  used to fail outright with a foreign-key error.
- **13 (network)** is tested with DevTools → Network → Offline, not by unplugging
  a router. The one thing that must never happen is being bounced to the
  sign-in page: that is a false logout and it is a bug.
- **1, 2 and 5 are the ones that prove email.** The app now sends over SMTP,
  which relays to any recipient, and `confirm_required` reports `true` on the
  live site — so registration issues no session until a link is clicked. What
  has never been observed is a message arriving in somebody else's inbox.
  A tester who is not the operator completing flows 1, 2 and 5 is exactly the
  evidence that is missing.
- **`beta.unverified` is now genuinely blocked**, not merely flagged: the gate
  is live, so that account should meet the confirm-your-address screen and be
  refused the dashboard.

---

## 3. Reporting a bug

**Route:** open a GitHub issue on `wealthwise-advisors/trading-platform` with
the `beta` label. For anything with a security dimension, email the operator
directly instead — do not open a public issue.

**Every report needs all eight:**

1. What you did, step by step, from signed out
2. What you expected
3. What happened
4. Account used (`beta.*` name — **never a password**)
5. Browser, version, OS, and window width
6. Time, with timezone
7. The `error_id` if the app showed one — it ties your report to the server log
8. A screenshot, and the browser console if the page broke

### Severity

| | Meaning | Response |
|---|---|---|
| **S1** | Data loss, a security hole, or nobody can sign in | Stop the beta, fix now |
| **S2** | A critical flow is blocked with no workaround | Fix before the beta continues |
| **S3** | Broken with a workaround | Fix before general release |
| **S4** | Cosmetic, or a rough edge | Backlog |

Anything touching **authentication, another account's data, or account
deletion is S1 by default** and gets downgraded only after it is understood.

---

## 4. Browser and device matrix

Minimum before general release. The dashboard is chart-heavy, so widths matter
more than usual.

| | Chrome | Firefox | Safari | Edge |
|---|---|---|---|---|
| Desktop 1920 | ☐ | ☐ | ☐ | ☐ |
| Laptop 1440 | ☐ | ☐ | ☐ | ☐ |
| Tablet 768 | ☐ | ☐ | ☐ | — |
| Mobile 390 | ☐ | — | ☐ | — |
| Mobile 320 | ☐ | — | ☐ | — |

Safari is not optional: it is the only WebKit engine, and iOS has no
alternative. It is also the most likely to differ on date inputs and flexbox
heights, both of which this UI leans on.

---

## 5. Regression suite

Before each beta build, and again before release:

```bash
py -3.12 -m pytest tests/ -q          # includes the four security suites
cd web && npm test && npx tsc -b --force && npx oxlint src
py -3.12 -m ruff check .
py -3.12 -m bandit -r src api -ll -q --exclude src/data/schwabdev
```

A red security suite (`test_auth`, `test_isolation`, `test_oauth_auth`,
`test_reset_auth`, `test_account_deletion`, `test_verification_gate`,
`test_account_data`) stops the release. Those suites assert refusals, and a
refusal that stops happening is not a flaky test.

---

## 6. Known issues

Kept current, and shown to testers before they start so they do not spend time
re-reporting them.

| Issue | Severity | Status |
|---|---|---|
| Real inbox delivery has never been confirmed by a recipient who is not the operator | S2 | SMTP is configured and the full chain is verified over a real socket; only an actual inbox is unproven. **Flows 1, 2 and 5 confirm it** |
| Crash reporting is dormant until an endpoint is configured | S4 | Code complete, needs `VITE_AUTOTRADER_ERROR_DSN` |
| Charts have no screen-reader alternative | S3 | Trade data is reachable in the trade log table |
| CSP keeps `'unsafe-inline'` for scripts | S3 | Known and accepted — see below |
| White on the primary gradient button is 2.83:1 at the light stop | S3 | WCAG AA needs 4.5:1. Fixing it requires darkening the brand gradient ~10%; not changed unilaterally |

---

## 7. Results

**Status: not started.** No tester has run any flow above.

| Round | Dates | Testers | Flows passed | S1 | S2 | S3 | S4 |
|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — |

Do not mark the product beta-tested until this table has a row in it.

---

## 8. Why the CSP still allows inline script

Checked deliberately, not overlooked.

The policy is otherwise tight — `default-src 'self'`, `frame-ancestors 'none'`,
`form-action 'self'`, `base-uri 'self'`, `object-src 'none'`, `connect-src 'self'`
— and every one of those is live and doing work. What it keeps is
`script-src 'unsafe-inline'`.

**Why it cannot simply be removed.** The sign-in, sign-up, help, legal and 404
pages are single self-contained HTML files, each carrying its own `<script>` and
`<style>` inline. They are served by nginx straight off disk. Dropping
`'unsafe-inline'` stops every one of those blocks executing, which breaks
sign-in — so removing the directive without doing the work first takes the site
down rather than hardening it.

**The correct fix, when it is done.** Per-request nonces: nginx generates a
random nonce per response, injects it into every `<script nonce="…">`, and emits
it in the header. That requires a template step in front of files that are
currently static — `ngx_http_sub_module` at minimum, or moving those pages into
a renderer. Hashes (`'sha256-…'`) are the alternative and are worse here: every
edit to any inline block changes its hash, so the policy silently breaks the
page the next time someone fixes a typo.

**What was verified instead:** nothing more dangerous was introduced. There is
no `'unsafe-eval'`, no `*` source, no `data:` in `script-src`, and no
`unsafe-inline` in `frame-ancestors`, `form-action`, `base-uri` or `object-src`
— the directives that actually stop clickjacking, form hijacking and
exfiltration all hold without it.
