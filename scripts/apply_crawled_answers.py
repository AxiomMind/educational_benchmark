import json
import os
import re

QUESTIONS_FILE = "GAOKAO_BENCH_BATCH_4000/questions.jsonl"
CACHE_FILE = "data/zujuan_answers_cache.json"

if not os.path.exists(CACHE_FILE):
    print("错误: 缓存文件不存在！")
    exit(1)

with open(CACHE_FILE, "r", encoding="utf-8") as f:
    cache = json.load(f)

print(f">>> 成功加载答案缓存: {len(cache)} 条记录。")

updated_records = []
filled_count = 0
missing_count = 0

with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
    for line in f:
        item = json.loads(line)
        if item.get("source", {}).get("source_id") == "ZUJUAN_XKW":
            m = re.search(r"题号:\s*(\d+)", item.get("quality", {}).get("notes", ""))
            if m:
                sqid = m.group(1)
                cached = cache.get(sqid)
                if cached and cached.get("answer"):
                    ans = cached["answer"]
                    exp = cached.get("explanation", "").strip()
                    item["answer"] = ans
                    item["answer_explanation"] = exp
                    item["quality"]["answer_status"] = "single_source"
                    item["quality"]["parse_status"] = "parsed"

                    # 关联证据链
                    raw_file_ref = item.get("provenance", {}).get("raw_file") or item.get("source_records", [{}])[0].get("raw_file", "")
                    item["answer_evidence"] = [
                        {
                            "source_id": "ZUJUAN_XKW",
                            "answer": ans,
                            "official": False,
                            "reliable": True,
                            "evidence_url": f"https://zujuan.xkw.com/17q{sqid}.html",
                            "raw_file": raw_file_ref,
                            "page_number": None,
                            "source_question_number": sqid,
                            "raw_answer": f"答案：{ans}"
                        }
                    ]
                    filled_count += 1
                else:
                    missing_count += 1
            else:
                missing_count += 1
        updated_records.append(item)

print(f">>> 回填完成！成功补充答案与解析: {filled_count} 题，仍缺失: {missing_count} 题。")

with open(QUESTIONS_FILE, "w", encoding="utf-8") as f:
    for item in updated_records:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

print(f">>> 已写入最新数据至 {QUESTIONS_FILE}！")
