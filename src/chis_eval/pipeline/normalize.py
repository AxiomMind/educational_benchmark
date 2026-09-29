from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from copy import deepcopy
from typing import Any, Iterable

from ..models import build_question_record
from ..parsers.answer import extract_answer


_INVISIBLE_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACE_RE = re.compile(r"\s+")
_QUESTION_NUMBER_RE = re.compile(r"^\s*(?:第\s*)?\d+\s*(?:题|[.．、)）])\s*")
_OPTION_PREFIX_RE = re.compile(r"^\s*[A-DＡ-Ｄa-dａ-ｄ]\s*[.．、:：)）]\s*")


def normalise_text(value: Any, *, strip_question_number: bool = False) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = unicodedata.normalize("NFKC", text)
    text = _INVISIBLE_RE.sub("", text)
    text = _CONTROL_RE.sub("", text)
    text = _SPACE_RE.sub(" ", text).strip()
    if strip_question_number:
        text = _QUESTION_NUMBER_RE.sub("", text, count=1).strip()
    return text


def normalise_record(record: dict[str, Any]) -> dict[str, Any]:
    result = build_question_record(deepcopy(record))
    changes: list[dict[str, str]] = []
    raw_question = result.get("raw_question") or result.get("question") or ""
    if not result.get("raw_question"):
        result["raw_question"] = raw_question
    normalized_question = normalise_text(raw_question, strip_question_number=True)
    _track_change(changes, "question", raw_question, normalized_question)
    result["normalized_question"] = normalized_question
    result["question"] = normalized_question

    raw_options = result.get("raw_options") or result.get("options") or {}
    result["raw_options"] = {letter: str(raw_options.get(letter, "")) for letter in "ABCD"}
    normalized_options: dict[str, str] = {}
    for letter in "ABCD":
        before = raw_options.get(letter, "")
        after = _OPTION_PREFIX_RE.sub("", normalise_text(before), count=1).strip()
        normalized_options[letter] = after
        _track_change(changes, f"options.{letter}", before, after)
    result["options"] = normalized_options

    result["shared_material"] = normalise_text(result.get("shared_material", ""))
    result["answer_explanation"] = normalise_text(result.get("answer_explanation", ""))
    original_answer = str(result.get("answer") or "")
    result["answer"] = extract_answer(original_answer)
    _track_change(changes, "answer", original_answer, result["answer"])

    if not result.get("group_id") and result.get("question_id"):
        suffix = str(result["question_id"]).split("_")[-1]
        result["group_id"] = f"GROUP_{suffix}"

    provenance = result.setdefault("provenance", {})
    provenance["normalization_changes"] = changes
    provenance["ordered_hash"] = ordered_hash(result)
    provenance["permutation_hash"] = permutation_hash(result)
    return result


def normalise_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalise_record(record) for record in records]


def ordered_hash(record: dict[str, Any]) -> str:
    payload = {
        "shared_material": record.get("shared_material", ""),
        "question": record.get("normalized_question") or record.get("question", ""),
        "options": [record.get("options", {}).get(letter, "") for letter in "ABCD"],
    }
    return _stable_hash(payload)


def permutation_hash(record: dict[str, Any]) -> str:
    payload = {
        "shared_material": record.get("shared_material", ""),
        "question": record.get("normalized_question") or record.get("question", ""),
        "options": sorted(record.get("options", {}).get(letter, "") for letter in "ABCD"),
    }
    return _stable_hash(payload)


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _track_change(changes: list[dict[str, str]], field: str, before: Any, after: Any) -> None:
    before_text = "" if before is None else str(before)
    after_text = "" if after is None else str(after)
    if before_text != after_text:
        changes.append({"field": field, "before": before_text, "after": after_text})
