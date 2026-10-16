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
| 📦 **Holds** | `8` files · `1,060` lines |


---

## 🔄 How it fits together

```
   run_local.py      ──► API :8801 + pages ──► ONE origin on :8800
                          (matches production's shape, which is the point)

   manage_users.py   ──► the database directly, no HTTP
   run_backtest.py   ──► src/ directly, no server, no browser
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`run_local.py`](run_local.py) | 🖥 Serves the built dashboard and the API on **one** port, so local matches production. | 183 |
| [`manage_users.py`](manage_users.py) | 👤 List, disable, enable and delete accounts. | 126 |
| [`run_backtest.py`](run_backtest.py) | ⏱ Run a backtest from the terminal, no browser. | 109 |
| [`generate_data.py`](generate_data.py) | 🎲 Write synthetic bars. | 34 |
| [`download_rithmic_data.py`](download_rithmic_data.py) | 📡 Pull history from Rithmic. | 70 |
| [`run-autotrader.cmd`](run-autotrader.cmd) | 🪟 Windows launcher. | 45 |


---

## 💡 Worth knowing

- ➜ **There is no sign-in.** `run_local.py` opens straight onto the dashboard, and clears any sign-in pages an older run left behind.


---

<div align="center">

<sub>⬅ <a href="../README.md">Project README</a></sub>

</div>
