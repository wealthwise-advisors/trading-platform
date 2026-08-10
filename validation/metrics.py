"""Expert Chart Validation Framework -- summary metrics (Task 8,
requirement 5). All metrics here are computed FROM REVIEW DATA in the
`reviews` table -- until a human reviewer populates that table, the
accuracy/precision/recall/F1/agreement metrics correctly report as "no
reviews yet" rather than a fabricated number. Confidence-distribution and
quality-distribution metrics don't need review data (they're direct engine
output) and are available immediately.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from typing import Optional

from validation.db import connect, fetch_all


def review_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]


def structure_accuracy(conn: sqlite3.Connection) -> Optional[dict]:
    """Fraction of reviewed analyses marked Correct or Acceptable
    Alternate (the two verdicts that mean "the engine's structural read
    was usable"), overall and broken out by verdict."""
    rows = fetch_all(conn, "SELECT verdict, COUNT(*) as n FROM reviews GROUP BY verdict")
    total = sum(r["n"] for r in rows)
    if total == 0:
        return None
    by_verdict = {r["verdict"]: r["n"] for r in rows}
    correct_ish = by_verdict.get("Correct", 0) + by_verdict.get("Acceptable Alternate", 0)
    return {
        "total_reviewed": total,
        "by_verdict": by_verdict,
        "structure_accuracy": round(correct_ish / total, 4),
    }


def wave_numbering_accuracy(conn: sqlite3.Connection) -> Optional[dict]:
    """Among analyses whose STRUCTURE was judged correct (Correct or
    Acceptable Alternate), what fraction were NOT flagged mis_numbering?
    Isolates "got the shape right but numbered it wrong" specifically."""
    rows = fetch_all(
        conn,
        "SELECT mis_numbering FROM reviews WHERE verdict IN ('Correct', 'Acceptable Alternate')",
    )
    if not rows:
        return None
    correct_numbering = sum(1 for r in rows if not r["mis_numbering"])
    return {
        "structurally_correct_count": len(rows),
        "correctly_numbered_count": correct_numbering,
        "wave_numbering_accuracy": round(correct_numbering / len(rows), 4),
    }


def hard_rule_compliance(conn: sqlite3.Connection) -> dict:
    """Does NOT need review data -- rule_violations_json is a direct,
    independent engine-output re-audit (see pipeline.py) computed for
    EVERY analysis, reviewed or not."""
    rows = fetch_all(conn, "SELECT rule_violations_json FROM analyses")
    total = len(rows)
    violating = sum(1 for r in rows if r["rule_violations_json"] != "[]")
    return {
        "total_analyses": total,
        "analyses_with_violations": violating,
        "hard_rule_compliance_rate": round(1 - violating / total, 4) if total else None,
    }


def confidence_calibration(conn: sqlite3.Connection) -> Optional[dict]:
    """Is the engine's own confidence score MEANINGFUL -- do high-
    confidence analyses actually get marked Correct more often than
    low-confidence ones? Needs review data; buckets confidence into
    quartile-ish bands and reports the Correct-or-Acceptable rate in each."""
    rows = fetch_all(
        conn,
        "SELECT a.confidence as confidence, r.verdict as verdict "
        "FROM reviews r JOIN analyses a ON r.analysis_id = a.analysis_id "
        "WHERE a.confidence IS NOT NULL",
    )
    if not rows:
        return None
    bands = {"low (0.0-0.4)": [], "medium (0.4-0.6)": [], "high (0.6-0.8)": [], "very_high (0.8-1.0)": []}
    for r in rows:
        c = r["confidence"]
        key = ("low (0.0-0.4)" if c < 0.4 else "medium (0.4-0.6)" if c < 0.6
              else "high (0.6-0.8)" if c < 0.8 else "very_high (0.8-1.0)")
        bands[key].append(r["verdict"] in ("Correct", "Acceptable Alternate"))
    return {
        band: {"n": len(vals), "accept_rate": round(sum(vals) / len(vals), 4) if vals else None}
        for band, vals in bands.items()
    }


def precision_recall_f1(conn: sqlite3.Connection, structure_flag_column: str) -> Optional[dict]:
    """Generic precision/recall/F1 for a specific miss-type flag (e.g.
    'missed_triangle', 'missed_diagonal', 'false_positive', 'false_negative').

    Definitions used here (structure-detection framing, not a binary
    classifier over a fixed label set):
      - Positive prediction  = the engine reported that structure type present.
      - False negative       = reviewer flagged this exact miss-type on a
                               chart where the engine reported NOTHING of
                               that type (missed it entirely).
      - False positive       = reviewer's `false_positive` flag on a chart
                               where the engine's verdict was itself judged
                               Incorrect for reporting a structure not there.
      - True positive        = Correct/Acceptable Alternate verdict where
                               the corresponding miss-flag was NOT set.
    """
    # Suppressed below (bandit B608): structure_flag_column is only ever
    # called with a hardcoded literal from a fixed internal dict (see
    # full_summary() below), never request/user input. Verified in
    # docs/SECURITY_AUDIT.md.
    rows = fetch_all(
        conn,
        f"SELECT r.verdict as verdict, r.{structure_flag_column} as miss_flag, "  # nosec B608
        f"r.false_positive as fp FROM reviews r",
    )
    if not rows:
        return None
    tp = sum(1 for r in rows if r["verdict"] in ("Correct", "Acceptable Alternate") and not r["miss_flag"])
    fn = sum(1 for r in rows if r["miss_flag"])
    fp = sum(1 for r in rows if r["fp"] and r["verdict"] == "Incorrect")
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)) if (precision and recall and (precision + recall)) else None
    return {
        "true_positive": tp, "false_positive": fp, "false_negative": fn,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
    }


def reviewer_agreement(conn: sqlite3.Connection) -> Optional[dict]:
    """For analyses reviewed by MORE THAN ONE reviewer, what fraction of
    reviewer pairs agree on verdict? (Simple pairwise agreement rate --
    not Cohen's kappa, which needs a larger sample than a small pilot
    review would realistically have; documented as a known simplification.)
    """
    rows = fetch_all(conn, "SELECT analysis_id, verdict FROM reviews")
    if not rows:
        return None
    by_analysis: dict[str, list[str]] = {}
    for r in rows:
        by_analysis.setdefault(r["analysis_id"], []).append(r["verdict"])
    multi = {k: v for k, v in by_analysis.items() if len(v) > 1}
    if not multi:
        return {"analyses_with_multiple_reviews": 0, "pairwise_agreement_rate": None}
    agree, total_pairs = 0, 0
    for verdicts in multi.values():
        for i in range(len(verdicts)):
            for j in range(i + 1, len(verdicts)):
                total_pairs += 1
                if verdicts[i] == verdicts[j]:
                    agree += 1
    return {
        "analyses_with_multiple_reviews": len(multi),
        "pairwise_agreement_rate": round(agree / total_pairs, 4) if total_pairs else None,
    }


def quality_score_distribution(conn: sqlite3.Connection) -> dict:
    """Does NOT need review data -- direct engine output, available for
    all 369+ populated analyses immediately."""
    out = {}
    # Suppressed below (bandit B608): `col` iterates a hardcoded literal
    # tuple on the line above, never request/user input. Verified in
    # docs/SECURITY_AUDIT.md.
    for col in ("impulse_quality", "corrective_quality", "triangle_quality", "diagonal_quality", "confidence"):
        rows = [r[col] for r in fetch_all(conn, f"SELECT {col} FROM analyses WHERE {col} IS NOT NULL")]  # nosec B608
        if rows:
            rows_sorted = sorted(rows)
            n = len(rows_sorted)
            out[col] = {
                "n": n, "min": round(rows_sorted[0], 3), "median": round(rows_sorted[n // 2], 3),
                "max": round(rows_sorted[-1], 3), "mean": round(sum(rows_sorted) / n, 3),
            }
        else:
            out[col] = None
    return out


def full_summary(conn: sqlite3.Connection) -> dict:
    return {
        "review_count": review_count(conn),
        "structure_accuracy": structure_accuracy(conn),
        "wave_numbering_accuracy": wave_numbering_accuracy(conn),
        "hard_rule_compliance": hard_rule_compliance(conn),
        "confidence_calibration": confidence_calibration(conn),
        "precision_recall_f1": {
            flag: precision_recall_f1(conn, flag)
            for flag in ("missed_triangle", "missed_diagonal", "mis_numbering", "wrong_correction", "wrong_degree")
        },
        "reviewer_agreement": reviewer_agreement(conn),
        "quality_score_distribution": quality_score_distribution(conn),
    }


if __name__ == "__main__":
    import json
    with connect() as conn:
        print(json.dumps(full_summary(conn), indent=2, default=str))
