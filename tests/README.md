# 🧪 `tests`

**1,492 tests. What the numbers on screen rest on.**

### What is defended here

- ➜ **Bar aggregation** — one aggregator, session-anchored, so no two paths can
  disagree about what a bar is
- ➜ **Follow-live across every timeframe** — all eleven, every position within a bar,
  seven combinations, five dates including both DST switches and a leap day
- ➜ **Determinism** — a session grown bar by bar must be byte-identical to one handed
  all the data at once
- ➜ **Elliott Wave rules** — a count that breaks a rule must be rejected
- ➜ **Error messages** — a bad request must name the field to change, not return a 500

### A test here earns its place by being able to fail

The follow-live matrix was written after a bug that only appeared on timeframes
coarser than 1m. **67 of its 107 cases fail against the commit that shipped that
bug** — which is the property that makes it worth running.

```bash
py -3.12 -m pytest              # all of it
py -3.12 -m pytest tests/test_follow_live_matrix.py -q
```

### Files in this directory

| File | Purpose | Lines |
|---|---|---:|
| [`test_indicator_correctness.py`](test_indicator_correctness.py) | Permanent guard on bar construction: boundaries AND OHLC, every timeframe. | 1,069 |
| [`test_multi_replay.py`](test_multi_replay.py) | Tests for the multi-timeframe replay clock. | 663 |
| [`test_replay_follow_live.py`](test_replay_follow_live.py) | Following the live market over the replay WebSocket. | 477 |
| [`test_swing_zigzag_regression.py`](test_swing_zigzag_regression.py) | Regression baseline for the Swing (major, 10-leg) / 3-Leg Deviation (minor) zigzag visualization --… | 436 |
| [`test_replay_extend.py`](test_replay_extend.py) | Tests for growing a live replay past the end of the snapshot it loaded. | 398 |
| [`test_follow_live_matrix.py`](test_follow_live_matrix.py) | Following the live market across EVERY timeframe, offset and date. | 321 |
| [`test_api_provider_errors.py`](test_api_provider_errors.py) | A provider that cannot serve the requested symbol is a BAD REQUEST, not a server defect. | 235 |
| [`test_reference_platform_parity.py`](test_reference_platform_parity.py) | Parity against the reference platform, pinned to bars it actually printed. | 201 |
| [`test_vwap_bands.py`](test_vwap_bands.py) | VWAP band regression tests. | 175 |
| [`test_schwab_redirect_parsing.py`](test_schwab_redirect_parsing.py) | How the pasted Schwab redirect URL is turned into an auth code. | 158 |
| [`test_symbol_universe.py`](test_symbol_universe.py) | The symbol list the UI offers must match what the backend can actually serve. | 117 |
| [`test_provider_timeframes.py`](test_provider_timeframes.py) | Every timeframe the UI offers must be loadable from every file/API provider. | 63 |
| [`test_engine.py`](test_engine.py) | Smoke tests for the backtesting engine. | 57 |

### Subdirectories

| Directory | Files |
|---|---:|
| [`fixtures/`](fixtures) | 1 |
| [`test_elliott_wave/`](test_elliott_wave) | 11 |

---

<sub>[⬅ Back to the project README](../README.md)</sub>
