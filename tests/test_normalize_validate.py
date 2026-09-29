from copy import deepcopy

from chis_eval.pipeline.normalize import normalise_record
from chis_eval.pipeline.validate import validate_records


def test_normalisation_preserves_raw_and_tracks_changes(valid_record: dict) -> None:
    record = deepcopy(valid_record)
    record["raw_question"] = " １． 中国古代\u200b某制度的主要作用是&nbsp; "
    record["raw_options"]["A"] = "Ａ．加强中央集权"
    record["answer"] = "ａ"
    normalized = normalise_record(record)
    assert normalized["raw_question"].startswith(" １")
    assert normalized["question"] == "中国古代某制度的主要作用是"
    assert normalized["options"]["A"] == "加强中央集权"
    assert normalized["answer"] == "A"
    assert normalized["provenance"]["normalization_changes"]
    assert len(normalized["provenance"]["ordered_hash"]) == 64


def test_validation_verifies_only_official_or_two_reliable_sources(valid_record: dict) -> None:
    records, summary = validate_records([valid_record])
    assert records[0]["quality"]["answer_status"] == "verified"
    assert records[0]["quality"]["parse_status"] == "valid"
    assert summary.qualified == 1

    single = deepcopy(valid_record)
    single["answer_evidence"] = [{"source_id": "one", "answer": "A"}]
    checked, _ = validate_records([single])
    assert checked[0]["quality"]["answer_status"] == "single_source"


def test_validation_detects_structural_errors_and_group_mismatch(valid_record: dict) -> None:
    first = deepcopy(valid_record)
    second = deepcopy(valid_record)
    second["question_id"] = "CHIS_000002"
    second["shared_material"] = "different material"
    second["options"]["D"] = second["options"]["C"]
    records, summary = validate_records([first, second])
    codes = {issue["code"] for issue in records[1]["quality"]["issues"]}
    assert "duplicate_options" in codes
    assert "inconsistent_group_material" in codes
    assert summary.parse_failed == 2
