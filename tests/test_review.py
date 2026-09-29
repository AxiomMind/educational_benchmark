from __future__ import annotations

import csv
from copy import deepcopy
from pathlib import Path

import pytest

from chis_eval.errors import ReviewMergeError
from chis_eval.pipeline.review import export_review_csv, merge_review_csv, write_merged_review


def _edit_review(path: Path, **updates: str) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = reader.fieldnames
    rows[0].update(updates)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_review_export_and_safe_merge(tmp_path: Path, valid_record: dict) -> None:
    review_path = tmp_path / "review.csv"
    export_review_csv(review_path, [valid_record])
    _edit_review(
        review_path,
        review_status="approved",
        reviewer="张三",
        notes="checked",
        question="tampering is ignored",
    )
    records, summary = merge_review_csv([valid_record], review_path)
    assert summary.merged == 1
    assert records[0]["question"] == valid_record["question"]
    assert records[0]["quality"]["review_status"] == "approved"
    assert records[0]["record_version"] == 2


def test_review_detects_stale_record(tmp_path: Path, valid_record: dict) -> None:
    review_path = tmp_path / "review.csv"
    export_review_csv(review_path, [valid_record])
    changed = deepcopy(valid_record)
    changed["question"] += " changed"
    _, summary = merge_review_csv([changed], review_path)
    assert summary.merged == 0
    assert "stale review snapshot" in summary.errors[0]


def test_review_never_overwrites_input(tmp_path: Path, valid_record: dict) -> None:
    review_path = tmp_path / "review.csv"
    input_path = tmp_path / "records.jsonl"
    export_review_csv(review_path, [valid_record])
    with pytest.raises(ReviewMergeError, match="must not overwrite"):
        write_merged_review(input_path, review_path, input_path, [valid_record])
