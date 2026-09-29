from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping


ANSWER_STATUSES = {
    "unchecked",
    "verified",
    "single_source",
    "conflict",
    "missing",
    "invalid",
}
REVIEW_STATUSES = {"pending", "approved", "needs_revision", "rejected"}
DUPLICATE_STATUSES = {
    "unchecked",
    "unique",
    "exact_duplicate",
    "reordered_duplicate",
    "suspected_duplicate",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empty_question_record() -> dict[str, Any]:
    """Return a fresh record matching the V0.1 canonical schema."""
    return {
        "schema_version": "0.1.0",
        "record_version": 1,
        "question_id": "",
        "group_id": "",
        "shared_material": "",
        "raw_question": "",
        "normalized_question": "",
        "question": "",
        "raw_options": {"A": "", "B": "", "C": "", "D": ""},
        "options": {"A": "", "B": "", "C": "", "D": ""},
        "answer": "",
        "answer_explanation": "",
        "answer_evidence": [],
        "has_image": False,
        "image_paths": [],
        "source": {
            "source_id": "",
            "site_name": "",
            "url": "",
            "paper_title": "",
            "year": None,
            "province": "",
            "exam_type": "",
            "page_number": None,
            "retrieved_at": "",
        },
        "source_records": [],
        "labels": {
            "primary_ability": "",
            "history_scope": "",
            "historical_period": "",
            "knowledge_point": "",
            "material_type": "",
        },
        "quality": {
            "answer_status": "unchecked",
            "duplicate_status": "unchecked",
            "parse_status": "pending",
            "review_status": "pending",
            "image_dependency": "unknown",
            "issues": [],
            "collector": "",
            "reviewer": "",
            "notes": "",
        },
        "provenance": {
            "raw_file": "",
            "content_hash": "",
            "ordered_hash": "",
            "permutation_hash": "",
            "crawler_version": "v0.1",
            "license_status": "unknown",
            "normalization_changes": [],
        },
    }


def build_question_record(values: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Deep-merge supplied values into a new canonical record."""
    record = empty_question_record()
    if values:
        _deep_update(record, values)
    return record


def _deep_update(target: dict[str, Any], values: Mapping[str, Any]) -> None:
    for key, value in values.items():
        if isinstance(value, Mapping) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = deepcopy(value)
