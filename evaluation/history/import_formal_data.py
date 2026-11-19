"""Import the frozen 3,993-question evaluation set from the local ABCD delivery."""
import argparse
import hashlib
import io
from pathlib import Path
import tempfile
from zipfile import ZipFile

from evaluate import image_references, load_items, read_image

ROOT = Path(__file__).resolve().parent
COORDINATOR = "协调端_ABCD八模型统一评分.zip"
COORDINATOR_SHA256 = "da56d233e4e2c2a1d97c6837b3c1bc78f544eb39bdfd6288c99e8a92a94ab056"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="ABCD 完成版 ZIP 或其中的协调端 ZIP")
    args = parser.parse_args()
    destination = ROOT / "data"
    if destination.exists():
        parser.exit(1, "data 已存在。请在新的评测目录导入，以保留现有数据。\n")
    with ZipFile(args.package) as archive:
        matches = [name for name in archive.namelist() if name.endswith("/" + COORDINATOR)]
        blob = archive.read(matches[0]) if len(matches) == 1 else args.package.read_bytes()
    if hashlib.sha256(blob).hexdigest() != COORDINATOR_SHA256:
        parser.exit(1, "协调端 ZIP 的 SHA-256 与正式评测包不同，请核对版本。\n")
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary, ZipFile(io.BytesIO(blob)) as archive:
        stage = Path(temporary) / "data"
        (stage / "images").mkdir(parents=True)
        prefix = "CHisEval_全量图文评测/data/"
        for filename in ("eval_inputs.jsonl", "eval_key.jsonl"):
            (stage / filename).write_bytes(archive.read(prefix + filename))
        items = load_items(stage / "eval_inputs.jsonl")
        refs = {pair for item in items for pair in image_references(item)}
        for filename, digest in refs:
            (stage / filename).write_bytes(archive.read(prefix + filename))
            read_image(stage, filename, digest)
        stage.rename(destination)
    print(f"已校验并导入 {len(items)} 题，{len(refs)} 张题图。")


if __name__ == "__main__":
    main()
