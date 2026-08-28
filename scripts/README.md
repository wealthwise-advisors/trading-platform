<div align="center">

# 🛠 Command-Line Tools

**Everything you run by hand.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| ▶️ **Run the app locally** | `py -3.12 scripts/run_local.py` ➜ one origin on `:8800` |
| 👤 **Manage accounts** | `py -3.12 scripts/manage_users.py list` |
| 🐍 **Python** | **Must be 3.12.** 3.14 breaks `pandas_ta` and fakes a test failure |
| 📁 **Path** | `scripts/` |
| 📦 **Holds** | `6` files · `771` lines |


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`run_local.py`](run_local.py) | 🖥 Serves the sign-in pages, the built dashboard and the API on **one** port, so local matches production. | 203 |
| [`manage_users.py`](manage_users.py) | 👤 Create, inspect, disable and link accounts. | 310 |
| [`run_backtest.py`](run_backtest.py) | ⏱ Run a backtest from the terminal, no browser. | 109 |
| [`generate_data.py`](generate_data.py) | 🎲 Write synthetic bars. | 34 |
| [`download_rithmic_data.py`](download_rithmic_data.py) | 📡 Pull history from Rithmic. | 70 |
| [`run-autotrader.cmd`](run-autotrader.cmd) | 🪟 Windows launcher. | 45 |


---

## 💡 Worth knowing

- ➜ **`run_local.py` prefers the Desktop copies of the sign-in pages** over [`web/public/`](../web/public). If a change seems not to apply locally, that is why.


---

<div align="center">

<sub>⬅ <a href="../README.md">Project README</a></sub>

</div>
