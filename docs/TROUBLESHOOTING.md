# Troubleshooting

## `ModuleNotFoundError` after a fresh install

Run `pip install -e ".[dev]"` (not just `pip install -r requirements.txt`)
so the `autotrader` package itself gets registered. If you only ran the
plain `requirements.txt` install, also run `pip install -e . --no-deps`.

## A synthetic test fixture's expected pivot never shows up in the swings list

N-bar fractal pivot detection (`identify_swings`, default `left=2,
right=2`) needs CONFIRMING bars on **both sides** of a pivot. A price
series that starts or ends exactly at its own intended first/last pivot
never gives that pivot the confirming bars it needs — it's silently
dropped, not flagged. If you're building a new OHLC fixture, add a few
small leading/trailing bars that pull back toward (not past) the endpoint
pivots.

## Schwab "Live Data" shows unavailable even with credentials set

`GET /api/data-sources` actually tries to construct a
`SchwabDataProvider()` (fixed in the Task 10 audit — it previously
reported `True` unconditionally, regardless of configuration). If it's
`False`, check that `config/credentials.yaml`'s `schwab` section is filled
in, and that `config/schwab_tokens.json` exists (or complete the auth flow
once via the UI).

## Schwab returns implausible prices for BTC or no data for EURUSD

Confirmed and documented during Task 8: Schwab's `BTC` symbol via this
provider returns synthetic-looking ~$48 prices, not real Bitcoin, and
`EURUSD` returns no data at all through the configured endpoint. Both are
data-source limitations, not bugs in this codebase. Stick to the verified
real-data symbols: ES, NQ, SPY, GC, CL.

## CORS errors in the browser console (production/Docker deployment)

Set `AUTOTRADER_CORS_ORIGINS` to include whatever origin your frontend is
actually served from. The default (`localhost:5173,localhost:3000`)
only covers local dev. `docker-compose.yml`'s default topology (nginx
proxies `/api/*` to the API — see `web/nginx.conf`) avoids this entirely
because the browser only ever talks to one origin; you'll only hit this if
you deploy the API and frontend as genuinely separate origins.

## Live trading doesn't do anything

By design — `src/live/trader.py` and `src/broker/rithmic_broker.py` are a
documented stub, not part of the v1.0.0 certified scope. See
[RELEASE.md](RELEASE.md#audit) "Known limitations."

## Rithmic import fails / `pyrithmic` not installed

Rithmic is an optional extra (`pip install -e ".[live]"`), not a default
dependency — the API's `/api/data-sources` endpoint reports it as
unavailable rather than crashing if it's not installed, and the "Real Data
(Rithmic)" dropdown option is disabled in the UI.

## `pytest` fails only in CI, not locally

Confirm you're on Python 3.12 — fractal pivot detection has
floating-point sensitivity that's been observed to differ across
pandas/numpy versions; CI pins the same 3.12 + current `requirements.txt`
versions this was verified against.
