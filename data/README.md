<div align="center">

# 📊 Data & Runtime State

**Bars going in, results coming out. Almost none of it is tracked.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Holds** | The SQLite database, the CSV archive, and saved runs |
| 🚫 **Gitignored** | The `.db` files and `historical/` — they are machine state, not source |
| 📦 **Full archive** | [`wealthwise-advisors/data`](https://github.com/wealthwise-advisors/data) — 433 MB, Git LFS |
| 📦 **Holds** | `2` files · `950` lines · `4` subfolders |


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`autotrader.db`](autotrader.db) | 🗄 The live database — accounts, sessions, saved backtests. | 552 |
| [`local-demo.db`](local-demo.db) | 🧪 A throwaway database for [`scripts/run_local.py`](../scripts/run_local.py). | 398 |


---

## 🗃 Subfolders

| Folder | ➜ What lives there |
|:--|:--|
| [`backtests/`](backtests) | 💾 Saved run artefacts |
| [`historical/`](historical) | 📈 Your own full CSV archive (gitignored) |
| [`local-site/`](local-site) | 🖥 What the local rig serves — assembled, not authored |
| [`sample/`](sample) | 🎲 5,000-row slices that ship with the code, so tests and demos need no download |


---

## 💡 Worth knowing

- ➜ **`data/sample/` is enough to run everything.** The full archive is only needed for real history.
- ➜ **`local-site/` is generated.** Editing it achieves nothing — the source is [`web/public/`](../web/public).


---

<div align="center">

<sub>⬅ <a href="../README.md">Project README</a></sub>

</div>
