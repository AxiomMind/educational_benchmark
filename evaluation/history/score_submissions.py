"""在协调端核对组员交回的原始响应，并用本地参考答案统一评分。"""

import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import sys

from evaluate import MODES, file_hash, image_references, load_items, question_messages, read_image, score_response


ROOT = Path(__file__).resolve().parent


def read_jsonl(path):
    with path.open(encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def wilson_interval(correct, n):
    if not n:
        return None
    z = 1.959963984540054
    p = correct / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return [center - half, center + half]


def paired_stats(pairs):
    if not pairs:
        return {"pairs": 0, "delta": None, "bootstrap_95_interval": None, "mcnemar_exact_p": None}
    transitions = Counter((left["status"], right["status"]) for left, right in pairs)
    changes = [int(right["status"] == "correct") - int(left["status"] == "correct")
               for left, right in pairs]
    rng = random.Random(20261113)
    boot = sorted(sum(rng.choices(changes, k=len(changes))) / len(changes) for _ in range(2000))
    improved = sum(change == 1 for change in changes)
    degraded = sum(change == -1 for change in changes)
    discordant = improved + degraded
    p_value = (min(1.0, 2 * sum(math.comb(discordant, k)
                               for k in range(min(improved, degraded) + 1)) / (2 ** discordant))
               if discordant else 1.0)
    return {
        "pairs": len(pairs), "delta": sum(changes) / len(changes),
        "bootstrap_95_interval": [boot[49], boot[1949]],
        "mcnemar_exact_p": p_value,
        "improved": improved, "degraded": degraded,
        "both_correct": transitions["correct", "correct"],
        "both_incorrect_or_failed": sum(
            left["status"] != "correct" and right["status"] != "correct" for left, right in pairs
        ),
    }


def load_run(folder, items, inputs_path, prompts):
    manifest = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    if manifest["dataset_sha256"] != file_hash(inputs_path):
        raise ValueError(f"{folder} 使用的数据文件指纹与组员版开发集不同")
    if manifest["modes"] != list(MODES):
        raise ValueError(f"{folder} 需要同时包含 Direct 和 CoT 条件")
    ids = manifest["question_ids"]
    if len(ids) != len(set(ids)) or not ids or not set(ids) <= set(items):
        raise ValueError(f"{folder} 的题号清单无效")
    for mode in MODES:
        expected_hash = hashlib.sha256(prompts[mode].encode()).hexdigest()
        if manifest["prompts"][mode] != expected_hash:
            raise ValueError(f"{folder} 的 {mode} 提示词指纹不同")
    seen = set()
    scored = {}
    for response in read_jsonl(folder / "results.jsonl"):
        qid, mode = response["question_id"], response["mode"]
        key = qid, mode
        if key in seen or qid not in ids or mode not in MODES:
            raise ValueError(f"{folder} 有重复或未计划的结果 {key}")
        if response["model"] != manifest["model"]:
            raise ValueError(f"{folder} 有模型配置不一致的结果")
        if response["messages"] != question_messages(prompts[mode], items[qid]):
            raise ValueError(f"{folder} 的 {qid}/{mode} 实际输入与标准输入不同")
        seen.add(key)
        raw = response.get("raw_response")
        score = (score_response(raw, mode, items[qid]["answer"]) if raw is not None
                 else {"status": "api_error", "prediction": None, "usage": None})
        scored[key] = {
            **response, **score,
            "gold": items[qid]["answer"],
            "ai_primary_ability": items[qid]["ai_primary_ability"],
            "ability_label": items[qid].get("primary_ability") or items[qid]["ai_primary_ability"],
            "source_id": items[qid]["source_id"],
            "knowledge_module": items[qid].get("knowledge_module"),
            "knowledge_module_method": items[qid].get("knowledge_module_method"),
            "ability_label_method": items[qid].get("ability_label_method"),
            "split_cluster": items[qid].get("split_cluster"),
        }
    return manifest, scored


def summarize_group(scored, ids):
    result = {}
    for mode in MODES:
        responses = [scored[qid, mode] for qid in ids if (qid, mode) in scored]
        statuses = Counter(row["status"] for row in responses)
        correct = statuses["correct"]
        n = len(responses)
        result[mode] = {
            "planned": len(ids), "attempted": n, "pending": len(ids) - n,
            "statuses": statuses, "accuracy_over_attempted": correct / n if n else None,
            "wilson_95_interval": wilson_interval(correct, n),
        }
    pairs = [(scored[qid, "direct"], scored[qid, "cot"]) for qid in ids
             if (qid, "direct") in scored and (qid, "cot") in scored]
    result["paired_including_failures"] = paired_stats(pairs)
    return result, pairs


def summarize(items, scored, ids):
    result, _ = summarize_group(scored, ids)
    result["by_ability_label"] = {}
    for label in ("FACT", "TIME", "SOURCE", "REASON"):
        group = [qid for qid in ids if (items[qid].get("primary_ability") or items[qid]["ai_primary_ability"]) == label]
        entry, _ = summarize_group(scored, group)
        result["by_ability_label"][label] = {"planned_questions": len(group), **entry}

    result["by_modality"] = {}
    for modality in ("text", "image"):
        group = [qid for qid in ids if bool(items[qid].get("image_paths")) == (modality == "image")]
        entry, _ = summarize_group(scored, group)
        result["by_modality"][modality] = {"planned_questions": len(group), **entry}

    result["complete"] = all(result[mode]["pending"] == 0 for mode in MODES)
    if any(items[qid].get("knowledge_module") for qid in ids):
        groups = {}
        for qid in ids:
            module = items[qid].get("knowledge_module") or "未标注"
            groups.setdefault(module, []).append(qid)
        result["by_knowledge_module"] = {
            module: {"planned_questions": len(group), **summarize_group(scored, group)[0]}
            for module, group in groups.items()
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path, help="各组员交回的每个模型的完整运行目录")
    parser.add_argument("--output", type=Path, default=ROOT / "统一评分结果")
    parser.add_argument("--data", type=Path, default=ROOT / "data/eval_key.jsonl")
    parser.add_argument("--knowledge-labels", type=Path,
                        help="按题号合并历史知识板块标签")
    args = parser.parse_args()
    try:
        items = {row["question_id"]: row for row in load_items(args.data)}
        if args.knowledge_labels is not None:
            labels = read_jsonl(args.knowledge_labels)
            ids = [row["question_id"] for row in labels]
            if len(ids) != len(set(ids)) or set(ids) != set(items):
                raise ValueError("历史知识板块标签和题集的题号不一致")
            for label in labels:
                module = label["knowledge_module"]
                if not isinstance(module, str) or not module.strip():
                    raise ValueError(f"{label['question_id']} 的历史知识板块为空")
                items[label["question_id"]].update({
                    key: value for key, value in label.items() if key.startswith("knowledge_module")
                })
        for row in items.values():
            for path, digest in image_references(row):
                read_image(args.data.parent, path, digest)
        prompts = {mode: (ROOT / "prompts" / f"{mode}.txt").read_text(encoding="utf-8").strip()
                   for mode in MODES}
        records, reports, models = [], [], set()
        for folder in args.runs:
            manifest, scored = load_run(folder, items, args.data.with_name("eval_inputs.jsonl"), prompts)
            if manifest["model"] in models:
                raise ValueError("有重复的模型 ID，请核对组员分工")
            models.add(manifest["model"])
            records.extend(scored.values())
            reports.append({
                "folder": str(folder), "model": manifest["model"], "endpoint": manifest["endpoint"],
                "parameters": manifest["parameters"],
                "response_models": sorted({str(row["response_model"]) for row in scored.values()
                                           if row.get("response_model")}),
                "native_reasoning_responses": sum(bool(row.get("native_reasoning_present"))
                                                 for row in scored.values()),
                "registered_question_count": len(manifest["question_ids"]),
                **summarize(items, scored, list(items)),
            })
        # Report all registered models on the same actually completed item pairs.
        all_scored = {
            (row["model"], row["question_id"], row["mode"]): row for row in records
        }
        common_ids = [
            qid for qid in items
            if all((model, qid, mode) in all_scored for model in models for mode in MODES)
        ]
        comparisons = []
        for report in reports:
            model = report["model"]
            pairs = [(all_scored[model, qid, "direct"], all_scored[model, qid, "cot"])
                     for qid in common_ids]
            comparisons.append({"model": model, **paired_stats(pairs)})
        args.output.mkdir(parents=True, exist_ok=False)
        with (args.output / "scored_results.jsonl").open("w", encoding="utf-8") as handle:
            for row in records:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        report = {
            "dataset_sha256": file_hash(args.data), "by_model": reports,
            "knowledge_labels_sha256": (
                file_hash(args.knowledge_labels) if args.knowledge_labels is not None else None
            ),
            "common_completed_question_ids": common_ids,
            "comparison_on_common_pairs": comparisons,
            "label_status": (
                "human_reviewed" if all(row.get("label_review_status") == "human_reviewed" for row in items.values())
                else "AI initial labels pending human review"
            ),
            "interval_scope": "descriptive intervals on this evaluation set; related variants can be correlated",
            "knowledge_module_methods": Counter(row.get("knowledge_module_method", "unknown") for row in items.values()),
            "ability_methods": Counter(row.get("ability_label_method", "unknown") for row in items.values()),
            "knowledge_module_review_statuses": Counter(row.get("knowledge_module_review_status", "unknown") for row in items.values()),
        }
        (args.output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        with (args.output / "error_cases.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            fields = ("model", "question_id", "direct_status", "cot_status",
                      "direct_prediction", "cot_prediction", "gold", "knowledge_module", "ability_label",
                      "question", "error_category", "notes")
            writer = csv.DictWriter(handle, fields)
            writer.writeheader()
            for model in sorted(models):
                for qid in items:
                    left = all_scored.get((model, qid, "direct"))
                    right = all_scored.get((model, qid, "cot"))
                    if left is None or right is None or left["status"] != "correct" or right["status"] != "correct":
                        writer.writerow({
                            "model": model, "question_id": qid,
                            "direct_status": left["status"] if left else "pending",
                            "cot_status": right["status"] if right else "pending",
                            "direct_prediction": left["prediction"] if left else "",
                            "cot_prediction": right["prediction"] if right else "",
                            "gold": items[qid]["answer"], "question": items[qid]["question"],
                            "knowledge_module": items[qid].get("knowledge_module"),
                            "ability_label": items[qid].get("primary_ability") or items[qid]["ai_primary_ability"],
                        })
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"无法汇总。{error}", file=sys.stderr)
        return 1
    print(f"已统一评分 {len(models)} 个模型，共同完成的成对题目 {len(common_ids)} 道。")
    print(f"结果已写入 {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
