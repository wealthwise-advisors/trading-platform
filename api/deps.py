"""Shared FastAPI dependencies — config loading, contract specs.

Mirrors what ui/app.py's CONTRACT_SPECS dict and src.config.load_config already
provide; this module doesn't duplicate logic, just exposes it to routers.
"""

from functools import lru_cache

from src.config import load_config

# Same defaults ui/app.py hardcodes for symbols not in config/settings.yaml.
CONTRACT_SPECS = {
    "ES": dict(tick_size=0.25, tick_value=12.50, point_value=50.0),
    "NQ": dict(tick_size=0.25, tick_value=5.00, point_value=20.0),
    "MES": dict(tick_size=0.25, tick_value=1.25, point_value=5.0),
    "CL": dict(tick_size=0.01, tick_value=10.00, point_value=1000.0),
    "HG": dict(tick_size=0.0005, tick_value=12.50, point_value=25000.0),
}
# Starting level for SYNTHETIC series only -- real providers supply their own.
# Roughly where each instrument trades, so a generated series is not absurd.
BASE_PRICES = {
    "ES": 4500.0, "NQ": 15000.0, "MES": 4500.0, "MNQ": 15000.0,
    "YM": 38000.0, "RTY": 2000.0,
    "CL": 75.0, "NG": 2.8,
    "GC": 2000.0, "SI": 24.0, "HG": 6.3,
}



#: What a symbol and a timeframe are allowed to look like, at the API boundary.
#:
#: These are PATH COMPONENTS before they are anything else.
#: src/data/csv_provider.py builds `self.data_dir / f"{symbol}_{timeframe}.csv"`,
#: and Path's `/` operator does not stop a segment climbing out of its parent --
#: "../../.." joined to a directory resolves above it, exactly as on a command
#: line. Reaching an arbitrary file still needs one whose name ends
#: `_{timeframe}.csv`, so this was never a read-anything hole, but "constrained
#: by a filename suffix" is not a security boundary and should not be relied on
#: as one.
#:
#: Alphanumeric only, which every real value already is: the configured
#: contracts are ES, NQ, MES, CL, HG, AAPL, BTC and the rest, and timeframes
#: are 1m, 5m, 15m, 1h. Nothing legitimate needs a dot or a slash, so nothing
#: legitimate is refused.
SYMBOL_PATTERN = r"^[A-Za-z0-9]{1,16}$"
TIMEFRAME_PATTERN = r"^[A-Za-z0-9]{1,8}$"


@lru_cache
def get_config() -> dict:
    return load_config()


def get_contract_spec(symbol: str) -> dict:
    """Contract economics for a symbol.

    settings.yaml wins over the hardcoded defaults above -- the same merge
    /api/contracts already performed. Previously this consulted only
    CONTRACT_SPECS, so a symbol defined in config was still priced with the
    ES fallback (0.25 tick / $50 per point). That silently produced plausible
    but wrong P&L for anything that isn't an E-mini, which matters now that
    equities and metals ship in data/sample/.
    """
    contracts = get_config().get("contracts", {}) or {}
    merged = {**CONTRACT_SPECS, **contracts}
    spec = merged.get(symbol)
    if spec is None:
        return dict(tick_size=0.25, tick_value=12.50, point_value=50.0)
    # settings.yaml entries carry extra keys (name, exchange, margins); the
    # engine only wants the three economics fields.
    return dict(
        tick_size=spec["tick_size"],
        tick_value=spec["tick_value"],
        point_value=spec["point_value"],
    )
