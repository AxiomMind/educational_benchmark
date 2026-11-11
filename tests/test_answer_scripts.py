import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_ocr_does_not_choose_last_of_conflicting_answers():
    spec = importlib.util.spec_from_file_location("answer_ocr", ROOT / "scripts/batch_ocr_answers.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.extract_candidate("A项正确；故选A项。")[0] == "A"
    assert module.extract_candidate("【答案】B。故选D项。")[0] == ""


def test_apply_preserves_answer_and_rejects_untraceable_cache(tmp_path, valid_record):
    record = valid_record
    record["source"]["source_id"] = "ZUJUAN_XKW"
    record["provenance"]["source_question_number"] = "123"
    input_file = tmp_path / "questions.jsonl"
    cache_file = tmp_path / "cache.json"
    output = tmp_path / "answered.jsonl"
    input_file.write_text(json.dumps(record) + "\n", encoding="utf-8")
    cache_file.write_text(json.dumps({"123": {"answer": "D"}}), encoding="utf-8")
    args = [sys.executable, str(ROOT / "scripts/apply_crawled_answers.py"),
            "--input", str(input_file), "--cache", str(cache_file),
            "--images", str(tmp_path), "--output", str(output),
            "--report", str(tmp_path / "report.json")]
    subprocess.run(args, check=True, capture_output=True)
    assert json.loads(output.read_text(encoding="utf-8"))["answer"] == "A"
    record["answer"] = ""
    input_file.write_text(json.dumps(record) + "\n", encoding="utf-8")
    subprocess.run(args, check=True, capture_output=True)
    assert json.loads(output.read_text(encoding="utf-8"))["answer"] == ""
    image = tmp_path / "123.png"
    image.write_bytes(b"synthetic image for hash verification")
    cache_file.write_text(json.dumps({"123": {
        "answer": "D", "explanation": "synthetic explanation",
        "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
    }}), encoding="utf-8")
    subprocess.run(args, check=True, capture_output=True)
    applied = json.loads(output.read_text(encoding="utf-8"))
    assert applied["answer"] == "D"
    assert applied["quality"]["answer_status"] == "single_source"
    assert applied["quality"]["review_status"] == "pending"
    assert applied["answer_evidence"][0]["reliable"] is False
