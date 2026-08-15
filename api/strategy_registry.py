"""
Strategy metadata + construction, centralized here so the frontend can render
a generic parameter form instead of hardcoding one branch per strategy (which
is what ui/app.py's sidebar does today). The actual strategy classes are
unchanged, imported from src/strategies/ as-is.
"""

from src.strategies import (
    MACrossoverStrategy, RSIMeanReversionStrategy, BreakoutStrategy,
    RSIDivergenceStrategy, RegimeAdaptiveStrategy,
)

STRATEGIES = [
    {
        "id": "ma_crossover", "label": "MA Crossover",
        "params": [
            {"name": "fast", "label": "Fast EMA", "type": "int", "min": 3, "max": 50, "step": 1, "default": 9},
            {"name": "slow", "label": "Slow EMA", "type": "int", "min": 10, "max": 200, "step": 1, "default": 21},
        ],
    },
    {
        "id": "rsi_mean_reversion", "label": "RSI Mean Reversion",
        "params": [
            {"name": "period", "label": "RSI Period", "type": "int", "min": 5, "max": 30, "step": 1, "default": 14},
            {"name": "oversold", "label": "Oversold", "type": "int", "min": 10, "max": 40, "step": 1, "default": 30},
            {"name": "overbought", "label": "Overbought", "type": "int", "min": 60, "max": 90, "step": 1, "default": 70},
        ],
    },
    {
        "id": "breakout", "label": "Breakout (Donchian)",
        "params": [
            {"name": "lookback", "label": "Channel Lookback", "type": "int", "min": 5, "max": 60, "step": 1, "default": 20},
            {"name": "atr_mult", "label": "ATR Stop Multiplier", "type": "float", "min": 0.5, "max": 5.0, "step": 0.1, "default": 2.0},
        ],
    },
    {
        "id": "rsi_divergence", "label": "RSI Divergence",
        "params": [
            {"name": "rsi_overbought", "label": "RSI Overbought", "type": "int", "min": 80, "max": 99, "step": 1, "default": 94},
            {"name": "rsi_oversold", "label": "RSI Oversold", "type": "int", "min": 1, "max": 20, "step": 1, "default": 2},
            {"name": "swing_lookback", "label": "Swing Lookback (bars)", "type": "int", "min": 2, "max": 20, "step": 1, "default": 5},
        ],
    },
    {
        "id": "regime_adaptive", "label": "Regime Adaptive (Auto)",
        "params": [],
    },
]

_IDS = {s["id"] for s in STRATEGIES}


def _with_defaults(strategy_id: str, params: dict) -> dict:
    """
    Fill in any parameter the caller left out, from the registry's own default.

    Without this, a request carrying `params: {}` -- which is a perfectly
    reasonable way to say "just use the defaults", and what the API's own
    documented default for that field is -- raised KeyError inside the
    constructor call below and surfaced as a bare 500 Internal Server Error.
    The registry already publishes a default for every parameter, so there is
    no reason for the caller to have to repeat them.
    """
    spec = next((s for s in STRATEGIES if s["id"] == strategy_id), None)
    if spec is None:
        return dict(params)
    merged = {p["name"]: p["default"] for p in spec["params"]}
    merged.update({k: v for k, v in (params or {}).items() if v is not None})
    return merged


def build_strategy(strategy_id: str, params: dict):
    params = _with_defaults(strategy_id, params)
    if strategy_id == "ma_crossover":
        return MACrossoverStrategy(fast=int(params["fast"]), slow=int(params["slow"]))
    if strategy_id == "rsi_mean_reversion":
        return RSIMeanReversionStrategy(
            period=int(params["period"]), oversold=float(params["oversold"]),
            overbought=float(params["overbought"]),
        )
    if strategy_id == "breakout":
        return BreakoutStrategy(lookback=int(params["lookback"]), atr_mult=float(params["atr_mult"]))
    if strategy_id == "rsi_divergence":
        return RSIDivergenceStrategy(
            rsi_overbought=float(params["rsi_overbought"]),
            rsi_oversold=float(params["rsi_oversold"]),
            swing_lookback=int(params["swing_lookback"]),
        )
    if strategy_id == "regime_adaptive":
        return RegimeAdaptiveStrategy()
    raise ValueError(f"Unknown strategy id: {strategy_id!r}. Valid: {sorted(_IDS)}")


def strategy_label(strategy_id: str) -> str:
    for s in STRATEGIES:
        if s["id"] == strategy_id:
            return s["label"]
    return strategy_id
