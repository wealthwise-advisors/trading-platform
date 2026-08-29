"""Say why the Schwab token file is not being accepted.

    py -3.12 scripts/schwab_token_doctor.py [path]

`SchwabDataProvider.is_authenticated()` returns False whenever `_read_tokens()`
returns None -- and `_read_tokens()` swallows the reason in a bare `except
Exception`. So the UI can only ever say "Not authenticated with Schwab", which
is the same message for a missing file, a malformed one, a file with the right
data under the wrong keys, and a genuinely expired refresh token. Four
different problems, one sentence, no way to tell them apart.

This prints the SHAPE of the file and what the provider concludes from it.

IT NEVER PRINTS A TOKEN.
------------------------
Key names, byte counts, and issue dates are not secrets -- they are exactly
what is needed to tell those four cases apart. Token values are never read into
a printable variable, never logged, and never returned. Running this in CI
output is safe by construction, not by remembering to be careful.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

EXPECTED = ("access_token_issued", "refresh_token_issued", "token_dictionary")
DEFAULT = "/app/config/schwab_tokens.json"


def report(path: str) -> int:
    print(f"  path            {path}")

    if not os.path.exists(path):
        print("  VERDICT         the file does not exist at this path")
        print("                  -> the app has nothing to read; put the new")
        print("                     token at config/schwab_tokens.json")
        return 1

    size = os.path.getsize(path)
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path),
                                            datetime.timezone.utc)
    print(f"  bytes           {size:,}")
    print(f"  modified (UTC)  {mtime.isoformat(timespec='seconds')}")

    if size == 0:
        print("  VERDICT         the file is EMPTY")
        return 1

    try:
        with open(path) as fh:
            data = json.load(fh)
    except Exception as exc:                       # noqa: BLE001 -- reporting
        print(f"  VERDICT         not valid JSON: {type(exc).__name__}: {exc}")
        return 1

    if not isinstance(data, dict):
        print(f"  VERDICT         top level is {type(data).__name__}, expected an object")
        return 1

    keys = sorted(data)
    print(f"  top-level keys  {keys}")

    missing = [k for k in EXPECTED if k not in data]
    if missing:
        print(f"  MISSING KEYS    {missing}")
        print("  VERDICT         the file is valid JSON but not the shape this")
        print("                  app writes. It expects exactly:")
        print(f"                    {list(EXPECTED)}")
        # The most common real cause: a raw schwabdev token dump, which is the
        # INNER object on its own rather than wrapped with the issue times.
        if "access_token" in data or "refresh_token" in data:
            print("                  This looks like a RAW token dump -- the inner")
            print("                  token_dictionary saved on its own, without the")
            print("                  two *_issued timestamps that wrap it.")
        return 1

    for key in ("access_token_issued", "refresh_token_issued"):
        raw = data[key]
        try:
            when = datetime.datetime.fromisoformat(raw)
        except Exception:                          # noqa: BLE001 -- reporting
            print(f"  VERDICT         {key} is not an ISO timestamp: {raw!r}")
            return 1
        age_h = (datetime.datetime.now(when.tzinfo) - when).total_seconds() / 3600
        print(f"  {key:15} {raw}   ({age_h:.1f}h ago)")

    td = data["token_dictionary"]
    if not isinstance(td, dict):
        print(f"  VERDICT         token_dictionary is {type(td).__name__}, expected an object")
        return 1
    print(f"  token_dict keys {sorted(td)}")       # names only, never values

    # Ask the provider itself, so this cannot disagree with the running app.
    try:
        # /app in the container, the repo root when run from a checkout.
        for root in ("/app", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))):
            if os.path.isdir(os.path.join(root, "src")):
                sys.path.insert(0, root)
                break
        from src.data.schwab_provider import SchwabDataProvider

        provider = SchwabDataProvider()
        at, rt, parsed = provider._read_tokens()
        print(f"  _read_tokens    {'OK' if parsed is not None else 'None  <-- the failure'}")
        print(f"  is_authenticated {provider.is_authenticated()}")
        hours = provider.refresh_token_hours_remaining()
        print(f"  hours remaining {hours:.1f}")
        if provider.is_authenticated():
            print("  VERDICT         the token is good; the app should show Live Data")
            return 0
        if hours <= 0:
            print("  VERDICT         the REFRESH token has expired (7-day window)")
            print("                  -> a new one is needed; refreshing cannot fix it")
        else:
            print("  VERDICT         the file parses but the provider still refuses it")
        return 1
    except Exception as exc:                       # noqa: BLE001 -- reporting
        print(f"  provider check  could not run: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(report(sys.argv[1] if len(sys.argv) > 1 else DEFAULT))
