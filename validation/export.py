"""Expert Chart Validation Framework -- export formats (Task 8,
requirement 6): CSV, Excel, JSON, Markdown. All four operate on the SAME
underlying query (charts + analyses + reviews, left-joined so unreviewed
analyses still export with empty review columns) so the four formats never
drift out of sync with each other.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import sqlite3

import pandas as pd

from validation.db import connect, fetch_all
from validation import metrics as metrics_mod

EXPORTS_DIR = Path(__file__).parent / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)

_JOIN_QUERY = """
SELECT
    c.chart_id, c.market, c.timeframe, c.bar_count, c.data_source,
    a.analysis_id, a.degree, a.n_swings, a.bias, a.cycle_position,
    a.impulse_quality, a.corrective_quality, a.triangle_quality, a.diagonal_quality,
    a.confidence, a.primary_count_json, a.alternate_counts_json,
    a.recursive_verification_json, a.rule_violations_json, a.warnings_json,
    r.review_id, r.reviewer, r.verdict, r.false_positive, r.false_negative,
    r.mis_numbering, r.wrong_degree, r.missed_triangle, r.missed_diagonal,
    r.wrong_correction, r.notes as review_notes
FROM charts c
JOIN analyses a ON a.chart_id = c.chart_id
LEFT JOIN reviews r ON r.analysis_id = a.analysis_id
ORDER BY c.market, c.timeframe, c.chart_id
"""


def _rows_dataframe(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.DataFrame(fetch_all(conn, _JOIN_QUERY))


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    """Plain markdown table renderer -- avoids adding a `tabulate`
    dependency (not currently installed in this project) just for one
    export helper."""
    df = df.reset_index()
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    body = "\n".join("| " + " | ".join(str(v) for v in row) + " |" for row in df.values)
    return "\n".join([header, sep, body])


def export_csv(conn: sqlite3.Connection, path: Path = None) -> Path:
    path = path or EXPORTS_DIR / "validation_export.csv"
    _rows_dataframe(conn).to_csv(path, index=False)
    return path


def export_excel(conn: sqlite3.Connection, path: Path = None) -> Path:
    path = path or EXPORTS_DIR / "validation_export.xlsx"
    df = _rows_dataframe(conn)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="analyses", index=False)
        summary = metrics_mod.full_summary(conn)
        flat_rows = []
        def _flatten(prefix, obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    _flatten(f"{prefix}.{k}" if prefix else k, v)
            else:
                flat_rows.append({"metric": prefix, "value": obj})
        _flatten("", summary)
        pd.DataFrame(flat_rows).to_excel(writer, sheet_name="summary_metrics", index=False)
    return path


def export_json(conn: sqlite3.Connection, path: Path = None) -> Path:
    path = path or EXPORTS_DIR / "validation_export.json"
    rows = fetch_all(conn, _JOIN_QUERY)
    payload = {"summary_metrics": metrics_mod.full_summary(conn), "analyses": rows}
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


def export_markdown(conn: sqlite3.Connection, path: Path = None) -> Path:
    path = path or EXPORTS_DIR / "validation_report.md"
    summary = metrics_mod.full_summary(conn)
    df = _rows_dataframe(conn)

    lines = ["# Elliott Wave Expert Chart Validation Report", ""]
    lines.append(f"**Analyses in database:** {len(df)}  ")
    lines.append(f"**Reviews recorded:** {summary['review_count']}  ")
    lines.append("")

    lines.append("## Coverage by market / timeframe")
    lines.append("")
    cov = df.groupby(["market", "timeframe"]).size().unstack(fill_value=0)
    lines.append(_df_to_markdown_table(cov))
    lines.append("")

    lines.append("## Hard-rule compliance")
    lines.append("")
    hrc = summary["hard_rule_compliance"]
    lines.append(f"- {hrc['analyses_with_violations']} of {hrc['total_analyses']} analyses show a rule "
                 f"violation on independent re-audit -- compliance rate **{hrc['hard_rule_compliance_rate']:.1%}**")
    lines.append("")

    lines.append("## Quality score distribution (direct engine output, no review needed)")
    lines.append("")
    lines.append("| Structure | n | min | median | mean | max |")
    lines.append("|---|---|---|---|---|---|")
    for name, stats in summary["quality_score_distribution"].items():
        if stats:
            lines.append(f"| {name} | {stats['n']} | {stats['min']} | {stats['median']} | {stats['mean']} | {stats['max']} |")
    lines.append("")

    if summary["review_count"] == 0:
        lines.append("## Review-derived metrics")
        lines.append("")
        lines.append("_No expert reviews recorded yet -- structure accuracy, wave-numbering "
                     "accuracy, confidence calibration, precision/recall/F1, and reviewer "
                     "agreement all require populating the `reviews` table via the review "
                     "gallery workflow (see README.md). They are computed live once reviews "
                     "exist -- not fabricated placeholders._")
    else:
        lines.append("## Structure accuracy")
        lines.append("")
        lines.append(f"```json\n{json.dumps(summary['structure_accuracy'], indent=2)}\n```")
        lines.append("")
        lines.append("## Precision / Recall / F1 by miss-type")
        lines.append("")
        lines.append("| Miss type | Precision | Recall | F1 |")
        lines.append("|---|---|---|---|")
        for flag, m in summary["precision_recall_f1"].items():
            if m:
                lines.append(f"| {flag} | {m['precision']} | {m['recall']} | {m['f1']} |")

    path.write_text("\n".join(lines))
    return path


def export_all(conn: sqlite3.Connection) -> dict:
    return {
        "csv": str(export_csv(conn)),
        "excel": str(export_excel(conn)),
        "json": str(export_json(conn)),
        "markdown": str(export_markdown(conn)),
    }


if __name__ == "__main__":
    with connect() as conn:
        paths = export_all(conn)
    for fmt, path in paths.items():
        print(f"{fmt}: {path}")
