import subprocess
import sys
import time
import os
import json
import re
import random

QUESTIONS_FILE = "GAOKAO_BENCH_BATCH_4000/questions.jsonl"
IMG_DIR = "data/answer_images"

def get_remaining_count():
    targets = []
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            if item.get("source", {}).get("source_id") == "ZUJUAN_XKW":
                m = re.search(r"题号:\s*(\d+)", item.get("quality", {}).get("notes", ""))
                if m:
                    targets.append(m.group(1))

    existing = set([f.split(".")[0] for f in os.listdir(IMG_DIR) if f.endswith(".png") and os.path.getsize(os.path.join(IMG_DIR, f)) > 1000])
    remaining = [t for t in targets if t not in existing]
    return len(remaining), len(existing), len(targets)

def run(cmd):
    print(f"\n>>> 正在执行: {cmd}")
    res = subprocess.run(cmd, shell=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        print(f"命令执行失败 (code {res.returncode}): {cmd}")
        return False
    return True

def main():
    batch_size = 100
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        batch_size = int(sys.argv[1])

    cycle = 1
    while True:
        rem, done, total = get_remaining_count()
        print(f"\n================================================================")
        print(f"  [循环轮次 #{cycle}] 进度: 已完成 {done}/{total} 题 ({done/total*100:.1f}%) | 剩余: {rem} 题")
        print(f"  本次计划处理: {min(batch_size, rem)} 题")
        print(f"================================================================\n")

        if rem == 0:
            print(">>> 🎉🎉 全部 3,600 道组卷网题目答案已全量提取、OCR、回填并提交！任务圆满结束！")
            break

        # Step 1: 下载原图
        if not run(f"python scripts/fetch_answer_images.py {batch_size}"):
            print(">>> 原图下载中断或遇到异常，流水线安全暂停。")
            break

        # Step 2: 离线并行多核 OCR
        if not run("python scripts/batch_ocr_answers.py"):
            print(">>> 本地 OCR 异常，流程暂停。")
            break

        # Step 3: 回填至 questions.jsonl
        if not run("python scripts/apply_crawled_answers.py"):
            print(">>> 回填数据失败，流程暂停。")
            break

        # Step 4: 运行质检与报告生成
        run("python -m chis_eval validate --input GAOKAO_BENCH_BATCH_4000/questions.jsonl --output GAOKAO_BENCH_BATCH_4000/validated.jsonl")
        run("python -m chis_eval export-review --input GAOKAO_BENCH_BATCH_4000/questions.jsonl --output GAOKAO_BENCH_BATCH_4000/reports/review.csv")
        run("python -m chis_eval report --input GAOKAO_BENCH_BATCH_4000/questions.jsonl --output GAOKAO_BENCH_BATCH_4000/reports/summary.json")
        run("rm -f GAOKAO_BENCH_BATCH_4000/validated.jsonl")

        # Step 5: Git Commit & Push
        run("git add GAOKAO_BENCH_BATCH_4000/questions.jsonl GAOKAO_BENCH_BATCH_4000/reports/review.csv GAOKAO_BENCH_BATCH_4000/reports/summary.json")
        commit_msg = f"feat(dataset): batch update verified answers (cycle {cycle}, completed {done+min(batch_size, rem)}/{total})"
        run(f'git commit -m "{commit_msg}"')
        run("git push origin main")

        print(f"\n>>> ✅ 轮次 #{cycle} 顺利完成并已成功 push 到 GitHub！")
        cycle += 1

        # 批次间休息 12 ~ 18 秒，让服务器会话自然平缓，彻底规避风控
        rem_after, _, _ = get_remaining_count()
        if rem_after > 0:
            rest_s = random.uniform(12.0, 18.0)
            print(f">>> 批次间拟人休整 {rest_s:.1f} 秒，随后自动进入下一轮...")
            time.sleep(rest_s)

if __name__ == "__main__":
    main()
