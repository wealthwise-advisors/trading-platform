# 🖥 `web/src/features`

**The pages.**

| Feature | What it is |
|---|---|
| [`replay/`](replay) | **Market Grid** — the multi-timeframe grid, consolidated tape and playback controls |
| [`backtest/`](backtest) | Configure, run and read a scored backtest |
| [`export/`](export) | Pull bars out for use elsewhere |

`replay/ReplayPage.tsx` is the largest component in the app. The logic it depends on
is deliberately kept in [`../lib`](../lib), where it can be tested directly.

### Subdirectories

| Directory | Files |
|---|---:|
| [`backtest/`](backtest) | 2 |
| [`export/`](export) | 1 |
| [`replay/`](replay) | 1 |

---

<sub>[⬅ Back to the project README](../../../README.md)</sub>
