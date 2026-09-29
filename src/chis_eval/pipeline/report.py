from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


def build_quality_report(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(records)
    by_source: Counter[str] = Counter()
    by_year: Counter[str] = Counter()
    rejection_reasons: Counter[str] = Counter()
    answer_statuses: Counter[str] = Counter()
    parse_statuses: Counter[str] = Counter()
    review_statuses: Counter[str] = Counter()
    duplicate_statuses: Counter[str] = Counter()

    for record in rows:
        source = record.get("source") or {}
        quality = record.get("quality") or {}
        by_source[str(source.get("source_id") or "unknown")] += 1
        by_year[str(source.get("year") if source.get("year") is not None else "unknown")] += 1
        answer_statuses[str(quality.get("answer_status") or "unknown")] += 1
        parse_statuses[str(quality.get("parse_status") or "unknown")] += 1
        review_statuses[str(quality.get("review_status") or "unknown")] += 1
        duplicate_statuses[str(quality.get("duplicate_status") or "unknown")] += 1
        if quality.get("review_status") == "rejected":
            issues = quality.get("issues") or []
            if issues:
                for issue in issues:
                    rejection_reasons[str(issue.get("code") or "unspecified")] += 1
            else:
                rejection_reasons["unspecified"] += 1

    return {
        "total": len(rows),
        "qualified": sum(
            (r.get("quality") or {}).get("parse_status") == "valid"
            and (r.get("quality") or {}).get("answer_status") == "verified"
            and (r.get("quality") or {}).get("review_status") == "approved"
            and (r.get("quality") or {}).get("duplicate_status") == "unique"
            and (r.get("quality") or {}).get("image_dependency") != "image_dependent"
            for r in rows
        ),
        "missing_answer": answer_statuses["missing"],
        "verified_answer": answer_statuses["verified"],
        "parse_failed": parse_statuses["failed"],
        "suspected_duplicate": duplicate_statuses["suspected_duplicate"],
        "exact_duplicate": duplicate_statuses["exact_duplicate"],
        "image_dependent": sum(
            (r.get("quality") or {}).get("image_dependency") == "image_dependent" for r in rows
        ),
        "needs_human_review": sum(
            (r.get("quality") or {}).get("review_status") in {"pending", "needs_revision"}
            for r in rows
        ),
        "by_source": dict(sorted(by_source.items())),
        "by_year": dict(sorted(by_year.items())),
        "answer_statuses": dict(sorted(answer_statuses.items())),
        "parse_statuses": dict(sorted(parse_statuses.items())),
        "review_statuses": dict(sorted(review_statuses.items())),
        "duplicate_statuses": dict(sorted(duplicate_statuses.items())),
        "rejection_reasons": dict(sorted(rejection_reasons.items())),
    }


def write_quality_report(path: str | Path, report: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
