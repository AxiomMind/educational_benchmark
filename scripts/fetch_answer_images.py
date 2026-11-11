"""使用本地登录会话下载答案原图，遇到验证或频率限制时停止。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
from chis_eval.storage.jsonl import read_jsonl

ROOT = Path(__file__).resolve().parents[1]


def fetch_image(qid, cookie_header, token):
    request = urllib.request.Request(
        "https://zujuan.xkw.com/zujuan-api/check_ques_parse",
        data=urllib.parse.urlencode({"quesId": qid, "bankId": 17}).encode(),
        headers={"User-Agent": "Mozilla/5.0", "Cookie": cookie_header,
                 "Referer": f"https://zujuan.xkw.com/17q{qid}.html",
                 "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
    if "安全验证" in body or "lockId" in body:
        raise RuntimeError("遇到访问验证，请在浏览器确认会话后手动重试。")
    try:
        key = json.loads(body).get("key")
    except json.JSONDecodeError:
        raise RuntimeError("接口返回非 JSON，请检查登录状态。") from None
    if not key:
        raise RuntimeError("接口未提供答案访问凭证，请检查账号与内容访问权限。")
    url = f"https://imzujuan.xkw.com/getAnswerAndParse/{qid}/17/{urllib.parse.quote(str(key), safe='')}"
    url += "?" + urllib.parse.urlencode({"enVqdWFu": token, "width": 884})
    request = urllib.request.Request(url, headers={"Referer": "https://zujuan.xkw.com/",
                                                  "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        content = response.read()
    if not content.startswith(b"\x89PNG\r\n\x1a\n") or len(content) < 10000:
        raise RuntimeError("响应不是预期的答案 PNG，可能是提示图；停止本轮下载。")
    return content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "datasets/history/questions.jsonl")
    parser.add_argument("--cookies", type=Path, default=ROOT / "data/xkw_cookies.json")
    parser.add_argument("--images", type=Path, default=ROOT / "data/answer_images")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--interval", type=float, default=3.0)
    args = parser.parse_args()
    if args.limit < 1 or args.interval < 2:
        parser.error("limit 必须为正数，interval 至少为 2 秒。")
    if not args.cookies.is_file():
        parser.error("请先运行 node scripts/login.js 保存登录会话。")
    cookies = json.loads(args.cookies.read_text(encoding="utf-8"))
    scoped = [c for c in cookies if c.get("domain", "").lstrip(".")
              in ("xkw.com", "zujuan.xkw.com")]
    token = next((c["value"] for c in scoped if c["name"] == "user_token"
                  and "zujuan" in c.get("domain", "")), None)
    if not token:
        parser.error("会话缺少组卷网 user_token，请重新登录。")
    header = "; ".join(f"{c['name']}={c['value']}" for c in scoped)
    qids = sorted({str(r["provenance"].get("source_question_number", ""))
                   for r in read_jsonl(args.input) if r["source"]["source_id"] == "ZUJUAN_XKW"})
    if any(not qid.isdigit() for qid in qids):
        parser.error("题库存在非法源题号。")
    args.images.mkdir(parents=True, exist_ok=True)
    completed = 0
    for qid in qids:
        destination = args.images / f"{qid}.png"
        if destination.is_file() and destination.stat().st_size >= 10000:
            continue
        try:
            content = fetch_image(qid, header, token)
        except (RuntimeError, urllib.error.URLError, TimeoutError) as exc:
            # 请求 URL 含令牌，只输出错误类别。
            message = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
            print(f"{qid}: 下载停止（{message}）")
            return 2
        destination.write_bytes(content)
        metadata = {"source_question_number": qid, "image": destination.name,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "source_url": f"https://zujuan.xkw.com/17q{qid}.html"}
        with (args.images / "manifest.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(metadata, ensure_ascii=False) + "\n")
        completed += 1
        print(f"已保存 {qid}（本轮 {completed}/{args.limit}）")
        if completed >= args.limit:
            break
        time.sleep(args.interval)
    print(f"本轮完成：{completed} 张。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
