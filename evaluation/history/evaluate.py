"""Run paired Direct / CoT evaluation through a Chat Completions compatible API."""

import argparse
import base64
from collections import Counter, defaultdict
from datetime import datetime, timezone
import getpass
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parent
LETTERS = "ABCD"
MODES = ("direct", "cot")
ANSWER_LINE = re.compile(r"答案\s*:\s*([ABCD])", re.IGNORECASE)
RESERVED = {
    "model", "messages", "stream", "n", "tools", "tool_choice", "functions",
    "function_call", "api_key", "response_format",
}


def encode(data):
    return json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_items(path):
    items = []
    seen = set()
    with path.open(encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            qid = row.get("question_id")
            stem = row.get("question")
            options = row.get("options")
            if (not isinstance(qid, str) or not qid or qid in seen
                    or not isinstance(stem, str) or not stem.strip()
                    or not isinstance(options, dict) or set(options) != set(LETTERS)
                    or any(not isinstance(value, str) or not value.strip() for value in options.values())
                    or ("answer" in row and row["answer"] not in set(LETTERS))
                    or not isinstance(row.get("shared_material", ""), str)
                    ):
                raise ValueError(f"第 {line_number} 行不是有效且唯一的四选一题")
            image_references(row)
            seen.add(qid)
            items.append(row)
    if not items:
        raise ValueError("数据集为空")
    return items


def image_references(row):
    paths = row.get("image_paths", [])
    hashes = row.get("image_sha256", [])
    if (not isinstance(paths, list) or not isinstance(hashes, list) or len(paths) != len(hashes)
            or (row.get("has_image") and not paths)):
        raise ValueError(f"{row['question_id']} 的图片和指纹清单不匹配")
    for path, digest in zip(paths, hashes):
        if (not isinstance(path, str) or not re.fullmatch(r"images/[A-Za-z0-9_.-]+\.(png|jpg|jpeg)", path)
                or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)):
            raise ValueError(f"{row['question_id']} 的图片路径或指纹无效")
    return list(zip(paths, hashes))


def read_image(root, path, digest):
    image_path = (root / path).resolve()
    if not image_path.is_relative_to(root.resolve()):
        raise ValueError(f"图片路径超出数据目录 {path}")
    data = image_path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f"图片指纹不匹配 {path}")
    return data


def question_messages(prompt, row):
    parts = []
    if row.get("shared_material", "").strip():
        parts.append("材料：\n" + row["shared_material"])
    parts.extend(("题目：\n" + row["question"],
                  "\n".join(f"{letter}. {row['options'][letter]}" for letter in LETTERS)))
    text = "\n\n".join(parts)
    refs = image_references(row)
    content = text
    if refs:
        content = [{"type": "text", "text": text}]
        content.extend({"type": "image_ref", "path": path, "sha256": digest} for path, digest in refs)
    return [{"role": "system", "content": prompt}, {"role": "user", "content": content}]


def api_messages(messages, image_root, model):
    content = messages[1]["content"]
    if isinstance(content, str):
        return messages
    blocks = []
    for block in content:
        if block["type"] == "text":
            blocks.append(block)
            continue
        path = block["path"]
        encoded = base64.b64encode(read_image(image_root, path, block["sha256"])).decode("ascii")
        media_type = "image/png" if path.endswith(".png") else "image/jpeg"
        # 这两款智谱视觉模型的接口示例使用不带 MIME 前缀的 Base64。
        url = encoded if model in {"glm-4.6v-flash", "glm-4.6v"} else f"data:{media_type};base64,{encoded}"
        blocks.append({"type": "image_url", "image_url": {"url": url}})
    return [messages[0], {"role": "user", "content": blocks}]


def extract_answer(text, mode):
    lines = [line.strip() for line in unicodedata.normalize("NFKC", text).splitlines()
             if line.strip()]
    if not lines or (mode == "direct" and len(lines) != 1) or (mode == "cot" and len(lines) < 2):
        return None
    match = ANSWER_LINE.fullmatch(lines[-1])
    if not match or any(ANSWER_LINE.fullmatch(line) for line in lines[:-1]):
        return None
    return match[1].upper()


def load_config(path):
    if path is None:
        raise ValueError("正式运行需要 --config；请使用组员包中对应模型的配置")
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    endpoint = urlsplit(config["endpoint"])
    if (not endpoint.hostname or endpoint.username or endpoint.password
            or endpoint.query or endpoint.fragment
            or (endpoint.scheme != "https" and (
                endpoint.scheme != "http" or endpoint.hostname not in {"127.0.0.1", "localhost", "::1"}
            ))
            or not endpoint.path.rstrip("/").endswith("/chat/completions")):
        raise ValueError("endpoint 需要填写完整的 HTTPS Chat Completions 地址。本机模拟允许 HTTP")
    model = config["model"]
    if not isinstance(model, str) or not model.strip() or model.startswith("REPLACE_"):
        raise ValueError("model 需要填写服务商提供的真实模型 ID")
    env_name = config.get("api_key_env", "CHISEVAL_API_KEY")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", env_name):
        raise ValueError("api_key_env 填环境变量名")
    parameters = config.get("parameters", {})
    if not isinstance(parameters, dict) or RESERVED.intersection(parameters):
        raise ValueError("parameters 中只能填写模型的生成参数")
    for key in ("max_tokens", "max_completion_tokens"):
        if key in parameters and (type(parameters[key]) is not int or parameters[key] < 1):
            raise ValueError(f"{key} 必须为正整数")
    if {"max_tokens", "max_completion_tokens"} <= set(parameters):
        raise ValueError("只配置服务商接受的一种输出长度字段")
    timeout = config.get("timeout_seconds", 60)
    interval = config.get("min_interval_seconds", 0.5)
    retries = config.get("retries", 2)
    if (not all(type(value) in (int, float) and math.isfinite(value) for value in (timeout, interval))
            or timeout <= 0 or interval < 0 or type(retries) is not int or not 0 <= retries <= 5):
        raise ValueError("检查超时、最短调用间隔及重试次数配置")
    return config["endpoint"], model, env_name, parameters, timeout, interval, retries


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def api_attempt(opener, endpoint, key, payload, timeout):
    request = Request(endpoint, data=encode(payload).encode(),
                      headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
                      method="POST")
    started = time.monotonic()
    attempt = {"retryable": False, "started_at_utc": datetime.now(timezone.utc).isoformat()}
    try:
        with opener.open(request, timeout=timeout) as response:
            data = json.load(response)
        if not isinstance(data, dict) or "error" in data:
            attempt["error"] = "invalid_or_error_response"
        else:
            choices = data.get("choices")
            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                attempt["response"] = data
            else:
                attempt["error"] = "missing_choices"
    except HTTPError as error:
        with error:
            attempt.update(error=f"http_{error.code}", http_status=error.code,
                           retryable=error.code in {408, 429, 500, 502, 503, 504})
            retry_after = error.headers.get("Retry-After", "")
            if retry_after.isdecimal():
                attempt["retry_after_seconds"] = int(retry_after)
    except (URLError, TimeoutError, ConnectionError, http.client.HTTPException):
        attempt.update(error="connection_or_timeout", retryable=True)
    except (ValueError, UnicodeError):
        attempt["error"] = "invalid_response_json"
    attempt["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return attempt


def score_response(response, mode, gold):
    choice = response["choices"][0]
    message = choice.get("message")
    message = message if isinstance(message, dict) else {}
    reason = choice.get("finish_reason")
    content = message.get("content")
    prediction = None
    if reason in {"length", "max_tokens"}:
        status = "truncated"
    elif reason in {"content_filter", "safety"} or message.get("refusal"):
        status = "refused"
    else:
        prediction = extract_answer(content, mode) if isinstance(content, str) else None
        if prediction is None:
            status = "format_error"
        elif gold is None:
            status = "answered"
        else:
            status = "correct" if prediction == gold else "incorrect"
    return {"status": status, "prediction": prediction, "finish_reason": reason,
            "usage": response.get("usage"), "response_model": response.get("model"),
            "native_reasoning_present": bool(message.get("reasoning_content"))}


def write_output(path, content):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)


def summary_metrics(cases, results):
    counts = Counter(row["status"] for row in results)
    valid = counts["correct"] + counts["incorrect"]
    attempted = len(results)
    return {
        "planned": cases, "attempted": attempted, "pending": cases - attempted,
        "statuses": dict(counts),
        "accuracy_over_attempted": (
            counts["correct"] / attempted
            if attempted and all(row.get("gold") in set(LETTERS) for row in results) else None
        ),
        "accuracy_valid_answers_only": counts["correct"] / valid if valid else None,
    }


def build_summary(items, modes, results):
    per_condition = {}
    ability_counts = Counter(row.get("ai_primary_ability") or "unlabeled" for row in items)
    for mode in modes:
        subset = [row for row in results if row["mode"] == mode]
        per_condition[mode] = summary_metrics(len(items), subset)
        per_condition[mode]["by_initial_ability"] = {
            label: summary_metrics(n, [row for row in subset if row["ai_primary_ability"] == label])
            for label, n in sorted(ability_counts.items())
        }
    paired = defaultdict(dict)
    transitions = Counter()
    for row in results:
        paired[row["question_id"]][row["mode"]] = row["status"]
    comparable = {"correct", "incorrect"}
    for pair in paired.values():
        if pair.get("direct") in comparable and pair.get("cot") in comparable:
            transitions[f"{pair['direct']}_to_{pair['cot']}"] += 1
    n_pairs = sum(transitions.values())
    usage = Counter()
    for result in results:
        data = result.get("usage")
        if isinstance(data, dict):
            for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
                if type(data.get(name)) is int:
                    usage[name] += data[name]
    return {
        "by_condition": per_condition,
        "paired_valid_answers": n_pairs,
        "transitions": dict(transitions),
        "paired_cot_minus_direct": (
            (transitions["incorrect_to_correct"] - transitions["correct_to_incorrect"]) / n_pairs
            if n_pairs else None
        ),
        "reported_usage": dict(usage),
        "response_models": sorted({str(row["response_model"]) for row in results
                                   if row.get("response_model")}),
        "native_reasoning_responses": sum(bool(row.get("native_reasoning_present")) for row in results),
    }


def execute(args, items, modes, prompts):
    endpoint, model, env_name, params, timeout, interval, retries = load_config(args.config)
    key = os.environ.get(env_name, "").strip()
    if not key and sys.stdin.isatty():
        key = getpass.getpass(f"{env_name}（输入不回显）：").strip()
    if not key:
        raise ValueError(f"请设置 {env_name} 或在交互终端输入 API Key")

    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "runner_version": 1, "dataset_sha256": file_hash(args.data),
        "question_ids": [row["question_id"] for row in items],
        "modes": modes, "endpoint": endpoint, "model": model, "parameters": params,
        "prompts": {mode: hashlib.sha256(prompts[mode].encode()).hexdigest() for mode in modes},
    }
    manifest_text = json.dumps(manifest, ensure_ascii=False, sort_keys=True, allow_nan=False)
    db = sqlite3.connect(args.output / "checkpoint.sqlite3", timeout=0)
    opener = build_opener(NoRedirect)
    calls = 0
    last_call = 0.0
    stopped = None
    consecutive_api_errors = 0
    ready = False
    retry_statuses = {"api_error"}
    if args.limit == 2:
        retry_statuses.update(("format_error", "refused", "truncated"))
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS run (id INTEGER PRIMARY KEY, manifest TEXT NOT NULL)")
            db.execute("""CREATE TABLE IF NOT EXISTS results (
                       question_id TEXT, mode TEXT, data TEXT NOT NULL,
                       PRIMARY KEY (question_id, mode))""")
            existing = db.execute("SELECT manifest FROM run WHERE id=1").fetchone()
            if existing and existing[0] != manifest_text:
                raise ValueError("输出目录已绑定其他题集、模式、提示词或模型配置，请换目录")
            db.execute("INSERT OR IGNORE INTO run VALUES (1, ?)", (manifest_text,))
        ready = True
        for row in items:
            for mode in modes:
                with db:
                    db.execute("BEGIN IMMEDIATE")
                    qid = row["question_id"]
                    previous = db.execute("SELECT data FROM results WHERE question_id=? AND mode=?",
                                          (qid, mode)).fetchone()
                    prior = json.loads(previous[0]) if previous else None
                    if prior and (not args.retry_failed or prior["status"] not in retry_statuses):
                        continue
                    if args.max_calls is not None and calls >= args.max_calls:
                        stopped = "已达到本次调用次数上限"
                        break
                    messages = question_messages(prompts[mode], row)
                    payload = dict(params, model=model, stream=False,
                                   messages=api_messages(messages, args.data.parent, model))
                    attempts = list(prior["attempts"]) if prior else []
                    for i in range(retries + 1):
                        remaining = interval - (time.monotonic() - last_call)
                        if remaining > 0:
                            time.sleep(remaining)
                        last_call = time.monotonic()
                        calls += 1
                        attempt = api_attempt(opener, endpoint, key, payload, timeout)
                        response = attempt.pop("response", None)
                        attempts.append(attempt)
                        if response is not None or not attempt["retryable"]:
                            break
                        if i == retries or (args.max_calls is not None and calls >= args.max_calls):
                            break
                        delay = attempt.get("retry_after_seconds", 2 ** i)
                        if delay > 60:
                            break
                        time.sleep(delay)
                    score = (score_response(response, mode, row.get("answer")) if response is not None
                             else {"status": "api_error", "prediction": None, "usage": None})
                    result = {
                        "question_id": qid, "mode": mode, "model": model,
                        "source_id": row.get("source_id"),
                        "ai_primary_ability": row.get("ai_primary_ability") or "unlabeled",
                        "gold": row.get("answer"), "messages": messages, **score,
                        "attempts": attempts, "raw_response": response,
                    }
                    db.execute("INSERT OR REPLACE INTO results VALUES (?, ?, ?)",
                               (qid, mode, encode(result)))
                print(f"{qid} {mode} {result['status']}", flush=True)
                consecutive_api_errors = consecutive_api_errors + 1 if response is None else 0
                if attempt.get("http_status") in {400, 401, 402, 403, 404, 422}:
                    stopped = f"服务返回 {attempt['error']}，请检查 API 配置和模型参数"
                    break
                if response is None and attempt.get("retry_after_seconds", 0) > 60:
                    stopped = f"服务返回限流，请至少等待 {attempt['retry_after_seconds']} 秒后续跑"
                    break
                if consecutive_api_errors >= 5:
                    stopped = "服务返回连续接口错误，暂停运行。排查后用 --retry-failed 续跑。"
                    break
            if stopped:
                break
    except KeyboardInterrupt:
        stopped = "运行已中断，可以用相同命令续跑"
    finally:
        try:
            if ready:
                with db:
                    db.execute("BEGIN IMMEDIATE")
                    results = [json.loads(value) for (value,) in db.execute(
                        "SELECT data FROM results ORDER BY question_id, mode"
                    )]
                    write_output(args.output / "run.json", manifest_text + "\n")
                    write_output(args.output / "results.jsonl", "".join(encode(row) + "\n" for row in results))
                    report = build_summary(items, modes, results)
                    report.update(calls_this_invocation=calls, stop_reason=stopped)
                    write_output(args.output / "summary.json", json.dumps(
                        report, ensure_ascii=False, indent=2
                    ) + "\n")
        finally:
            db.close()
    if stopped:
        print(stopped, file=sys.stderr)
    print(f"本次请求 {calls} 次。逐题结果及汇总写入 {args.output}")
    return 1 if stopped and stopped.startswith("服务返回") else 0


def positive_int(value):
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("应为正整数")
    return result


def main():
    parser = argparse.ArgumentParser(description="运行 CHisEval 图文历史单选题 Direct / CoT 评测")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "eval_inputs.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "full")
    parser.add_argument("--mode", choices=(*MODES, "both"), default="both")
    parser.add_argument("--limit", type=positive_int, help="取前 N 题试跑")
    parser.add_argument("--max-calls", type=positive_int, help="本次调用上限，含重试")
    parser.add_argument("--retry-failed", action="store_true", help="重跑 API 失败项，两题试跑也重跑未产出有效答案的记录")
    parser.add_argument("--dry-run", action="store_true", help="预览首题输入及调用规模")
    args = parser.parse_args()
    try:
        items = load_items(args.data)[:args.limit]
        modes = list(MODES) if args.mode == "both" else [args.mode]
        prompts = {mode: (ROOT / "prompts" / f"{mode}.txt").read_text(encoding="utf-8").strip()
                   for mode in modes}
        for row in items:
            for path, digest in image_references(row):
                read_image(args.data.parent, path, digest)
        if args.dry_run:
            image_questions = sum(bool(row.get("image_paths")) for row in items)
            print(json.dumps({"questions": len(items), "image_questions": image_questions,
                              "planned_calls_without_retries": len(items) * len(modes),
                              "examples": {row["question_id"]: {
                                  mode: question_messages(prompts[mode], row) for mode in modes
                              } for row in items[:2]}}, ensure_ascii=False, indent=2))
            return 0
        return execute(args, items, modes, prompts)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, sqlite3.Error) as error:
        print(f"运行失败（{type(error).__name__}）{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
