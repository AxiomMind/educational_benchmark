from chis_eval.pipeline.report import build_quality_report
from chis_eval.pipeline.validate import validate_records


def test_report_contains_required_counts(valid_record: dict) -> None:
    records, _ = validate_records([valid_record])
    report = build_quality_report(records)
    assert report["total"] == 1
    assert report["verified_answer"] == 1
    assert report["needs_human_review"] == 1
    assert report["qualified"] == 0
    assert report["by_source"] == {"fixture": 1}
