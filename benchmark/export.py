"""Independent Industry Benchmark -- export (JSON + Markdown report)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import sqlite3

from benchmark.db import connect, fetch_all
from benchmark import metrics as metrics_mod

EXPORTS_DIR = Path(__file__).parent / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)


def export_json(conn: sqlite3.Connection, path: Path = None) -> Path:
    path = path or EXPORTS_DIR / "benchmark_export.json"
    rows = fetch_all(
        conn,
        "SELECT c.*, r.engine_structure_type, r.confidence, r.engine_primary_count_json, "
        "cmp.primary_agreement, cmp.recommendation, cmp.recommendation_basis, cmp.rule_differences_json "
        "FROM benchmark_charts c JOIN benchmark_runs r ON r.chart_id = c.chart_id "
        "JOIN benchmark_comparisons cmp ON cmp.run_id = r.run_id",
    )
    sources = fetch_all(conn, "SELECT * FROM reference_sources")
    payload = {"reference_sources": sources, "summary_metrics": metrics_mod.full_summary(conn), "cases": rows}
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


def export_markdown(conn: sqlite3.Connection, path: Path = None) -> Path:
    path = path or EXPORTS_DIR / "benchmark_report.md"
    summary = metrics_mod.full_summary(conn)
    sources = fetch_all(conn, "SELECT * FROM reference_sources ORDER BY category, name")

    lines = ["# Elliott Wave Independent Industry Benchmark Report", ""]

    ds = summary["dataset_summary"]
    lines.append("## Dataset summary")
    lines.append("")
    lines.append(f"- Total benchmark cases: **{ds['total_cases']}**")
    lines.append(f"- By category: {ds['by_category']}")
    lines.append("- Real-market cases by symbol/timeframe: " +
                ", ".join(f"{r['symbol']}/{r['timeframe']}={r['n']}" for r in ds["by_symbol_timeframe"]))
    lines.append("- Real-market cases by regime (trend, volatility): " +
                ", ".join(f"({r['regime_trend']},{r['regime_volatility']})={r['n']}" for r in ds["by_regime"]))
    lines.append("")

    lines.append("## Reference source access status")
    lines.append("")
    lines.append("| Source | Category | Status | Cases | Notes |")
    lines.append("|---|---|---|---|---|")
    for s in sources:
        n_cases = next((r["n"] for r in ds["by_source"] if r["name"] == s["name"]), 0)
        lines.append(f"| {s['name']} | {s['category']} | **{s['access_status']}** | {n_cases} | {s['access_notes'][:120]}... |")
    lines.append("")

    a = summary["agreement"]
    lines.append(f"## Agreement statistics ({a['n']} synthetic archetype benchmarks -- see 'Dataset summary' for the "
                f"369 additional real-market robustness cases, which have no independent reference count and are "
                f"reported separately below, not blended into this accuracy number)")
    lines.append("")
    lines.append(f"- Primary agreement rate: **{a['primary_agreement_pct']:.1%}** (95% Wilson CI: "
                f"{a['primary_agreement_ci_95']['lower']:.1%}-{a['primary_agreement_ci_95']['upper']:.1%})")
    lines.append(f"- By recommendation: {a['by_recommendation']}")
    lines.append(f"- By agreement level: {a['by_agreement_level']}")
    k = summary["cohens_kappa"]
    lines.append(f"- Cohen's Kappa: **{k['kappa']}** (observed={k['observed_agreement']}, chance={k['chance_agreement']}) -- {k['note']}")
    lines.append("")

    repro = summary["reproducibility"]
    lines.append("## Reproducibility (requirement 6)")
    lines.append("")
    lines.append(f"- {repro['n_checked']} cases checked, {repro['runs_per_check']} independent runs each: "
                f"**{repro['deterministic_pct']:.0%} fully deterministic** (byte-identical output every run)")
    lines.append(f"- By category: {repro['by_category']}")
    lines.append(f"- {repro['note']}")
    lines.append("")

    rr = summary["regime_robustness"]
    lines.append("## Real-market regime robustness (369 cases, NOT an accuracy comparison -- see note)")
    lines.append("")
    lines.append(f"- Resolved a top-level structure: **{rr['resolved_structure_pct']:.1%}** of real-market windows")
    lines.append(f"- Zero hard-rule warnings: **{rr['zero_hard_rule_warnings_pct']:.1%}**")
    lines.append(f"- By trend regime: {rr['by_regime']['trend']}")
    lines.append(f"- By volatility regime: {rr['by_regime']['volatility']}")
    lines.append(f"- {rr['note']}")
    lines.append("")

    lines.append("## Precision / Recall / F1 by structure type")
    lines.append("")
    lines.append("| Type | TP | FP | FN | Precision | Recall | F1 |")
    lines.append("|---|---|---|---|---|---|---|")
    for label, m in summary["precision_recall_f1_per_class"].items():
        lines.append(f"| {label} | {m['tp']} | {m['fp']} | {m['fn']} | {m['precision']} | {m['recall']} | {m['f1']} |")
    lines.append("")

    lines.append("## Rule-level comparison (open-source TradingView Pine script)")
    lines.append("")
    for r in summary["rule_comparisons"]:
        lines.append(f"- **{r['rule_name']}** [{r['agreement']}]: engine -- {r['engine_rule']}")
        lines.append(f"  reference -- {r['reference_rule']}")
    lines.append("")

    path.write_text("\n".join(lines))
    return path


if __name__ == "__main__":
    with connect() as conn:
        j = export_json(conn)
        m = export_markdown(conn)
    print(f"json: {j}\nmarkdown: {m}")
