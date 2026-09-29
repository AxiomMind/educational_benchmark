from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import combinations
from typing import Any, Iterable

from .normalize import ordered_hash, permutation_hash


@dataclass(frozen=True)
class DeduplicationResult:
    records: list[dict[str, Any]]
    exact_pairs: list[dict[str, Any]]
    reordered_pairs: list[dict[str, Any]]
    suspected_pairs: list[dict[str, Any]]

    def summary(self) -> dict[str, int]:
        return {
            "records": len(self.records),
            "exact_duplicate_pairs": len(self.exact_pairs),
            "reordered_duplicate_pairs": len(self.reordered_pairs),
            "suspected_duplicate_pairs": len(self.suspected_pairs),
        }


def deduplicate_records(
    records: Iterable[dict[str, Any]], near_threshold: float = 0.88, ngram_size: int = 3
) -> DeduplicationResult:
    if not 0 <= near_threshold <= 1:
        raise ValueError("near_threshold must be between 0 and 1")
    output = [deepcopy(record) for record in records]
    for record in output:
        provenance = record.setdefault("provenance", {})
        provenance["ordered_hash"] = ordered_hash(record)
        provenance["permutation_hash"] = permutation_hash(record)
        record.setdefault("quality", {})["duplicate_status"] = "unique"

    exact_pairs = _hash_pairs(output, "ordered_hash", "exact_duplicate")
    exact_keys = {_pair_key(pair) for pair in exact_pairs}
    reordered_pairs = [
        pair
        for pair in _hash_pairs(output, "permutation_hash", "reordered_duplicate")
        if _pair_key(pair) not in exact_keys
    ]

    known = exact_keys | {_pair_key(pair) for pair in reordered_pairs}
    suspected_pairs: list[dict[str, Any]] = []
    for left, right in combinations(output, 2):
        key = tuple(sorted((str(left.get("question_id")), str(right.get("question_id")))))
        if key in known:
            continue
        similarity = _similarity(_comparison_text(left), _comparison_text(right), ngram_size)
        if similarity >= near_threshold:
            pair = _pair_report(left, right, similarity, "suspected_duplicate")
            suspected_pairs.append(pair)
            _set_duplicate_status(left, "suspected_duplicate")
            _set_duplicate_status(right, "suspected_duplicate")

    return DeduplicationResult(output, exact_pairs, reordered_pairs, suspected_pairs)


def _hash_pairs(
    records: list[dict[str, Any]], hash_field: str, status: str
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        digest = str(record.get("provenance", {}).get(hash_field) or "")
        if digest:
            groups[digest].append(record)
    pairs: list[dict[str, Any]] = []
    for group in groups.values():
        if len(group) < 2:
            continue
        for left, right in combinations(group, 2):
            pairs.append(_pair_report(left, right, 1.0, status))
            _set_duplicate_status(left, status)
            _set_duplicate_status(right, status)
    return pairs


def _set_duplicate_status(record: dict[str, Any], status: str) -> None:
    priority = {
        "unique": 0,
        "suspected_duplicate": 1,
        "reordered_duplicate": 2,
        "exact_duplicate": 3,
    }
    quality = record.setdefault("quality", {})
    current = str(quality.get("duplicate_status") or "unique")
    if priority.get(status, 0) > priority.get(current, 0):
        quality["duplicate_status"] = status


def _comparison_text(record: dict[str, Any]) -> str:
    options = record.get("options") or {}
    return "|".join(
        [
            str(record.get("shared_material") or ""),
            str(record.get("normalized_question") or record.get("question") or ""),
            *(str(options.get(letter) or "") for letter in "ABCD"),
        ]
    )


def _similarity(left: str, right: str, ngram_size: int) -> float:
    sequence = SequenceMatcher(None, left, right).ratio()
    left_ngrams = _ngrams(left, ngram_size)
    right_ngrams = _ngrams(right, ngram_size)
    if not left_ngrams and not right_ngrams:
        jaccard = 1.0
    elif not left_ngrams or not right_ngrams:
        jaccard = 0.0
    else:
        jaccard = len(left_ngrams & right_ngrams) / len(left_ngrams | right_ngrams)
    return round((sequence + jaccard) / 2, 6)


def _ngrams(text: str, size: int) -> set[str]:
    compact = "".join(text.split())
    if not compact:
        return set()
    if len(compact) <= size:
        return {compact}
    return {compact[index : index + size] for index in range(len(compact) - size + 1)}


def _pair_report(
    left: dict[str, Any], right: dict[str, Any], similarity: float, duplicate_type: str
) -> dict[str, Any]:
    suggested = _suggested_record(left, right)
    return {
        "question_id_1": left.get("question_id", ""),
        "question_id_2": right.get("question_id", ""),
        "duplicate_type": duplicate_type,
        "similarity": similarity,
        "question_1": left.get("question", ""),
        "question_2": right.get("question", ""),
        "options_1": left.get("options", {}),
        "options_2": right.get("options", {}),
        "source_1": left.get("source", {}),
        "source_2": right.get("source", {}),
        "suggested_keep": suggested.get("question_id", ""),
        "answer_equivalence": _answer_equivalence(left, right),
        "human_status": "pending",
    }


def _suggested_record(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    answer_rank = {
        "verified": 5,
        "single_source": 4,
        "unchecked": 3,
        "missing": 2,
        "conflict": 1,
        "invalid": 0,
    }
    license_rank = {"allowed": 3, "research_only": 2, "unknown": 1, "restricted": 0}

    def score(record: dict[str, Any]) -> tuple[int, int, str]:
        return (
            answer_rank.get(str(record.get("quality", {}).get("answer_status")), 0),
            license_rank.get(str(record.get("provenance", {}).get("license_status")), 0),
            str(record.get("question_id", "")),
        )

    ranked = sorted((left, right), key=lambda record: (-score(record)[0], -score(record)[1], score(record)[2]))
    return ranked[0]


def _answer_equivalence(left: dict[str, Any], right: dict[str, Any]) -> str:
    left_answer = str(left.get("answer") or "")
    right_answer = str(right.get("answer") or "")
    if left_answer not in set("ABCD") or right_answer not in set("ABCD"):
        return "unknown"
    left_text = str((left.get("options") or {}).get(left_answer) or "").strip()
    right_text = str((right.get("options") or {}).get(right_answer) or "").strip()
    if not left_text or not right_text:
        return "unknown"
    return "equivalent" if left_text == right_text else "conflict"


def _pair_key(pair: dict[str, Any]) -> tuple[str, str]:
    return tuple(sorted((str(pair["question_id_1"]), str(pair["question_id_2"]))))
