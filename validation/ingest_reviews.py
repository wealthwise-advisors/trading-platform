"""Expert Chart Validation Framework -- review ingestion (Task 8).

Loads a completed reviews CSV (downloaded from review_gallery.html, or
filled in manually in a spreadsheet using the same column names) into the
`reviews` table. Run: py -3.12 validation/ingest_reviews.py <path.csv>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from validation.db import connect, insert_review, init_db

REQUIRED_COLUMNS = [
    "analysis_id", "reviewer", "verdict", "false_positive", "false_negative",
    "mis_numbering", "wrong_degree", "missed_triangle", "missed_diagonal",
    "wrong_correction", "notes",
]


def ingest(csv_path: Path) -> int:
    init_db()
    df = pd.read_csv(csv_path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"reviews CSV missing required columns: {missing}")

    n = 0
    with connect() as conn:
        for _, row in df.iterrows():
            insert_review(
                conn, analysis_id=row["analysis_id"], reviewer=row["reviewer"],
                verdict=row["verdict"],
                false_positive=bool(row["false_positive"]), false_negative=bool(row["false_negative"]),
                mis_numbering=bool(row["mis_numbering"]), wrong_degree=bool(row["wrong_degree"]),
                missed_triangle=bool(row["missed_triangle"]), missed_diagonal=bool(row["missed_diagonal"]),
                wrong_correction=bool(row["wrong_correction"]), notes=str(row.get("notes", "")),
            )
            n += 1
    return n


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: py -3.12 validation/ingest_reviews.py <reviews_batch.csv>")
        sys.exit(1)
    count = ingest(Path(sys.argv[1]))
    print(f"ingested {count} reviews")
