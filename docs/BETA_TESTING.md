# Beta Testing

**No beta test has been run yet.** This document describes the process; it is
not a record that anything has happened. Nothing here should be read as
evidence that the flows below have been exercised by real people. Fill in
"Results" at the bottom when they have.

---

## 1. Access

There are no test accounts to create. **Sign-in was removed on 2026-10-16**: the
app opens straight from its link, and every visitor runs as the same workspace
account.

**Rules that are not negotiable:**

- **No credentials in this repository, ever** — not here, not in a fixture, not
  in a comment.
- **Testers share one workspace.** Saved configurations, the paper-trading
  session and the journal are the same for everyone with the link. Agree who is
  driving the paper session before starting it, and name saved configurations
  `beta.<you>.<what>` so a cleanup pass can find them.
- **Share the link only with testers.** With no sign-in, the URL is the access
  control — anyone who has it can use every feature, live data included.

---

## 2. Critical flows

Nine. Each is pass/fail, and a failure needs the report in §3.

| # | Flow | Passes when |
|---|---|---|
| 1 | Opening the app | The link lands on the dashboard with no sign-in screen. The first visit shows the introduction; Skip dismisses it, and it stays dismissed in another browser |
| 2 | Backtest | Runs, shows results, double-clicking Run does not start two |
| 3 | Results | Charts, trades, equity, monthly returns all render |
| 4 | Replay | Socket connects, steps bar by bar, survives a pause |
| 5 | Export | CSV/JSON download; buttons are genuinely dead until the form is valid |
| 6 | Saved configurations | Save a setup, open the app in another browser — it is there |
| 7 | Network failure | Offline strip appears, nothing is lost, recovery works |
| 8 | Empty workspace | Every screen explains itself rather than looking broken |
| 9 | Error recovery | A forced error shows the boundary, and "Try again" recovers |

### Flows worth extra attention

- **7 (network)** is tested with DevTools → Network → Offline, not by unplugging
  a router. The app must stay exactly where it was and recover when the
  connection returns.
- **6 (saved configurations)** is the proof that state is server-side and
  shared — and the reminder that one tester's save is everyone's.

---

## 3. Reporting a bug

**Route:** open a GitHub issue on `wealthwise-advisors/trading-platform` with
the `beta` label. For anything with a security dimension, email the operator
directly instead — do not open a public issue.

**Every report needs all eight:**

1. What you did, step by step, from opening the link
2. What you expected
3. What happened
4. Any saved configuration involved (`beta.*` name)
5. Browser, version, OS, and window width
6. Time, with timezone
7. The `error_id` if the app showed one — it ties your report to the server log
8. A screenshot, and the browser console if the page broke

### Severity

| | Meaning | Response |
|---|---|---|
| **S1** | Data loss, a security hole, or the app will not open | Stop the beta, fix now |
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

A red workspace suite (`test_isolation`, `test_account_data`,
`test_live_sessions`, `test_backup_restore`, `test_account_deletion`) stops the
release. They hold the data-layer isolation and the cross-origin refusal, and a
refusal that stops happening is not a flaky test.

---

## 6. Known issues

Kept current, and shown to testers before they start so they do not spend time
re-reporting them.

| Issue | Severity | Status |
|---|---|---|
| ~~Real inbox delivery unconfirmed~~ | — | **RESOLVED 2026-08-31.** A sign-in code sent from the deployed site arrived in a real inbox. Email delivery works; password reset and confirmation ride the same transport |
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

**Why it cannot simply be removed.** The help, legal and 404 pages are single
self-contained HTML files, each carrying its own `<script>` and `<style>`
inline. They are served by nginx straight off disk. Dropping `'unsafe-inline'`
stops every one of those blocks executing — so removing the directive without
doing the work first breaks those pages rather than hardening the site. (The
sign-in and sign-up pages that were also on this list went with sign-in on
2026-10-16.)

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
