"""Record every answer the app's screens need, for an offline copy of the app.

Static calls once (account, strategies, symbols, quotes ...); for each of the 13 timeframes one
backtest over the whole range on live Schwab data (Globex hours) and every results call the
screens make. Backtest ids become OFFLINE-<tf> so offlineServer.ts can find them.

Usage (the API must be running on :8000 and Schwab authenticated):
    py -3.12 record_app.py 2026-11-09 2026-11-20 <out rec.json>
"""
import json
import sys
import urllib.request

B = "http://127.0.0.1:8000"
TFS = ["1m", "2m", "3m", "5m", "10m", "15m", "20m", "25m", "30m", "35m", "40m", "45m", "1h"]
START, END, OUT = sys.argv[1], sys.argv[2], sys.argv[3]


def get(u):
    return json.load(urllib.request.urlopen(B + u, timeout=900))


def post(u, d):
    r = urllib.request.Request(B + u, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=900))


rec = {"get": {}, "bt": {}}
for u in ["/api/auth/me", "/api/strategies", "/api/version", "/api/symbols?data_source=schwab",
          "/api/quotes?symbols=ES%2CNQ%2CYM%2CRTY%2CCL%2CGC", "/api/quotes?symbols=%24SPX%2C%24NDX%2C%24DJI%2C%24VIX"]:
    rec["get"][u] = get(u)
rec["get"]["/api/account/configs"] = []
# Only the recorded source is offered, so nothing on the page points at data the file has not got.
rec["get"]["/api/data-sources"] = [{"id": "schwab", "label": f"Live Data (Schwab) · recorded {START} to {END}", "available": True}]
rec["get"]["/api/schwab/status"] = {"available": True, "authenticated": True, "needs_reauth": False, "hours_remaining": 168, "error": None}

SUFFIX = ["", "/price-data", "/trades", "/equity-curve", "/monthly-returns", "/elliott-wave", "/chart-patterns",
          "/candlestick-patterns?min_confidence=0", "/zigzag?dev_3=0.0005&dev_10=0.001&dev_1=0"]
for tf in TFS:
    s = post("/api/backtests", {"symbol": "ES", "timeframe": tf, "data_source": "schwab", "strategy_id": "rsi_divergence",
                                "params": {}, "start_date": START, "end_date": END,
                                "session_start": "18:00:00", "session_end": "17:00:00"})
    bid = s["backtest_id"]
    one = {"post": s}
    for suf in SUFFIX:
        one[suf.split("?")[0] or "summary"] = get(f"/api/backtests/{bid}{suf}")
    rec["bt"][tf] = json.loads(json.dumps(one).replace(bid, f"OFFLINE-{tf}"))
    print(f"recorded {tf}", flush=True)
s = json.dumps(rec, separators=(",", ":"), ensure_ascii=False)
open(OUT, "w", encoding="utf-8").write(s)
print("recording MB", round(len(s.encode()) / 1e6, 1))
