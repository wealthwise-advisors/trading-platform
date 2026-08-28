<div align="center">

# 🗃 Archived Predecessors

**Five retired codebases, kept readable. None of it runs.**

![status](https://img.shields.io/badge/status-frozen-64748b?style=flat-square) ![built](https://img.shields.io/badge/built-never-ef4444?style=flat-square) ![files](https://img.shields.io/badge/files-442-0ea5e9?style=flat-square)

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **What this is** | The code that came **before** this platform, preserved so it is not lost |
| 🚫 **Not built · not tested · not imported · not deployed** | Nothing here is on any code path |
| 🔄 **Relationship to `src/`** | This platform is a **rebuild**, not a merge — none of this code was carried over |
| 🛡 **Dependabot** | Alerts raised here are dismissed as `not_used` |
| 📁 **Path** | `legacy/` |
| 📦 **Holds** | `1` files · `71` lines · `5` subfolders |


---

## 🔄 How it fits together

```
   trading-strategy ─┐
   trading-web ──────┤
   Wealthwise ───────┼──►  legacy/   (frozen, reference only)
   backtest ─────────┤        ╳  no import reaches src/
   local ────────────┘
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`REDACTIONS.md`](REDACTIONS.md) | 🔒 What was stripped before archiving, and why. | 71 |


---

## 🗃 Subfolders

| Folder | ➜ What lives there |
|:--|:--|
| [`Wealthwise/`](Wealthwise) | 🌊 Per-timeframe Elliott Wave scripts, Terraform, Ansible — **23 files** |
| [`backtest/`](backtest) | ⏱ Elliott Wave backtester, Schwab client, vendored `schwabdev` — **19 files** |
| [`local/`](local) | ☁️ Reference copies of Docker and workflow files, plus one 2021 report — **7 files** |
| [`trading-strategy/`](trading-strategy) | 📈 Swings/divergence work + a vendored `backtesting` library — **219 files** |
| [`trading-web/`](trading-web) | 🌐 Three React + Flask apps: original, Schwab, replay — **181 files** |


---

## 💡 Worth knowing

- ➜ **Read it, do not import it.** Anything worth keeping gets rewritten into [`src/`](../src) with tests.
- ➜ **Secrets were removed before archiving** — see [`REDACTIONS.md`](REDACTIONS.md).


---

<div align="center">

<sub>⬅ <a href="../README.md">Project README</a></sub>

</div>
