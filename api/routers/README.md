# 🛣 `api/routers`

**REST endpoints and the replay socket.**

The replay router is the interesting one: a session is created over HTTP and then
driven over a **WebSocket**, one message per tick. Only panes that actually closed a
bar are sent, so a 1h pane contributes nothing on 59 of every 60 ticks and the client
leaves it untouched instead of redrawing it.

### Files in this directory

| File | Purpose | Lines |
|---|---|---:|
| [`replay.py`](replay.py) | Live replay: create a session, then drive it bar-by-bar over a WebSocket. | 480 |
| [`backtests.py`](backtests.py) | Backtest run + result sub-resource endpoints. | 335 |
| [`meta.py`](meta.py) | Health check and reference/meta endpoints. | 247 |
| [`optimize.py`](optimize.py) | Strategy Optimizer — sweeps a strategy's own parameter grid (from strategy_registry.STRATEGIES) through the… | 115 |
| [`data_export.py`](data_export.py) | Raw OHLC data export -- pick a symbol, date range, and data source, get back a CSV/Excel/PDF/Word file. | 84 |
| [`schwab.py`](schwab.py) | Schwab OAuth2 flow — thin wrapper around SchwabDataProvider's existing auth methods… | 64 |

---

<sub>[⬅ Back to the project README](../../README.md)</sub>
