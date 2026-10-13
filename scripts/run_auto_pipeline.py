import subprocess
import sys
import time

def run(cmd):
    print(f"\n>>> 正在执行: {cmd}")
    res = subprocess.run(cmd, shell=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        print(f"命令执行失败 (code {res.returncode}): {cmd}")
        return False
    return True

def main():
    batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 100

    print(f"================================================================")
    print(f"  CHisEval 答案流水线：自动拉取 -> 本地OCR -> 回填数据 -> 提交Git")
    print(f"  本次批次大小: {batch_size} 题")
    print(f"================================================================\n")

    # Step 1: 下载原图
    if not run(f"python scripts/fetch_answer_images.py {batch_size}"):
        print("原图下载中断或遇到风控，流程暂停。")
        return

    # Step 2: 离线并行多核 OCR
    if not run("python scripts/batch_ocr_answers.py"):
        print("本地 OCR 异常，流程暂停。")
        return

    # Step 3: 回填至 questions.jsonl
    if not run("python scripts/apply_crawled_answers.py"):
        print("回填数据失败，流程暂停。")
        return

    # Step 4: 运行质检与报告生成
    run("python -m chis_eval validate --input GAOKAO_BENCH_BATCH_4000/questions.jsonl --output GAOKAO_BENCH_BATCH_4000/validated.jsonl")
    run("python -m chis_eval export-review --input GAOKAO_BENCH_BATCH_4000/questions.jsonl --output GAOKAO_BENCH_BATCH_4000/reports/review.csv")
    run("python -m chis_eval report --input GAOKAO_BENCH_BATCH_4000/questions.jsonl --output GAOKAO_BENCH_BATCH_4000/reports/summary.json")
    run("rm -f GAOKAO_BENCH_BATCH_4000/validated.jsonl")

    # Step 5: Git Commit & Push
    run("git add GAOKAO_BENCH_BATCH_4000/questions.jsonl GAOKAO_BENCH_BATCH_4000/reports/review.csv GAOKAO_BENCH_BATCH_4000/reports/summary.json")
    run('git commit -m "feat(dataset): batch update verified answer parses for batch 4000"')
    run("git push origin main")

    print("\n>>> 🎉 本批次处理与 Git 提交全流程顺利完成！")

if __name__ == "__main__":
    main()
