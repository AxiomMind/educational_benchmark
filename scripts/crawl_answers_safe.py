import json
import os
import re
import sys
import time
import random
import urllib.request
import urllib.parse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

COOKIE_FILE = "data/xkw_cookies.json"
CACHE_FILE = "data/zujuan_answers_cache.json"
QUESTIONS_FILE = "GAOKAO_BENCH_BATCH_4000/questions.jsonl"
TMP_IMG_DIR = "data/tmp_answer_imgs"
os.makedirs(TMP_IMG_DIR, exist_ok=True)

# 1. 加载解除风控后的最新 VIP Cookie
with open(COOKIE_FILE, "r", encoding="utf-8") as f:
    cookies = json.load(f)

cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
zujuan_token = [c["value"] for c in cookies if c["name"] == "user_token" and "zujuan" in c.get("domain", "")][0]

# 2. 加载本地断点续传缓存
cache = {}
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        print(f">>> 已从本地缓存中加载 {len(cache)} 道题目的答案解析记录。")
    except Exception as e:
        print(f"读取缓存警告: {e}")

# 3. 单题安全抓取函数（带随机温和延时，杜绝风控）
def get_answer_for_qid(source_qid):
    if str(source_qid) in cache:
        return str(source_qid), cache[str(source_qid)]

    # 温和延时：模拟人工操作节奏（1.0 ~ 1.8 秒随机）
    time.sleep(random.uniform(1.0, 1.8))

    post_data = urllib.parse.urlencode({"quesId": str(source_qid), "bankId": 17}).encode("utf-8")
    req = urllib.request.Request(
        "https://zujuan.xkw.com/zujuan-api/check_ques_parse",
        data=post_data,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Cookie": cookie_str,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"https://zujuan.xkw.com/17q{source_qid}.html"
        }
    )

    key = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                resp_text = resp.read().decode("utf-8")
                if "安全验证" in resp_text or "lockId" in resp_text:
                    print(f"\n[⚠️ 风控预警] 题目 {source_qid} 触发安全验证，请暂停或稍候重试！")
                    return str(source_qid), None
                res = json.loads(resp_text)
                key = res.get("key")
                if key:
                    break
        except Exception:
            time.sleep(2)

    if not key:
        return str(source_qid), None

    # Step B: 下载答案与解析原图
    img_url = f"https://imzujuan.xkw.com/getAnswerAndParse/{source_qid}/17/{key}?enVqdWFu={zujuan_token}&width=884"
    req_img = urllib.request.Request(
        img_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": "https://zujuan.xkw.com/"
        }
    )

    img_bytes = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req_img, timeout=12) as resp:
                img_bytes = resp.read()
                if len(img_bytes) > 1000:
                    break
        except Exception:
            time.sleep(2)

    if not img_bytes:
        return str(source_qid), None

    # Step C: Tesseract 本地 OCR 识别
    tmp_path = os.path.join(TMP_IMG_DIR, f"{source_qid}.png")
    with open(tmp_path, "wb") as fp:
        fp.write(img_bytes)

    wsl_img_path = f"/mnt/c/Users/26730/educational_benchmark/data/tmp_answer_imgs/{source_qid}.png"
    ocr_cmd = ["wsl.exe", "tesseract", wsl_img_path, "stdout", "-l", "chi_sim"]
    ocr_proc = subprocess.run(ocr_cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    ocr_text = ocr_proc.stdout.strip()

    try:
        os.remove(tmp_path)
    except Exception:
        pass

    # Step D: 多模式正则提取选项
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

    ans = ""
    for p in patterns:
        m = re.findall(p, ocr_text)
        if m:
            ans = m[-1]
            break

    explanation = ocr_text.replace("\r", "").strip()

    record = {
        "source_qid": str(source_qid),
        "answer": ans,
        "explanation": explanation
    }
    return str(source_qid), record

def main():
    max_count = int(sys.argv[1]) if len(sys.argv) > 1 else None

    # 读取目标题目
    targets = []
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            if item.get("source", {}).get("source_id") == "ZUJUAN_XKW":
                m = re.search(r"题号:\s*(\d+)", item.get("quality", {}).get("notes", ""))
                if m:
                    targets.append((item["question_id"], m.group(1)))

    if max_count:
        targets = targets[:max_count]

    to_fetch = [t[1] for t in targets if t[1] not in cache]
    print(f">>> 目标题目总数: {len(targets)} 道，已缓存: {len(cache)} 道，待抓取: {len(to_fetch)} 道")

    if not to_fetch:
        print(">>> 🎉 所有目标题目均已抓取完毕！")
        return

    # 温和安全模式：2 个并发工作线程
    completed = 0
    success = 0

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(get_answer_for_qid, qid): qid for qid in to_fetch}
        for fut in as_completed(futures):
            qid = futures[fut]
            try:
                res_qid, res_data = fut.result()
                if res_data and res_data.get("answer"):
                    cache[res_qid] = res_data
                    success += 1
                elif res_data:
                    cache[res_qid] = res_data
                    print(f"提示: 题目 {res_qid} 提取到解析但未匹配到明显选项字母 (OCR首句: {res_data['explanation'][:30]}...)")
                else:
                    print(f"警告: 题目 {res_qid} 抓取无数据！")
            except Exception as e:
                print(f"抓取题目 {qid} 异常: {e}")

            completed += 1

            if completed % 20 == 0 or completed == len(to_fetch):
                print(f"进度: [{completed}/{len(to_fetch)}] 成功: {success} 道 (有效率 {success/completed*100:.1f}%) | 缓存累计: {len(cache)} 道")
                with open(CACHE_FILE, "w", encoding="utf-8") as fp:
                    json.dump(cache, fp, ensure_ascii=False, indent=2)

    # 最终保存
    with open(CACHE_FILE, "w", encoding="utf-8") as fp:
        json.dump(cache, fp, ensure_ascii=False, indent=2)

    print(f"\n>>> 本轮抓取完成！当前缓存总题数: {len(cache)} 道")

if __name__ == "__main__":
    main()
