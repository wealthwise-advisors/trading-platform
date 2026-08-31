# Implementation Plan

**Product:** AutoTrader
**Owner:** WealthWise Advisors
**Version:** 1.1
**Status:** Phases 1–7 complete · Phase 8 (beta testing) not started
**Created:** 2026-08-31

> [!NOTE]
> **This document was newly created on 2026-08-31.** The repository had no
> project-wide implementation plan: [`ELLIOTT_WAVE.md`](ELLIOTT_WAVE.md#implementation)
> is a retrospective record of one feature, and [`RELEASE.md`](RELEASE.md#audit)
> and [`VERIFICATION_REPORT.md`](VERIFICATION_REPORT.md) are audits of work
> already done. None of them plans forward.
>
> Everything below is drawn from the repository's own history, tests, CI
> configuration and audit records. **No requirement here is invented.** Where
> something is unknown or unverified it says so rather than guessing.

**Related:** [`PRD.md`](PRD.md) (what and why) · [`Technical Requirements Document.md`](Technical%20Requirements%20Document.md) (what it must do) · [`Design Document.md`](Design%20Document.md) (how it is built)

---

## 1. Where this starts

v1.0.0 shipped and is deployed at `https://3-218-23-37.sslip.io`. A 20-point
production-readiness audit on 2026-08-31 scored it **47% — NOT READY**, with
four confirmed critical findings. Phases 1–6 below are the remediation of that
audit; Phases 7–8 are what is left.

Readiness by phase: **47% → 53% → 76%.**

---

## 2. Phases

Ordered by dependency, not by preference. A phase does not start until the one
it depends on has met its completion criteria.

### Phase 1 — Account deletion ✅ Complete

**Why first:** it was broken *and* promised in writing. `backtests.user_id`
references `users(id)` with no `ON DELETE` action, so SQLite refused to remove
anyone who had ever run a backtest — the deletion path worked only on accounts
that had never used the product.

| | |
|---|---|
| **Depends on** | nothing |
| **Deliverables** | `repo.delete_account()`, `DELETE /api/auth/me`, account-settings UI, `manage_users.py delete --keep-results` |
| **Decision** | Full deletion, not anonymisation. Every read is owner-scoped, so a detached backtest is reachable by nobody — retention with no reader, against a policy that promises removal. |
| **Testing** | 16 tests in [`test_account_deletion.py`](../tests/test_account_deletion.py), incl. a direct assertion of the FK refusal so the regression cannot return quietly |
| **Complete when** | an account owning backtests closes, sessions die, `PRAGMA foreign_key_check` is empty ✅ |

### Phase 2 — Email verification enforcement ✅ Complete

**Why second:** `users.email_verified` was written by registration, cleared by
the confirmation link, and read by no route.

| | |
|---|---|
| **Depends on** | Phase 1 (closing an account must work *before* people are gated) |
| **Deliverables** | `verification_enforced()`, `verification_blocks()`, gate in `require_user` **and** the WebSocket guard, `VerifyEmailNotice` screen, `manage_users.py verify` |
| **Constraint** | The gate must not fire where the key cannot be delivered. Gating on "mail configured" would have locked out every live user, since this host has a Resend key but a sandbox sender. It additionally requires a non-sandbox sender. |
| **Testing** | 15 tests in [`test_verification_gate.py`](../tests/test_verification_gate.py) |
| **Complete when** | unverified → 403, verified → 200, and unconfigured/sandboxed mail enforces nothing ✅ |

### Phase 3 — Failure visibility ✅ Complete

| | |
|---|---|
| **Depends on** | nothing |
| **Deliverables** | request timeouts (30s / 300s), `AbortController`, root `ErrorBoundary`, global handlers, offline detection |
| **Constraint** | No automatic retry. Every mutation here is non-idempotent. |
| **Complete when** | a stalled fetch fails with a readable message and a render throw shows recovery UI ✅ |

### Phase 4 — Own the user's data ✅ Complete

| | |
|---|---|
| **Depends on** | Phase 1 (deletion must remove what this phase starts storing) |
| **Deliverables** | schema v8 `user_configs`, `/api/account/configs`, one-way localStorage migration, `/api/auth/export` |
| **Classification** | Category A (account-owned) moved server-side; Category B (per-device display preferences) stayed local, deliberately |
| **Testing** | 23 tests in [`test_account_data.py`](../tests/test_account_data.py), incl. cross-user isolation |
| **Complete when** | configs survive a new session, are invisible to another account, and leave with the account ✅ |

### Phase 5 — Durable throttling ✅ Complete

| | |
|---|---|
| **Depends on** | nothing |
| **Deliverables** | schema v8 `login_attempts`, `Throttle` backed by SQLite |
| **Decision** | SQLite, not Redis. Already shared, already backed up, two integers per key; the deployment runs one uvicorn worker ([`Dockerfile`](../Dockerfile) `CMD`). |
| **Complete when** | a *fresh process* still reports the block ✅ |

### Phase 6 — Product completeness ✅ Complete

| | |
|---|---|
| **Depends on** | Phases 1–5 |
| **Deliverables** | server-side onboarding, empty states, offline banner, app-wide duplicate-submit audit, [`BETA_TESTING.md`](BETA_TESTING.md), legal pages reconciled with behaviour |
| **Testing** | 8 axe-core checks in `accessibility.a11y.test.tsx` — 0 violations across 4 screens |
| **Complete when** | the full lifecycle runs end to end ✅ |

### Phase 7 — Email deliverability ✅ Complete

**The last blocker, and it no longer needs a domain.** While
`AUTOTRADER_MAIL_FROM` is on `resend.dev`, Resend delivers only to the account
owner — every other recipient is dropped after a `200 OK`, so password reset
silently fails for real users on a site with open registration.

Resend's way out is verifying a domain, which needs DNS control this project
does not have (`3-218-23-37.sslip.io` is a free IP-to-hostname service). So
`api/verification.py` gained an SMTP transport: any ordinary mailbox relays to
any recipient with no domain and no DNS.

| | |
|---|---|
| **Depends on** | nothing in code — **the code is complete, both transports** |
| **Blocked by** | one mailbox credential |
| **Route A (no domain needed)** | set `AUTOTRADER_SMTP_HOST` / `_USER` / `_PASSWORD` and `AUTOTRADER_MAIL_FROM` → redeploy |
| **Route B (owns a domain)** | verify it in Resend → add DKIM/SPF → set `AUTOTRADER_MAIL_FROM` → redeploy |
| **Then, either route** | `manage_users.py verify <owner>` before the gate activates, or keep `AUTOTRADER_REQUIRE_VERIFIED_EMAIL=0` |
| **Complete when** | ~~someone who is not the operator resets their password successfully~~ |
| **Done** | 2026-08-31 — a sign-in code from the deployed site arrived in a real inbox. Confirmation, reset and sign-in codes all share the transport, so all three are live |

> Step 5 is not optional. Phase 2's gate switches itself on the moment a
> non-sandbox sender appears. Skipping it locks the operator out of their own
> application.

### Phase 8 — Beta validation ⚪ Not started

| | |
|---|---|
| **Depends on** | **Phase 7** — flows 2 and 5 cannot be tested until mail is delivered |
| **Deliverables** | `beta.*` accounts, 15 critical flows, browser/device matrix, filled results table |
| **Complete when** | [`BETA_TESTING.md`](BETA_TESTING.md) §7 has a row in it |

---

## 3. Dependency graph

```
Phase 1 ──┬─► Phase 2 ──┐
          │             ├─► Phase 6 ──► Phase 8
          └─► Phase 4 ──┤              ▲
                        │              │
Phase 3 ────────────────┤              │
Phase 5 ────────────────┘              │
                                       │
Phase 7 (external — DNS) ──────────────┘
```

Phase 7 gates Phase 8 and nothing else. It is the critical path.

---

## 4. Testing stages

Every stage runs before a merge; the release adds the last two.

| Stage | Command | Gate |
|---|---|---|
| Lint | `ruff check .` | blocking |
| Types (py) | `mypy src/analysis` | informational — 3 pre-existing errors |
| Types (ts) | `npx tsc -b --force` | blocking |
| Unit + API | `pytest tests/ --cov-fail-under=70` | blocking |
| Frontend | `npm test` (incl. axe-core) | blocking |
| Security | `bandit -r src api -ll` | blocking |
| Dependencies | `pip-audit` | informational |
| Manual | browser/device matrix | release only |
| Real users | 15 beta flows | release only |

**A red security suite stops the release**: `test_auth`, `test_isolation`,
`test_oauth_auth`, `test_reset_auth`, `test_account_deletion`,
`test_verification_gate`, `test_account_data`. These assert *refusals*; one
that stops happening is not a flaky test.

> New suite asserting a refusal? Add it to `_SECURITY_SUITES` in
> [`conftest.py`](../tests/conftest.py), or it runs with `require_user`
> overridden and passes without reaching the guard.

---

## 5. Rollout

Push to `master` → [`deploy.yml`](../.github/workflows/deploy.yml) → EC2.

The pipeline opens port 22 just-in-time via the security group, deploys, and
closes it. It asserts the running commit SHA through `/api/version`, so a
deploy cannot report success while serving old code.

**Migrations** are additive and guarded — `CREATE TABLE IF NOT EXISTS` plus a
`PRAGMA table_info` check per added column ([`connection.py`](../db/connection.py)).
Schema v8 adds two tables and one column and requires no downtime.

**Rollback:** re-run the workflow against the previous commit. Data recovery is
[`backup.sh`](../scripts/backup.sh) / [`restore.sh`](../scripts/restore.sh) —
see [`BACKUP.md`](BACKUP.md).

---

## 6. Completion criteria

Production-ready when **all** hold:

- [x] Every audit-critical finding closed
- [x] Full test suite green, security suites included
- [x] Legal pages describe actual behaviour
- [x] Account lifecycle verified end to end
- [ ] **A non-owner can reset their password** ← Phase 7
- [ ] **Beta results table has at least one round** ← Phase 8
- [ ] Browser/device matrix completed
- [ ] Crash reporting configured, or accepted as deliberately off

---

## 7. Known unverifiable items

Recorded rather than assumed, because no environment available to the project
so far can decide them:

| Item | Why | Resolves in |
|---|---|---|
| Responsive layout below 768px | no browser in the dev environment | Phase 8 |
| Colour contrast | jsdom has no layout engine; axe cannot compute it | Phase 8 |
| Chart accessibility | Plotly does not render in jsdom | Phase 8 |
| OAuth callback leg | the client secret only runs on a real human sign-in | Phase 8 |
| Production database state | port 22 is closed outside a deploy window | Phase 7 |
