"""Health check and reference/meta endpoints."""

from fastapi import APIRouter

from api.deps import CONTRACT_SPECS, get_config
from api.strategy_registry import STRATEGIES

router = APIRouter(tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/version")
def get_version():
    """Task 10 API audit: no version endpoint existed. Reports the
    installed package version (falls back honestly to 'unknown' rather
    than a hardcoded guess if the package metadata isn't available, e.g.
    running from source without `pip install -e .`)."""
    from importlib.metadata import version, PackageNotFoundError

    try:
        pkg_version = version("autotrader")
    except PackageNotFoundError:
        pkg_version = "unknown (not installed as a package)"
    return {"version": pkg_version, "api": "autotrader"}


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
        SchwabDataProvider()
        availability["schwab"] = True
    except Exception:
        # Task 10 API audit: this previously never actually tried to
        # construct the provider, so it unconditionally reported True
        # regardless of whether config/credentials.yaml had a schwab
        # section at all -- the frontend's "Live Data (Schwab)" option
        # showed as available even with no credentials configured.
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
