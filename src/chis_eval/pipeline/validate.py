from __future__ import annotations

import re
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlparse

from ..models import ANSWER_STATUSES, REVIEW_STATUSES


@dataclass(frozen=True)
class ValidationSummary:
    total: int
    structurally_valid: int
    qualified: int
    missing_answer: int
    parse_failed: int
    image_dependent: int
    by_source: dict[str, int]
    by_year: dict[str, int]
    issue_counts: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "structurally_valid": self.structurally_valid,
            "qualified": self.qualified,
            "missing_answer": self.missing_answer,
            "parse_failed": self.parse_failed,
            "image_dependent": self.image_dependent,
            "by_source": self.by_source,
            "by_year": self.by_year,
            "issue_counts": self.issue_counts,
        }


def validate_records(
    records: Iterable[dict[str, Any]], earliest_year: int = 1900
) -> tuple[list[dict[str, Any]], ValidationSummary]:
    output = [deepcopy(record) for record in records]
    material_by_group: dict[str, set[str]] = defaultdict(set)
    for record in output:
        group_id = str(record.get("group_id") or "")
        if group_id:
            material_by_group[group_id].add(str(record.get("shared_material") or ""))

    for record in output:
        quality = record.setdefault("quality", {})
        existing = quality.get("issues") or []
        issues = [issue for issue in existing if isinstance(issue, dict)]
        issues.extend(_record_issues(record, earliest_year))
        group_id = str(record.get("group_id") or "")
        if group_id and len(material_by_group[group_id]) > 1:
            issues.append(
                _issue(
                    "inconsistent_group_material",
                    "error",
                    "Records in the same group have different shared material",
                )
            )
        quality["issues"] = _unique_issues(issues)
        _set_answer_status(record)
        _set_image_dependency(record)
        severities = {item.get("severity") for item in quality["issues"]}
        if "error" in severities:
            quality["parse_status"] = "failed"
        elif quality["issues"]:
            quality["parse_status"] = "needs_review"
        else:
            quality["parse_status"] = "valid"

    issue_counts: Counter[str] = Counter()
    by_source: Counter[str] = Counter()
    by_year: Counter[str] = Counter()
    for record in output:
        for issue in record.get("quality", {}).get("issues", []):
            issue_counts[str(issue.get("code", "unknown"))] += 1
        source = record.get("source", {})
        by_source[str(source.get("source_id") or "unknown")] += 1
        by_year[str(source.get("year") if source.get("year") is not None else "unknown")] += 1

    summary = ValidationSummary(
        total=len(output),
        structurally_valid=sum(
            r.get("quality", {}).get("parse_status") == "valid" for r in output
        ),
        qualified=sum(
            r.get("quality", {}).get("parse_status") == "valid"
            and r.get("quality", {}).get("answer_status") == "verified"
            and r.get("quality", {}).get("image_dependency") != "image_dependent"
            for r in output
        ),
        missing_answer=sum(r.get("quality", {}).get("answer_status") == "missing" for r in output),
        parse_failed=sum(r.get("quality", {}).get("parse_status") == "failed" for r in output),
        image_dependent=sum(
            r.get("quality", {}).get("image_dependency") == "image_dependent" for r in output
        ),
        by_source=dict(sorted(by_source.items())),
        by_year=dict(sorted(by_year.items())),
        issue_counts=dict(sorted(issue_counts.items())),
    )
    return output, summary


def _record_issues(record: dict[str, Any], earliest_year: int) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not str(record.get("normalized_question") or record.get("question") or "").strip():
        issues.append(_issue("empty_question", "error", "Question text is empty"))
    if not str(record.get("group_id") or "").strip():
        issues.append(_issue("missing_group_id", "error", "group_id is empty"))

    options = record.get("options")
    if not isinstance(options, dict) or set(options) != set("ABCD"):
        issues.append(_issue("invalid_option_keys", "error", "Options must be exactly A, B, C and D"))
    else:
        empty = [letter for letter in "ABCD" if not str(options.get(letter) or "").strip()]
        if empty:
            issues.append(_issue("empty_options", "error", f"Empty options: {', '.join(empty)}"))
        nonempty = [str(options[letter]).strip() for letter in "ABCD" if str(options[letter]).strip()]
        if len(nonempty) != len(set(nonempty)):
            issues.append(_issue("duplicate_options", "error", "Two or more options have the same text"))

    answer = str(record.get("answer") or "")
    if answer and answer not in set("ABCD"):
        issues.append(_issue("invalid_answer", "error", "Answer must be A, B, C or D"))
    if answer in set("ABCD") and isinstance(options, dict) and not options.get(answer):
        issues.append(_issue("missing_answer_option", "error", "Answer points to a missing option"))

    source = record.get("source") or {}
    url = str(source.get("url") or "")
    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        issues.append(_issue("invalid_source_url", "error", "A traceable HTTP(S) source URL is required"))
    year = source.get("year")
    latest_year = datetime.now(timezone.utc).year + 1
    if year is not None and (not isinstance(year, int) or not earliest_year <= year <= latest_year):
        issues.append(_issue("invalid_year", "warning", f"Year must be between {earliest_year} and {latest_year}"))

    searchable = " ".join(
        [
            str(record.get("shared_material") or ""),
            str(record.get("question") or ""),
            *(str(value) for value in (options or {}).values()),
        ]
    )
    if "\ufffd" in searchable or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", searchable):
        issues.append(_issue("abnormal_unicode", "warning", "Replacement or control characters detected"))

    provenance = record.get("provenance") or {}
    confidence = provenance.get("ocr_confidence")
    if isinstance(confidence, (float, int)) and confidence < 0.80:
        issues.append(_issue("low_ocr_confidence", "warning", "OCR confidence is below 0.80"))
    if record.get("has_image") and not record.get("image_paths"):
        issues.append(_issue("unprocessed_image", "warning", "Image reference has no saved local asset"))
    return issues


def _set_answer_status(record: dict[str, Any]) -> None:
    quality = record.setdefault("quality", {})
    answer = str(record.get("answer") or "")
    if not answer:
        quality["answer_status"] = "missing"
        return
    if answer not in set("ABCD"):
        quality["answer_status"] = "invalid"
        return

    evidence = [item for item in record.get("answer_evidence", []) if isinstance(item, dict)]
    evidence_answers = {str(item.get("answer", "")).upper() for item in evidence if item.get("answer")}
    if len(evidence_answers) > 1:
        quality["answer_status"] = "conflict"
    elif any(item.get("official") is True and item.get("answer") == answer for item in evidence):
        quality["answer_status"] = "verified"
    else:
        reliable_sources = {
            item.get("source_id")
            for item in evidence
            if item.get("reliable") is True and item.get("answer") == answer
        }
        if len(reliable_sources) >= 2:
            quality["answer_status"] = "verified"
        elif evidence:
            quality["answer_status"] = "single_source"
        elif quality.get("answer_status") not in ANSWER_STATUSES:
            quality["answer_status"] = "unchecked"


def _set_image_dependency(record: dict[str, Any]) -> None:
    quality = record.setdefault("quality", {})
    if not record.get("has_image"):
        quality["image_dependency"] = "not_image_dependent"
        return
    text = f"{record.get('shared_material', '')} {record.get('question', '')}"
    cues = ("如图", "下图", "图中", "地图", "示意图", "表中", "图表")
    quality["image_dependency"] = (
        "image_dependent" if any(cue in text for cue in cues) else "needs_review"
    )


def _issue(code: str, severity: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def _unique_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    output: list[dict[str, Any]] = []
    for issue in issues:
        key = (str(issue.get("code", "")), str(issue.get("message", "")))
        if key not in seen:
            seen.add(key)
            output.append(issue)
    return output
