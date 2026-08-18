# `legacy/` — the retired repositories, preserved

Historical reference only. **Nothing here is built, tested, imported or deployed.**

## Why this exists

Six repositories sat alongside this one, each carrying a README that said the work
had *"moved to wealthwise-advisors/trading-platform"* and was *"kept for history"*.
Read quickly, that says they are empty and safe to delete.

They were not. Between them they held **442 files**, and none of that code is in
this repository — `trading-platform` is a **rebuild**, not a merge. The Streamlit
application was retired and the Elliott Wave engine was removed and rewritten from
scratch, so the originals survived only in those repositories.

Checked before archiving, against this repository's tracked files:

| Looked for | Found in `trading-platform` |
|---|---|
| `swings_divergence` | 0 files |
| `wealth_wise_project` | 0 files |
| `elliot_wave` | 0 files |
| `ew_backtest` | 0 files |
| `assign_wave_numbers` | 0 files |
| `multi_indicator_divergence` | 0 files |

Deleting those repositories first would have destroyed all of it. This directory is
the copy that makes deletion safe.

## What came from where

| Directory | Source repository | Files | What it was |
|---|---|---|---|
| `trading-strategy/` | `wealthwise-advisors/trading-strategy` | 219 | Swings/divergence strategy work and a vendored `backtesting` library |
| `trading-web/` | `wealthwise-advisors/trading-web` | 181 | Three React + Flask applications: the original, a Schwab variant and a replay variant |
| `Wealthwise/` | `wealthwise-advisors/Wealthwise` | 23 | Per-timeframe Elliott Wave scripts, Terraform and Ansible deployment |
| `backtest/` | `wealthwise-advisors/backtest` | 19 | Elliott Wave backtester, Schwab client, vendored `schwabdev` |
| `local/cloud/` | local disk only | 6 | Reference copies of the Docker and workflow files |
| `local/BackTest_Results/` | local disk only | 1 | A 2021 strategy report |

Cloned at depth 1 — the tip only. The old histories were deliberately **not**
brought across: at least one of them contains committed Schwab tokens, and pulling
that history in would have imported the exposure along with the code.

## Credentials were removed on the way in

**36 of these files hardcoded live Schwab credentials.** Every such value was
replaced before committing. See [REDACTIONS.md](REDACTIONS.md) for the file-by-file
list — key names only, never values.

This is the part worth understanding: copying the code verbatim would have made the
exposure *worse*, not neutral. The same credentials would then sit in one more
place, and that place is the repository that actually deploys to production.

**Redacting a copy does not un-expose a credential.** Everything in REDACTIONS.md
should be rotated at the provider regardless of what happens to these files.

## Not in here

- **`Data/`** — 433 MB of market data, including a single 335 MB file. GitHub rejects
  any file over 100 MB, so it cannot be committed normally. It lives in the
  `wealthwise-advisors/data` repository via Git LFS, and this repository already
  carries 5,000-row samples of the same files under `data/sample/`.
- **`.claude/`** — local editor and agent settings, machine-specific and already
  ignored by `.gitignore`.

## If you need something from here

Copy it forward deliberately and bring it up to current standards — these files
predate the current test suite, the shared bar aggregator and the credential
handling in `config/`. Do not import from `legacy/` at runtime.
