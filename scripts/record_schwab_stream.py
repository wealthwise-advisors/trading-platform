"""Record Schwab's futures stream to a file, for the stream hub's tests (upgrade plan, Feature 3).

    py -3.12 scripts/record_schwab_stream.py --seconds 600 --out tests/fixtures/schwab_stream_es.jsonl

Logs in with the app's own tokens, subscribes CHART_FUTURES (1-minute bars) and
LEVELONE_FUTURES (quotes) for the given roots, and writes every raw message as one
JSON line: {"t": <receive time, epoch ms>, "msg": <message as Schwab sent it>}.
Nothing is parsed here, so the recording shows exactly what Schwab sends and the
hub's parser is tested against that, not against what we think it sends.

Uses its own asyncio connection rather than schwabdev's Stream.start(), whose
reconnect logic swallows the errors this recording exists to see.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CHART_FIELDS = "0,1,2,3,4,5,6,7,8"          # key, time, O, H, L, C, V, (7, 8 if sent)
LEVELONE_FIELDS = "0,1,2,3,4,5,8,9,10,11,12,13,14,18,19,20,22,23,33,34,35"


async def record(seconds: int, out: Path, roots: list[str]) -> int:
    import websockets
    from src.data.schwab_provider import SchwabDataProvider

    provider = SchwabDataProvider()
    provider._ensure_client()
    client = provider._client
    prefs = client.preferences()
    prefs.raise_for_status()
    info = prefs.json()["streamerInfo"][0]
    keys = ",".join(r if r.startswith("/") else f"/{r}" for r in roots)
    rid = 0

    def req(service: str, command: str, parameters: dict | None = None) -> dict:
        nonlocal rid
        rid += 1
        r = {"service": service, "command": command, "requestid": rid,
             "SchwabClientCustomerId": info["schwabClientCustomerId"],
             "SchwabClientCorrelId": info["schwabClientCorrelId"]}
        if parameters:
            r["parameters"] = parameters
        return r

    n = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        def keep(raw: str) -> None:
            nonlocal n
            n += 1
            f.write(json.dumps({"t": int(time.time() * 1000), "msg": json.loads(raw)}) + "\n")
            f.flush()

        async with websockets.connect(info["streamerSocketUrl"], ping_interval=None) as ws:
            await ws.send(json.dumps({"requests": [req("ADMIN", "LOGIN", {
                "Authorization": client.access_token,
                "SchwabClientChannel": info["schwabClientChannel"],
                "SchwabClientFunctionId": info["schwabClientFunctionId"]})]}))
            keep(await ws.recv())
            await ws.send(json.dumps({"requests": [
                req("CHART_FUTURES", "SUBS", {"keys": keys, "fields": CHART_FIELDS}),
                req("LEVELONE_FUTURES", "SUBS", {"keys": keys, "fields": LEVELONE_FIELDS}),
            ]}))
            end = time.time() + seconds
            while time.time() < end:
                try:
                    keep(await asyncio.wait_for(ws.recv(), timeout=max(1.0, end - time.time())))
                except asyncio.TimeoutError:
                    break
            await ws.send(json.dumps({"requests": [req("ADMIN", "LOGOUT")]}))
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=600)
    ap.add_argument("--out", type=Path, default=Path("tests/fixtures/schwab_stream_es.jsonl"))
    ap.add_argument("roots", nargs="*", default=["ES"])
    a = ap.parse_args()
    n = asyncio.run(record(a.seconds, a.out, a.roots))
    print(f"{n} messages -> {a.out}")


if __name__ == "__main__":
    main()
