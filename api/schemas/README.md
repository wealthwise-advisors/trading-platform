# 📋 `api/schemas`

**Request and response models.**

Pydantic models, which means validation happens at the edge. A malformed request is
rejected with a message naming the field, rather than becoming a `500` from deep
inside the engine.

### Files in this directory

| File | Purpose | Lines |
|---|---|---:|
| [`backtest.py`](backtest.py) | Pydantic request/response models for the backtest endpoints. | 116 |
| [`elliott_wave.py`](elliott_wave.py) | Pydantic response models for the Elliott Wave endpoint. | 65 |
| [`replay.py`](replay.py) | Request/response models for the live-replay endpoints. | 58 |
| [`optimize.py`](optimize.py) | Request/response models for the Strategy Optimizer (parameter sweep). | 38 |
| [`schwab.py`](schwab.py) | Request/response models for the Schwab OAuth endpoints. | 21 |

---

<sub>[⬅ Back to the project README](../../README.md)</sub>
