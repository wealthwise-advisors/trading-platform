"""Load and merge settings.yaml with optional credentials.yaml."""

from pathlib import Path
import yaml


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
