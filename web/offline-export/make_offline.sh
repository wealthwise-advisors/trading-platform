#!/bin/bash
# One command: the offline copy of the app for a date range, as ONE HTML file sir can open anywhere.
#   bash web/offline-export/make_offline.sh 2026-11-23 2026-11-27 "D:/AutoTrader_ES_23-27_Nov_2026.html"
# Needs the API running on :8000 with Schwab authenticated. Takes ~10-20 minutes (13 backtests).
set -eo pipefail
START=$1; END=$2; OUT=$3
[ -n "$OUT" ] || { echo "usage: make_offline.sh <start YYYY-MM-DD> <end YYYY-MM-DD> <out.html>"; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$HERE/.work"; mkdir -p "$WORK"
curl -sf -m 10 http://127.0.0.1:8000/api/health > /dev/null || { echo "FAILED: the API is not running on :8000"; exit 1; }
echo "1/3 recording $START to $END from Schwab ..."
PYTHONIOENCODING=utf-8 py -3.12 "$HERE/record_app.py" "$START" "$END" "$WORK/rec.json"
echo "2/3 building the app ..."
cd "$HERE/.." && VIEWER_OUT="$WORK/build" npx vite build --config vite.offline.config.ts --logLevel error
echo "3/3 packing one file ..."
PYTHONIOENCODING=utf-8 py -3.12 "$HERE/pack_offline.py" "$WORK/build" "$WORK/rec.json" "$OUT"
