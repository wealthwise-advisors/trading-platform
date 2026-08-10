"""Load and merge settings.yaml with optional credentials.yaml."""

import os
from pathlib import Path
import yaml


def resolve_config_dir() -> Path:
    """Find the config/ directory across every way this project actually
    runs. Task 10.1 verification found `src/data/schwab_provider.py` and
    `external_csv_provider.py` each hardcoded `Path(__file__).parent.parent.parent
    / "config"` -- correct ONLY for an editable install (__file__ still
    points at the repo checkout), silently wrong for a real `pip install .`
    or the built Docker image, both of which install into site-packages,
    where climbing 3 parents lands outside any config/ directory at all.

    Checked in order, first match wins:
      1. AUTOTRADER_CONFIG_DIR env var, if set -- explicit override, always wins.
      2. <cwd>/config -- correct for `uvicorn api.main:app` run from the repo
         root (the documented dev workflow) AND for the Docker image (WORKDIR
         /app, config/ bind-mounted at /app/config, cwd is /app at startup).
      3. The old package-relative guess -- kept as a last-resort fallback so
         nothing that worked via editable install regresses.
    Raises FileNotFoundError with a clear message if none exist, rather than
    silently resolving to a directory that doesn't contain what's needed --
    the caller decides what to do with a real error, not a confusing one
    two-thirds of the way through a YAML parse.
    """
    candidates = []
    env_dir = os.environ.get("AUTOTRADER_CONFIG_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.append(Path.cwd() / "config")
    candidates.append(Path(__file__).parent.parent / "config")

    for c in candidates:
        if c.is_dir():
            return c

    raise FileNotFoundError(
        "Could not locate the config/ directory. Checked: "
        + ", ".join(str(c) for c in candidates)
        + ". Set AUTOTRADER_CONFIG_DIR, or run from the repo root."
    )


def load_config(
    settings_path: str = "config/settings.yaml",
    credentials_path: str = "config/credentials.yaml",
) -> dict:
    base = Path(settings_path)
    creds = Path(credentials_path)

    with base.open() as f:
        config = yaml.safe_load(f)

    if creds.exists():
        with creds.open() as f:
            cred_data = yaml.safe_load(f) or {}
        # Merge credentials into rithmic section
        if "rithmic" in cred_data:
            config.setdefault("rithmic", {}).update(cred_data["rithmic"])

    return config


def get_contract_spec(config: dict, symbol: str) -> dict:
    contracts = config.get("contracts", {})
    if symbol not in contracts:
        raise KeyError(f"No contract spec for '{symbol}'. Add it to config/settings.yaml.")
    return contracts[symbol]
