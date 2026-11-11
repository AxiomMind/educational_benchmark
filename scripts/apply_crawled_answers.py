"""回填缺失答案到新文件；校验答案原图哈希，并生成最新质量报告。"""
import argparse
import hashlib
import json
from pathlib import Path
from chis_eval.pipeline.report import build_quality_report, write_quality_report
from chis_eval.pipeline.validate import validate_records
from chis_eval.storage.jsonl import read_jsonl, write_jsonl

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "datasets/history/questions.jsonl")
    parser.add_argument("--cache", type=Path, default=ROOT / "data/zujuan_answers_cache.json")
    parser.add_argument("--images", type=Path, default=ROOT / "data/answer_images")
    parser.add_argument("--output", type=Path, default=ROOT / "data/cleaned/answered.jsonl")
    parser.add_argument("--report", type=Path, default=ROOT / "data/reports/answers.json")
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("output 必须与 input 不同。")
    if not args.cache.is_file():
        parser.error(f"答案缓存不存在：{args.cache}")
    cache = json.loads(args.cache.read_text(encoding="utf-8"))
    records = list(read_jsonl(args.input))
    filled = 0
    for item in records:
        if item["source"]["source_id"] != "ZUJUAN_XKW" or item.get("answer"):
            continue
        qid = str(item.get("provenance", {}).get("source_question_number", ""))
        if not qid.isdigit():
            continue
        candidate = cache.get(qid, {})
        answer = candidate.get("answer", "")
        image = args.images / f"{qid}.png"
        if answer not in ("A", "B", "C", "D") or not image.is_file():
            continue
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        if candidate.get("image_sha256") != digest:
            continue
        item["answer"] = answer
        item["answer_explanation"] = candidate.get("explanation", "")
        item["answer_evidence"] = [{
            "source_id": "ZUJUAN_XKW", "answer": answer, "official": False,
            "reliable": False, "evidence_url": f"https://zujuan.xkw.com/17q{qid}.html",
            "source_question_number": qid, "image_name": image.name,
            "image_sha256": digest, "extraction_method": "tesseract_ocr",
            "needs_review": True,
        }]
        item["quality"]["answer_status"] = "single_source"
        item["quality"]["review_status"] = "pending"
        item["quality"]["issues"].append({
            "code": "ocr_answer_unreviewed", "severity": "warning",
            "message": "OCR 候选答案尚未人工核对原图"})
        item["record_version"] += 1
        filled += 1
    validated, _ = validate_records(records)
    write_jsonl(args.output, validated)
    write_quality_report(args.report, build_quality_report(validated))
    print(f"回填 {filled} 题；结果：{args.output}；报告：{args.report}")


if __name__ == "__main__":
    main()
