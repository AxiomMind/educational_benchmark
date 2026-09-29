from copy import deepcopy

from chis_eval.pipeline.deduplicate import deduplicate_records


def test_exact_and_reordered_duplicates_are_separate(valid_record: dict) -> None:
    exact = deepcopy(valid_record)
    exact["question_id"] = "CHIS_000002"
    reordered = deepcopy(valid_record)
    reordered["question_id"] = "CHIS_000003"
    reordered["options"] = {
        "A": valid_record["options"]["B"],
        "B": valid_record["options"]["A"],
        "C": valid_record["options"]["C"],
        "D": valid_record["options"]["D"],
    }
    reordered["answer"] = "B"
    result = deduplicate_records([valid_record, exact, reordered])
    assert len(result.exact_pairs) == 1
    assert len(result.reordered_pairs) == 2
    statuses = {r["question_id"]: r["quality"]["duplicate_status"] for r in result.records}
    assert statuses["CHIS_000001"] == "exact_duplicate"
    assert statuses["CHIS_000003"] == "reordered_duplicate"


def test_near_duplicate_is_only_flagged(valid_record: dict) -> None:
    near = deepcopy(valid_record)
    near["question_id"] = "CHIS_000002"
    near["question"] += "？"
    near["normalized_question"] = near["question"]
    result = deduplicate_records([valid_record, near], near_threshold=0.80)
    assert len(result.suspected_pairs) == 1
    assert len(result.records) == 2
    assert all(r["quality"]["duplicate_status"] == "suspected_duplicate" for r in result.records)
