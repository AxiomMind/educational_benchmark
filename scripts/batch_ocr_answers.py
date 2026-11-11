"""离线 OCR：保留原文与图片哈希，冲突答案留待复核。"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def extract_candidate(text):
    patterns = (
        r"故选[：:\s]*([A-D])", r"【答案】\s*([A-D])",
        r"(?:正确答案|故答案为|本题选|所以选)[：:\s]*([A-D])",
        r"答案[：:\s]+([A-D])", r"([A-D])\s*项正确",
    )
    claims = sorted({a for p in patterns for a in re.findall(p, text)})
    return (claims[0] if len(claims) == 1 else ""), claims


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, default=ROOT / "data/answer_images")
    parser.add_argument("--cache", type=Path, default=ROOT / "data/zujuan_answers_cache.json")
    parser.add_argument("--tesseract", default="tesseract")
    parser.add_argument("--wsl", action="store_true", help="使用 WSL 中的 tesseract")
    parser.add_argument("--language", default="chi_sim+eng")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not args.images.is_dir():
        parser.error(f"图片目录不存在：{args.images}")
    cache = json.loads(args.cache.read_text(encoding="utf-8")) if args.cache.exists() else {}
    args.cache.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    for image in sorted(args.images.glob("*.png")):
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        if not args.force and cache.get(image.stem, {}).get("image_sha256") == digest:
            continue
        image_arg = str(image.resolve())
        command = [args.tesseract]
        if args.wsl:
            image_arg = subprocess.run(["wsl.exe", "wslpath", "-a", "-u", image_arg],
                capture_output=True, text=True, check=True).stdout.strip()
            command = ["wsl.exe", args.tesseract]
        result = subprocess.run(
            command + [image_arg, "stdout", "-l", args.language, "--psm", "6"],
            capture_output=True, text=True, encoding="utf-8", check=True, timeout=180)
        text = result.stdout.strip()
        answer, claims = extract_candidate(text)
        cache[image.stem] = {"source_qid": image.stem, "answer": answer,
            "explanation": text, "answer_claims": claims, "needs_review": True,
            "image_name": image.name, "image_sha256": digest}
        temporary = args.cache.with_suffix(".tmp")
        temporary.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(args.cache)
        count += 1
        print(f"{image.stem}: {answer or '未识别/答案冲突，需复核'}")
    print(f"本轮识别 {count} 张，缓存共 {len(cache)} 条。")


if __name__ == "__main__":
    main()
