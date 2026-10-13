import json
import os
import re
import sys
import time
import random
import urllib.request
import urllib.parse

COOKIE_FILE = "data/xkw_cookies.json"
IMG_DIR = "data/answer_images"
QUESTIONS_FILE = "GAOKAO_BENCH_BATCH_4000/questions.jsonl"
os.makedirs(IMG_DIR, exist_ok=True)

# 1. 加载 Cookie 与 Token
with open(COOKIE_FILE, "r", encoding="utf-8") as f:
    cookies = json.load(f)

cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
zujuan_token = [c["value"] for c in cookies if c["name"] == "user_token" and "zujuan" in c.get("domain", "")][0]

def fetch_single_image(qid):
    out_path = os.path.join(IMG_DIR, f"{qid}.png")
    if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
        return True, "already_exists"

    # Step A: POST check_ques_parse
    post_data = urllib.parse.urlencode({"quesId": str(qid), "bankId": 17}).encode("utf-8")
    req = urllib.request.Request(
        "https://zujuan.xkw.com/zujuan-api/check_ques_parse",
        data=post_data,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Cookie": cookie_str,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"https://zujuan.xkw.com/17q{qid}.html"
        }
    )

    key = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                resp_text = resp.read().decode("utf-8")
                if "安全验证" in resp_text or "lockId" in resp_text:
                    print(f"\n[⚠️ 触发验证] 题目 {qid} 触发安全验证，请在浏览器中完成验证！")
                    return False, "risk_alert"
                res = json.loads(resp_text)
                key = res.get("key")
                if key:
                    break
        except Exception:
            time.sleep(1.5)

    if not key:
        return False, "no_key"

    # Step B: GET image
    img_url = f"https://imzujuan.xkw.com/getAnswerAndParse/{qid}/17/{key}?enVqdWFu={zujuan_token}&width=884"
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
            time.sleep(1.5)

    if not img_bytes or len(img_bytes) < 1000:
        return False, "bad_image"

    with open(out_path, "wb") as fp:
        fp.write(img_bytes)

    return True, "downloaded"

def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None

    # 提取所有组卷网题目的源 QID
    targets = []
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            if item.get("source", {}).get("source_id") == "ZUJUAN_XKW":
                m = re.search(r"题号:\s*(\d+)", item.get("quality", {}).get("notes", ""))
                if m:
                    targets.append(m.group(1))

    existing = set([f.split(".")[0] for f in os.listdir(IMG_DIR) if f.endswith(".png") and os.path.getsize(os.path.join(IMG_DIR, f)) > 1000])
    to_download = [t for t in targets if t not in existing]

    print(f">>> 题目总数: {len(targets)} 道，已下载原图: {len(existing)} 道，待下载: {len(to_download)} 道")

    if limit:
        to_download = to_download[:limit]
        print(f">>> 本轮执行上限: {limit} 道")

    if not to_download:
        print(">>> 🎉 所有原图已全部下载完毕！")
        return

    success_count = 0
    fail_count = 0
    t0 = time.time()

    for idx, qid in enumerate(to_download, 1):
        ok, reason = fetch_single_image(qid)
        if ok:
            success_count += 1
        else:
            fail_count += 1
            if reason == "risk_alert":
                print("\n>>> 安全机制触发，下载器自动暂停退出以保护账号！")
                break

        # 进度输出
        if idx % 10 == 0 or idx == len(to_download):
            speed = idx / (time.time() - t0)
            print(f"进度: [{idx}/{len(to_download)}] 成功: {success_count} | 失败: {fail_count} | 速度: {speed:.1f} 题/秒 | 预估剩余: {(len(to_download)-idx)/max(speed, 0.1)/60:.1f} 分钟")

    # 模拟人类教师翻页查看节奏（1.0 ~ 1.5 秒）
    time.sleep(random.uniform(1.0, 1.5))

    # 每 50 题稍微停顿 4 秒（模拟翻卷或看题）
    if idx % 50 == 0 and idx != len(to_download):
        time.sleep(random.uniform(3.0, 5.0))

    print(f"\n>>> 本轮下载结束！共下载成功: {success_count} 张原图，耗时: {(time.time()-t0)/60:.1f} 分钟。")

if __name__ == "__main__":
    main()
