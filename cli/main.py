"""``elliott`` production CLI (Task 10, v1.0.0 release).

Thin wrapper around the existing, unmodified engine/benchmark/validation/
config code -- this module contains NO Elliott Wave logic of its own, only
argument parsing, I/O, and calls into ``src.analysis``, ``benchmark``,
``validation``, and ``src.config``. Every subcommand is a real, working
call into production code, not a stub.

Commands: analyze, benchmark, validate, export, version, config
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_ohlc_csv(path: Path):
    import pandas as pd

    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"error: {path} is missing required column(s): {sorted(missing)}")
    return df


# --------------------------------------------------------------------------- #
# elliott analyze
# --------------------------------------------------------------------------- #
def cmd_analyze(args: argparse.Namespace) -> int:
    from src.analysis.wave_analysis import analyze_degrees

    path = Path(args.input)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1

    df = _load_ohlc_csv(path)
    degrees = analyze_degrees(df)

    result = {}
    for name, a in degrees.items():
        result[name] = {
            "degree": a.degree,
            "trend": a.trend,
            "n_swings": a.n_swings,
            "impulse_valid": a.impulse.valid if a.impulse else None,
            "impulse_direction": a.impulse.direction if a.impulse else None,
            "correction_type": a.correction.type.value if a.correction else None,
            "bias": a.bias,
            "invalidation": a.invalidation,
            "cycle_position": a.cycle_position,
            "n_wave_labels": len(a.wave_sequence),
            "n_alternates": len(a.alternates),
            "warnings": list(a.warnings),
        }

    if not args.quiet:
        print(f"Elliott Wave analysis: {path} ({len(df)} bars)\n")
        for name, r in result.items():
            print(f"  [{name}]  trend={r['trend']}  swings={r['n_swings']}  bias={r['bias']}")
            if r["impulse_valid"] is not None:
                print(f"      impulse: valid={r['impulse_valid']} direction={r['impulse_direction']}")
            if r["correction_type"]:
                print(f"      correction: {r['correction_type']}")
            print(f"      wave labels={r['n_wave_labels']}  alternates={r['n_alternates']}  warnings={r['warnings']}")

    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2, default=str))
        if not args.quiet:
            print(f"\nJSON written to {args.json}")
    return 0


# --------------------------------------------------------------------------- #
# elliott validate
# --------------------------------------------------------------------------- #
def cmd_validate(args: argparse.Namespace) -> int:
    import subprocess

    target = args.path or "tests/elliott"
    print(f"Running Elliott Wave regression suite: {target}")
    proc = subprocess.run([sys.executable, "-m", "pytest", target, "-q"])
    return proc.returncode


# --------------------------------------------------------------------------- #
# elliott benchmark
# --------------------------------------------------------------------------- #
def cmd_benchmark(args: argparse.Namespace) -> int:
    from benchmark.db import connect
    from benchmark import metrics as metrics_mod

    if not args.report_only:
        from benchmark import populate_all
        populate_all.main()

    with connect() as conn:
        summary = metrics_mod.full_summary(conn)

    a = summary["agreement"]
    rr = summary["regime_robustness"]
    repro = summary["reproducibility"]
    print("\n=== Benchmark summary ===")
    print(f"synthetic archetype agreement: {a['primary_agreement_pct']:.1%}  "
         f"(95% CI [{a['primary_agreement_ci_95']['lower']:.1%}, {a['primary_agreement_ci_95']['upper']:.1%}], n={a['n']})")
    print(f"real-market robustness: {rr['resolved_structure_pct']:.1%} resolved, "
         f"{rr['zero_hard_rule_warnings_pct']:.1%} zero hard-rule warnings (n={rr['n']})")
    print(f"reproducibility: {repro['deterministic_pct']:.1%} deterministic over {repro['n_checked']} cases x {repro['runs_per_check']} runs")

    if args.json:
        Path(args.json).write_text(json.dumps(summary, indent=2, default=str))
        print(f"\nJSON written to {args.json}")
    return 0


# --------------------------------------------------------------------------- #
# elliott export
# --------------------------------------------------------------------------- #
def cmd_export(args: argparse.Namespace) -> int:
    from src.analysis.wave_analysis import analyze_degrees

    path = Path(args.input)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1

    df = _load_ohlc_csv(path)
    degrees = analyze_degrees(df)
    out_path = Path(args.output) if args.output else path.with_suffix(f".analysis.{args.format}")

    if args.format == "json":
        payload = {
            name: {
                "degree": a.degree, "trend": a.trend, "n_swings": a.n_swings,
                "bias": a.bias, "invalidation": a.invalidation,
                "wave_sequence": [
                    {"bar": w.index, "price": round(w.price, 4), "wave": w.wave, "sub": w.sub, "direction": w.direction}
                    for w in a.wave_sequence
                ],
                "warnings": list(a.warnings),
            }
            for name, a in degrees.items()
        }
        out_path.write_text(json.dumps(payload, indent=2, default=str))
    elif args.format == "csv":
        import csv as csv_mod
        rows = []
        for name, a in degrees.items():
            for w in a.wave_sequence:
                rows.append({"degree": name, "bar": w.index, "price": round(w.price, 4), "wave": w.wave, "sub": w.sub, "direction": w.direction})
        with out_path.open("w", newline="") as f:
            writer = csv_mod.DictWriter(f, fieldnames=["degree", "bar", "price", "wave", "sub", "direction"])
            writer.writeheader()
            writer.writerows(rows)
    else:
        print(f"error: unsupported format {args.format!r}", file=sys.stderr)
        return 1

    print(f"exported {out_path}")
    return 0


# --------------------------------------------------------------------------- #
# elliott version
# --------------------------------------------------------------------------- #
def cmd_version(args: argparse.Namespace) -> int:
    import platform
    from importlib.metadata import version, PackageNotFoundError

    try:
        pkg_version = version("autotrader")
    except PackageNotFoundError:
        pkg_version = "1.0.0 (not installed as a package -- running from source)"

    print(f"autotrader (elliott CLI)  v{pkg_version}")
    print(f"python {platform.python_version()}  ({platform.system()} {platform.release()})")

    if args.verbose:
        for dep in ("pandas", "numpy", "fastapi", "pydantic", "plotly", "pandas_ta"):
            try:
                print(f"  {dep}: {version(dep)}")
            except PackageNotFoundError:
                print(f"  {dep}: NOT INSTALLED")
    return 0


# --------------------------------------------------------------------------- #
# elliott config
# --------------------------------------------------------------------------- #
_SECRET_KEYS = {"app_key", "app_secret", "credentials_path", "token", "tokens_file", "secret", "password", "key"}


def _redact(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if any(s in k.lower() for s in _SECRET_KEYS):
                out[k] = "***SET***" if v else "(not set)"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    return obj


def cmd_config(args: argparse.Namespace) -> int:
    from src.config import load_config

    settings_path = Path(args.settings)
    if not settings_path.exists():
        print(f"error: {settings_path} not found", file=sys.stderr)
        return 1

    try:
        config = load_config(str(settings_path), args.credentials)
    except Exception as exc:
        print(f"error: failed to load config: {exc}", file=sys.stderr)
        return 1

    print(f"Config loaded from: {settings_path}")
    print(f"Credentials file:   {args.credentials}  ({'found' if Path(args.credentials).exists() else 'not found -- ok, optional'})")
    print()

    required_sections = ["app", "backtesting", "contracts"]
    ok = True
    for section in required_sections:
        present = section in config
        ok = ok and present
        print(f"  [{'OK ' if present else 'MISSING'}] section '{section}'")

    if not ok:
        print("\nvalidation FAILED: settings.yaml is missing required section(s) above")
        return 1

    if args.show:
        print("\nEffective config (secrets redacted):")
        print(json.dumps(_redact(config), indent=2, default=str))

    print(f"\nvalidation OK -- {len(config.get('contracts', {}))} contract spec(s) loaded")
    return 0


# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="elliott", description="AutoTrader / Elliott Wave engine production CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("analyze", help="Run the Elliott Wave engine on an OHLC CSV file")
    p.add_argument("input", help="Path to an OHLC CSV (columns: open,high,low,close[,volume])")
    p.add_argument("--json", metavar="FILE", help="Write the full analysis result as JSON to FILE")
    p.add_argument("-q", "--quiet", action="store_true", help="Suppress the printed summary")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("validate", help="Run the Elliott Wave regression/validation test suite")
    p.add_argument("path", nargs="?", default=None, help="Test path (default: tests/elliott)")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("benchmark", help="Run (or report on) the independent industry benchmark")
    p.add_argument("--report-only", action="store_true", help="Skip re-populating; just summarize the existing benchmark.db")
    p.add_argument("--json", metavar="FILE", help="Write the full metrics summary as JSON to FILE")
    p.set_defaults(func=cmd_benchmark)

    p = sub.add_parser("export", help="Analyze a CSV and export the wave sequence")
    p.add_argument("input", help="Path to an OHLC CSV")
    p.add_argument("--format", choices=["json", "csv"], default="json")
    p.add_argument("--output", metavar="FILE", help="Output path (default: <input>.analysis.<format>)")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("version", help="Show version and environment info")
    p.add_argument("-v", "--verbose", action="store_true", help="Also show key dependency versions")
    p.set_defaults(func=cmd_version)

    p = sub.add_parser("config", help="Show and validate the loaded configuration")
    p.add_argument("--settings", default="config/settings.yaml")
    p.add_argument("--credentials", default="config/credentials.yaml")
    p.add_argument("--show", action="store_true", help="Print the effective config (secrets redacted)")
    p.set_defaults(func=cmd_config)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
