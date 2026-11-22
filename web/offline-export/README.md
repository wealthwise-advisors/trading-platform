# Offline copy of the app

One HTML file with the whole app and a recorded date range inside it — for sending to someone
who has no access to the live app. It opens in Chrome with no server, login or internet.

```bash
# API running on :8000 with Schwab authenticated; ~10-20 minutes
bash web/offline-export/make_offline.sh 2026-11-23 2026-11-27 "D:/AutoTrader_ES_23-27_Nov_2026.html"
```

- **Works in the file:** every chart, all 13 timeframes (1m-1h), Run Backtest for any dates inside
  the recorded range, every results tab, patterns, Elliott Wave, Multi-chart.
- **Shows a message instead:** dates outside the range, 2h/4h/1D/1W/1M, Market Grid replay,
  Strategy Optimizer, saving and downloads — they need the live app.
- **Shorter ranges inside the recording** cut the recorded run; trades and swing letters come from
  the whole run (see the shortcut note in `offlineServer.ts`).
- Over ~25 MB (about two weeks of data) Gmail sends it as a Drive link; share it via Drive and ask
  the reader to download it, then open it in Chrome.

| File | Does |
|---|---|
| `make_offline.sh` | The one command: record, build, pack |
| `record_app.py` | Records every answer the screens need, per timeframe |
| `offlineServer.ts` | Answers the app from the recording, inside the browser |
| `main.tsx` · `index.html` | The app's entry, opening on the recorded run |
| `pack_offline.py` | Inlines the build and the recording into one HTML file |
