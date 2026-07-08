"""Health check and reference/meta endpoints."""

from fastapi import APIRouter

from api.deps import CONTRACT_SPECS, get_config
from api.strategy_registry import STRATEGIES

router = APIRouter(tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/strategies")
def list_strategies():
    return STRATEGIES


@router.get("/contracts")
def list_contracts():
    cfg = get_config()
    contracts = cfg.get("contracts", {})
    # Fall back to the hardcoded defaults for symbols not in settings.yaml,
    # matching ui/app.py's CONTRACT_SPECS behavior.
    merged = {**CONTRACT_SPECS, **contracts}
    return merged


@router.get("/data-sources")
def list_data_sources():
    availability = {"synthetic": True}
    try:
        from src.data.external_csv_provider import ExternalCSVProvider
        try:
            ExternalCSVProvider()
            availability["external_csv"] = True
        except Exception:
            availability["external_csv"] = False
    except Exception:
        availability["external_csv"] = False

    try:
        from src.data.schwab_provider import SchwabDataProvider
        availability["schwab"] = True
    except Exception:
        availability["schwab"] = False

    try:
        import src.data.rithmic_provider  # noqa: F401
        availability["rithmic"] = True
    except ImportError:
        availability["rithmic"] = False

    return [
        {"id": "synthetic", "label": "Synthetic Data", "available": availability["synthetic"]},
        {"id": "external_csv", "label": "My Historical Data (CSV)", "available": availability["external_csv"]},
        {"id": "schwab", "label": "Live Data (Schwab)", "available": availability["schwab"]},
        {"id": "rithmic", "label": "Real Data (Rithmic)", "available": availability["rithmic"]},
    ]
