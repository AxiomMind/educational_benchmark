from __future__ import annotations

import csv
from pathlib import Path

from chis_eval.pipeline.export import export_canonical_csv


def test_canonical_csv_contains_traceability_fields(tmp_path: Path, valid_record: dict) -> None:
    output = tmp_path / "questions.csv"
    count = export_canonical_csv(output, [valid_record])
    with output.open("r", encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert count == 1
    assert row["question_id"] == "CHIS_000001"
    assert row["source_url"] == "https://example.test/paper/1"
    assert row["raw_question"]
    assert row["answer_evidence_json"].startswith("[")
