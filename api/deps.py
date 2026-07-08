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
}
BASE_PRICES = {"ES": 4500.0, "NQ": 15000.0, "MES": 4500.0, "CL": 75.0}


@lru_cache
def get_config() -> dict:
    return load_config()


def get_contract_spec(symbol: str) -> dict:
    return CONTRACT_SPECS.get(symbol, dict(tick_size=0.25, tick_value=12.50, point_value=50.0))
