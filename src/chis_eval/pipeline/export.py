from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable


CANONICAL_CSV_COLUMNS = [
    "schema_version",
    "record_version",
    "question_id",
    "group_id",
    "shared_material",
    "raw_question",
    "normalized_question",
    "question",
    "raw_option_A",
    "raw_option_B",
    "raw_option_C",
    "raw_option_D",
    "option_A",
    "option_B",
    "option_C",
    "option_D",
    "answer",
    "answer_explanation",
    "answer_status",
    "has_image",
    "image_paths_json",
    "source_id",
    "source_name",
    "source_url",
    "paper_title",
    "year",
    "province",
    "exam_type",
    "page_number",
    "retrieved_at",
    "source_records_json",
    "answer_evidence_json",
    "duplicate_status",
    "parse_status",
    "review_status",
    "image_dependency",
    "issues_json",
    "collector",
    "reviewer",
    "notes",
    "raw_file",
    "content_hash",
    "ordered_hash",
    "permutation_hash",
    "license_status",
    "normalization_changes_json",
]


def export_canonical_csv(path: str | Path, records: Iterable[dict[str, Any]]) -> int:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [_flatten(record) for record in records]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANONICAL_CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _safe(value) for key, value in row.items()})
    return len(rows)


def _flatten(record: dict[str, Any]) -> dict[str, Any]:
    raw_options = record.get("raw_options") or {}
    options = record.get("options") or {}
    source = record.get("source") or {}
    quality = record.get("quality") or {}
    provenance = record.get("provenance") or {}
    row = {
        "schema_version": record.get("schema_version", ""),
        "record_version": record.get("record_version", ""),
        "question_id": record.get("question_id", ""),
        "group_id": record.get("group_id", ""),
        "shared_material": record.get("shared_material", ""),
        "raw_question": record.get("raw_question", ""),
        "normalized_question": record.get("normalized_question", ""),
        "question": record.get("question", ""),
        "answer": record.get("answer", ""),
        "answer_explanation": record.get("answer_explanation", ""),
        "answer_status": quality.get("answer_status", ""),
        "has_image": record.get("has_image", False),
        "image_paths_json": _json(record.get("image_paths", [])),
        "source_id": source.get("source_id", ""),
        "source_name": source.get("site_name", ""),
        "source_url": source.get("url", ""),
        "paper_title": source.get("paper_title", ""),
        "year": source.get("year", ""),
        "province": source.get("province", ""),
        "exam_type": source.get("exam_type", ""),
        "page_number": source.get("page_number", ""),
        "retrieved_at": source.get("retrieved_at", ""),
        "source_records_json": _json(record.get("source_records", [])),
        "answer_evidence_json": _json(record.get("answer_evidence", [])),
        "duplicate_status": quality.get("duplicate_status", ""),
        "parse_status": quality.get("parse_status", ""),
        "review_status": quality.get("review_status", ""),
        "image_dependency": quality.get("image_dependency", ""),
        "issues_json": _json(quality.get("issues", [])),
        "collector": quality.get("collector", ""),
        "reviewer": quality.get("reviewer", ""),
        "notes": quality.get("notes", ""),
        "raw_file": provenance.get("raw_file", ""),
        "content_hash": provenance.get("content_hash", ""),
        "ordered_hash": provenance.get("ordered_hash", ""),
        "permutation_hash": provenance.get("permutation_hash", ""),
        "license_status": provenance.get("license_status", ""),
        "normalization_changes_json": _json(provenance.get("normalization_changes", [])),
    }
    for letter in "ABCD":
        row[f"raw_option_{letter}"] = raw_options.get(letter, "")
        row[f"option_{letter}"] = options.get(letter, "")
    return row


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _safe(value: Any) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text
