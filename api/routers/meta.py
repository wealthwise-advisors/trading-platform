"""Health check and reference/meta endpoints."""

import os
from functools import lru_cache

from fastapi import APIRouter, Depends

from api.auth import require_user

from api.deps import BASE_PRICES, CONTRACT_SPECS, get_config
from src.data.rithmic_provider import EXCHANGE_MAP
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

    # The commit this container was started for, supplied by the deploy as an
    # environment variable. This is what lets a deploy prove the container
    # answering is the one it just started: "version" is 1.0.0 on every build
    # and so cannot tell a fresh container from a stale one holding the same
    # port. That exact ambiguity let a deploy report success while the previous
    # stack was still serving. "unknown" outside a deploy.
    return {
        "version": pkg_version,
        "api": "autotrader",
        "commit": os.getenv("AUTOTRADER_COMMIT", "unknown"),
    }


@router.get("/strategies", dependencies=[Depends(require_user)])
def list_strategies():
    return STRATEGIES


@router.get("/contracts", dependencies=[Depends(require_user)])
def list_contracts():
    cfg = get_config()
    contracts = cfg.get("contracts", {})
    # Fall back to the hardcoded defaults for symbols not in settings.yaml,
    # matching ui/app.py's CONTRACT_SPECS behavior.
    merged = {**CONTRACT_SPECS, **contracts}
    return merged


def _csv_files_by_symbol(data_dir) -> dict[str, list]:
    """Group the CSVs in a directory by the symbol each one serves.

    Mirrors ExternalCSVProvider._find_file()'s resolution patterns --
    {SYM}_FULL.csv, {SYM}_FULL_{year}.csv, {SYM}_{year}.csv, FULL_{SYM}.csv --
    so the symbols advertised here cannot drift from the ones the loader can
    actually resolve.
    """
    import re

    out: dict[str, list] = {}
    for p in sorted(data_dir.glob("*.csv")):
        for pattern in (
            r"^([A-Z0-9]+)_FULL(?:_\d{4})?$",
            r"^FULL_([A-Z0-9]+)(?:_\d{4})?$",
            r"^([A-Z0-9]+)_(\d{4})$",
        ):
            m = re.match(pattern, p.stem)
            if m:
                out.setdefault(m.group(1), []).append(p)
                break
    return out


@lru_cache(maxsize=256)
def _file_span(path_str: str, mtime: float, size: int) -> tuple[str, str] | None:
    """(first, last) timestamp of a CSV, without reading the whole file.

    mtime/size are part of the cache key only -- they make the entry
    self-invalidating when the file changes. The tail is read by seeking to
    the end rather than scanning, because a real archive file can be hundreds
    of megabytes and this runs on every /symbols request.
    """
    try:
        with open(path_str, "rb") as f:
            f.readline()                      # header
            first_line = f.readline().decode("utf-8", "ignore")
            if not first_line.strip():
                return None
            f.seek(0, 2)
            end = f.tell()
            f.seek(max(0, end - 8192))
            tail = [ln for ln in f.read().decode("utf-8", "ignore").splitlines() if ln.strip()]
            if not tail:
                return None
        return first_line.split(",")[0].strip(), tail[-1].split(",")[0].strip()
    except OSError:
        return None


def csv_coverage(data_dir, symbol: str) -> list[dict]:
    """Date windows a symbol actually has data for, oldest first.

    Returned as separate segments rather than one min/max span because
    coverage is often not continuous -- the bundled ES sample is five
    disjoint windows (2008, then 2022 through 2025), so a single
    "2008-01-02 to 2025-01-07" range would invite picking 2015 and getting
    nothing back.
    """
    import os

    spans = []
    for p in _csv_files_by_symbol(data_dir).get(symbol, []):
        try:
            st = os.stat(p)
        except OSError:
            continue
        span = _file_span(str(p), st.st_mtime, st.st_size)
        if span:
            spans.append({"start": span[0][:10], "end": span[1][:10]})
    return sorted(spans, key=lambda s: s["start"])


@router.get("/symbols", dependencies=[Depends(require_user)])
def list_symbols(data_source: str = "synthetic"):
    """Symbols selectable for a given data source.

    The frontend used to hardcode ["ES","NQ","MES","CL","HG"], so the
    instruments committed under data/sample/ -- gold, bitcoin and nine
    equities -- could not be chosen at all, and the four E-minis that have no
    bundled data were offered regardless.

    For external_csv the list is derived from the files actually present,
    using ExternalCSVProvider's own resolution patterns so the two cannot
    disagree. Every other source is generated or streams on demand, so the
    configured contracts are the meaningful list.

    `has_spec` reports whether the symbol has real contract economics.
    Anything false falls back to the E-mini default and its P&L should not
    be trusted -- see api/deps.get_contract_spec.
    """
    cfg = get_config()
    specs = {**CONTRACT_SPECS, **(cfg.get("contracts", {}) or {})}

    def entry(sym: str) -> dict:
        spec = specs.get(sym)
        return {
            "symbol": sym,
            "name": (spec or {}).get("name", sym) if isinstance(spec, dict) else sym,
            "has_spec": spec is not None,
            # Which venue the contract trades on. Read from the download
            # provider's own map rather than a second copy here, so the picker
            # and a Rithmic request can never disagree about where ES lives.
            "exchange": EXCHANGE_MAP.get(sym.upper()),
        }

    if data_source == "external_csv":
        from pathlib import Path

        try:
            from src.data.external_csv_provider import ExternalCSVProvider
            data_dir = Path(ExternalCSVProvider().data_dir)
        except Exception:
            return []

        out = []
        for sym in _csv_files_by_symbol(data_dir):
            e = entry(sym)
            # Coverage travels with the symbol so the UI can default the date
            # pickers into a window that exists, instead of today's date --
            # which is what produced "No bars found for ES between
            # 2026-08-07 ... and ...".
            e["coverage"] = csv_coverage(data_dir, sym)
            out.append(e)
        return sorted(out, key=lambda e: (not e["has_spec"], e["symbol"]))

    if data_source == "schwab":
        # Schwab serves a rolling window of intraday history, not an archive.
        # Reporting it as coverage lets the date pickers, the availability hint
        # and the disabled Run button all behave exactly as they do for CSV --
        # without which the only feedback was a failed request reading "check
        # the symbol, date range, and that your account has data access", which
        # named three possible causes and confirmed none of them.
        import datetime as _dt

        from src.data.schwab_provider import INTRADAY_LOOKBACK_DAYS

        today = _dt.date.today()
        window = [{
            "start": (today - _dt.timedelta(days=INTRADAY_LOOKBACK_DAYS)).isoformat(),
            "end": today.isoformat(),
        }]
        return [{**entry(s), "coverage": window} for s in specs]

    if data_source == "synthetic":
        # The generator only models a starting price for these; anything else
        # would be produced at the 4500 fallback, so a "NVDA" series would
        # trade around E-mini levels. Offer only what it can actually model.
        return [entry(s) for s in BASE_PRICES]

    # schwab / rithmic stream whatever the venue supports; the configured
    # contracts are the set we can price.
    return [entry(s) for s in specs]


@router.get("/data-sources", dependencies=[Depends(require_user)])
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
