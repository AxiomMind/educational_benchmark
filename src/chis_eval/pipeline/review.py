from __future__ import annotations

import csv
import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ..errors import ReviewMergeError
from ..models import REVIEW_STATUSES
from ..storage.jsonl import write_jsonl


REVIEW_COLUMNS = [
    "question_id",
    "group_id",
    "shared_material",
    "question",
    "option_A",
    "option_B",
    "option_C",
    "option_D",
    "answer",
    "answer_status",
    "source_name",
    "source_url",
    "year",
    "province",
    "exam_type",
    "duplicate_status",
    "parse_status",
    "review_status",
    "reviewer",
    "notes",
    "review_snapshot_hash",
]


@dataclass(frozen=True)
class ReviewMergeSummary:
    input_rows: int
    merged: int
    skipped: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "input_rows": self.input_rows,
            "merged": self.merged,
            "skipped": self.skipped,
            "errors": list(self.errors),
        }


def export_review_csv(path: str | Path, records: Iterable[dict[str, Any]]) -> int:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [_review_row(record) for record in records]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_safe(value) for key, value in row.items()})
    return len(rows)


def merge_review_csv(
    records: Iterable[dict[str, Any]], review_path: str | Path
) -> tuple[list[dict[str, Any]], ReviewMergeSummary]:
    output = [deepcopy(record) for record in records]
    by_id = {str(record.get("question_id")): record for record in output}
    errors: list[str] = []
    merged = 0
    row_count = 0
    seen_ids: set[str] = set()
    with Path(review_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = set(REVIEW_COLUMNS) - set(reader.fieldnames or [])
        if missing_columns:
            raise ReviewMergeError(
                "Review sheet is missing columns: " + ", ".join(sorted(missing_columns))
            )
        for line_number, raw_row in enumerate(reader, start=2):
            row_count += 1
            row = {key: _csv_restore(value or "") for key, value in raw_row.items()}
            question_id = row.get("question_id", "")
            if question_id in seen_ids:
                errors.append(f"line {line_number}: duplicate question_id {question_id}")
                continue
            seen_ids.add(question_id)
            record = by_id.get(question_id)
            if record is None:
                errors.append(f"line {line_number}: unknown question_id {question_id}")
                continue
            if row.get("review_snapshot_hash") != review_snapshot_hash(record):
                errors.append(f"line {line_number}: stale review snapshot for {question_id}")
                continue
            status = row.get("review_status", "pending") or "pending"
            if status not in REVIEW_STATUSES:
                errors.append(f"line {line_number}: invalid review_status {status!r}")
                continue
            quality = record.setdefault("quality", {})
            quality["review_status"] = status
            quality["reviewer"] = row.get("reviewer", "")
            quality["notes"] = row.get("notes", "")
            record["record_version"] = int(record.get("record_version", 1)) + 1
            merged += 1
    return output, ReviewMergeSummary(row_count, merged, row_count - merged, tuple(errors))


def write_merged_review(
    input_path: str | Path,
    review_path: str | Path,
    output_path: str | Path,
    records: Iterable[dict[str, Any]],
) -> ReviewMergeSummary:
    if Path(input_path).resolve() == Path(output_path).resolve():
        raise ReviewMergeError("Review merge output must not overwrite the input JSONL")
    merged, summary = merge_review_csv(records, review_path)
    write_jsonl(output_path, merged)
    return summary


def review_snapshot_hash(record: dict[str, Any]) -> str:
    protected = {
        "question_id": record.get("question_id"),
        "group_id": record.get("group_id"),
        "shared_material": record.get("shared_material"),
        "question": record.get("question"),
        "options": record.get("options"),
        "answer": record.get("answer"),
        "source": record.get("source"),
        "answer_status": record.get("quality", {}).get("answer_status"),
        "duplicate_status": record.get("quality", {}).get("duplicate_status"),
        "parse_status": record.get("quality", {}).get("parse_status"),
    }
    encoded = json.dumps(protected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _review_row(record: dict[str, Any]) -> dict[str, Any]:
    options = record.get("options") or {}
    source = record.get("source") or {}
    quality = record.get("quality") or {}
    return {
        "question_id": record.get("question_id", ""),
        "group_id": record.get("group_id", ""),
        "shared_material": record.get("shared_material", ""),
        "question": record.get("question", ""),
        "option_A": options.get("A", ""),
        "option_B": options.get("B", ""),
        "option_C": options.get("C", ""),
        "option_D": options.get("D", ""),
        "answer": record.get("answer", ""),
        "answer_status": quality.get("answer_status", ""),
        "source_name": source.get("site_name", ""),
        "source_url": source.get("url", ""),
        "year": source.get("year", ""),
        "province": source.get("province", ""),
        "exam_type": source.get("exam_type", ""),
        "duplicate_status": quality.get("duplicate_status", ""),
        "parse_status": quality.get("parse_status", ""),
        "review_status": quality.get("review_status", "pending"),
        "reviewer": quality.get("reviewer", ""),
        "notes": quality.get("notes", ""),
        "review_snapshot_hash": review_snapshot_hash(record),
    }


def _csv_safe(value: Any) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _csv_restore(value: str) -> str:
    if len(value) >= 2 and value[0] == "'" and value[1] in "=+-@":
        return value[1:]
    return value
