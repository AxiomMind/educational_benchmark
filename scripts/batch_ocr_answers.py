import json
import os
import re
import sys
import time
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

IMG_DIR = "data/answer_images"
CACHE_FILE = "data/zujuan_answers_cache.json"

# 加载现有缓存
cache = {}
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        print(f">>> 已加载缓存: {len(cache)} 条记录。")
    except Exception as e:
        print(f"读取缓存警告: {e}")

patterns = [
    r"故选\s*([A-D])\s*项",
    r"【答案】\s*([A-D])",
    r"答案[：:\s]*([A-D])",
    r"([A-D])\s*项正确",
    r"正确答案[：:\s]*([A-D])",
    r"故选\s*([A-D])",
    r"本题选\s*([A-D])",
    r"故答案为\s*([A-D])",
    r"所以选\s*([A-D])",
    r"故选：?\s*([A-D])"
]

def ocr_single_image(qid):
    wsl_img_path = f"/mnt/c/Users/26730/educational_benchmark/data/answer_images/{qid}.png"
    ocr_cmd = ["wsl.exe", "tesseract", wsl_img_path, "stdout", "-l", "chi_sim"]
    ocr_proc = subprocess.run(ocr_cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    ocr_text = ocr_proc.stdout.strip()

    ans = ""
    for p in patterns:
        m = re.findall(p, ocr_text)
        if m:
            ans = m[-1]
            break

    exp = ocr_text.replace("\r", "").strip()

    return qid, {
        "source_qid": str(qid),
        "answer": ans,
        "explanation": exp
    }

def main():
    if not os.path.exists(IMG_DIR):
        print(f"错误: 目录 {IMG_DIR} 不存在！")
        return

    all_images = [f.split(".")[0] for f in os.listdir(IMG_DIR) if f.endswith(".png")]
    to_ocr = [qid for qid in all_images if qid not in cache or not cache[qid].get("answer")]

    print(f">>> 本地图片总数: {len(all_images)} 张，已识别: {len(cache)} 张，待 OCR: {len(to_ocr)} 张")

    if not to_ocr:
        print(">>> 🎉 所有已下载的图片均已完成 OCR，无需重复识别！")
        return

    completed = 0
    success = 0
    t0 = time.time()

    # 本地 6 线程并行离线 OCR（零网络请求、零服务器压力）
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(ocr_single_image, qid): qid for qid in to_ocr}
        for fut in as_completed(futures):
            qid = futures[fut]
            try:
                res_qid, res_data = fut.result()
                if res_data and res_data.get("answer"):
                    cache[res_qid] = res_data
                    success += 1
                elif res_data and res_data.get("explanation"):
                    cache[res_qid] = res_data
            except Exception as e:
                print(f"OCR 题目 {qid} 异常: {e}")

            completed += 1

            if completed % 25 == 0 or completed == len(to_ocr):
                speed = completed / (time.time() - t0)
                print(f"OCR 进度: [{completed}/{len(to_ocr)}] 成功提取答案: {success} 道 ({success/completed*100:.1f}%) | 速度: {speed:.1f} 张/秒")
                with open(CACHE_FILE, "w", encoding="utf-8") as fp:
                    json.dump(cache, fp, ensure_ascii=False, indent=2)

    with open(CACHE_FILE, "w", encoding="utf-8") as fp:
        json.dump(cache, fp, ensure_ascii=False, indent=2)

    print(f"\n>>> 批量 OCR 全部完成！当前缓存总数: {len(cache)} 道，耗时: {(time.time()-t0):.1f} 秒。")

if __name__ == "__main__":
    main()
