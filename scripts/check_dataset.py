"""离线检查题库结构、内容哈希、资源引用、原始文件和汇总报告的一致性。"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from chis_eval.pipeline.normalize import ordered_hash, permutation_hash
from chis_eval.pipeline.report import build_quality_report
from chis_eval.storage.jsonl import read_jsonl

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "datasets/history")
    args = parser.parse_args()
    base = args.dataset.resolve()
    records = list(read_jsonl(base / "questions.jsonl"))
    schema = json.loads((ROOT / "schemas/question_schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = []
    ids = Counter(record["question_id"] for record in records)
    errors.extend(f"重复题号：{qid}" for qid, count in ids.items() if count > 1)
    manifests = list(read_jsonl(base / "manifests/raw_files.jsonl"))
    raw_by_path = {row["raw_file"]: row for row in manifests}
    if len(raw_by_path) != len(manifests):
        errors.append("原始文件清单包含重复路径")
    used_assets, used_raw = set(), set()
    for record in records:
        qid = record["question_id"]
        errors.extend(f"{qid}: {error.message}" for error in validator.iter_errors(record))
        if record["question"] != record["normalized_question"]:
            errors.append(f"{qid}: 题干字段不一致")
        for key, compute in [("ordered_hash", ordered_hash), ("permutation_hash", permutation_hash)]:
            if record["provenance"][key] != compute(record):
                errors.append(f"{qid}: {key} 失效")
        if record["answer"] not in record["options"] or any(not v.strip() for v in record["options"].values()):
            errors.append(f"{qid}: 答案或选项不完整")
        used_assets.update(record["image_paths"])
        raw_path = record["provenance"]["raw_file"]
        used_raw.add(raw_path)
        if raw_path not in raw_by_path:
            errors.append(f"{qid}: 缺少原始文件清单项")
        elif record["provenance"]["content_hash"] != raw_by_path[raw_path]["content_hash"]:
            errors.append(f"{qid}: 原始文件哈希与清单不一致")
        used_raw.update(e["raw_file"] for e in record["answer_evidence"] if e.get("raw_file"))
    for relative in used_assets | used_raw:
        target = (base / relative).resolve()
        if not target.is_relative_to(base) or not target.is_file():
            errors.append(f"缺失或越界资源：{relative}")
    for relative, row in raw_by_path.items():
        target = (base / relative).resolve()
        if target.is_relative_to(base) and target.is_file():
            if hashlib.sha256(target.read_bytes()).hexdigest() != row["content_hash"]:
                errors.append(f"原始文件 SHA-256 不符：{relative}")
    for directory, references in [("assets", used_assets), ("raw", used_raw)]:
        actual = {p.relative_to(base).as_posix() for p in (base / directory).iterdir() if p.is_file()}
        errors.extend(f"未引用文件：{p}" for p in sorted(actual - references))
    if set(raw_by_path) != used_raw:
        errors.append("原始文件清单与实际引用集合不一致")
    expected = build_quality_report(records)
    actual = json.loads((base / "reports/summary.json").read_text(encoding="utf-8"))
    if actual != expected:
        errors.append("summary.json 已过期，请重新生成")
    if errors:
        print("\n".join(errors))
        return 1
    print(json.dumps({"records": len(records), "images": len(used_assets),
        "raw_files": len(used_raw), "integrity_errors": 0,
        "note": "完整性检查不代表答案、年份和 OCR 内容已人工验证"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
