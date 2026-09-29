from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from ..errors import ChisEvalError


@dataclass(frozen=True)
class OcrPageResult:
    page_number: int
    image_path: str
    raw_result_path: str
    raw_text_path: str
    cleaned_text_path: str
    mean_confidence: float | None


def ocr_pdf_with_paddle(
    pdf_path: str | Path,
    output_dir: str | Path,
    language: str = "ch",
) -> list[OcrPageResult]:
    """Render and OCR a scanned PDF while retaining every intermediate artifact.

    This optional path is never called for PDFs with a usable text layer.
    """
    try:
        import fitz  # type: ignore
        from paddleocr import PaddleOCR  # type: ignore
    except ImportError as exc:
        raise ChisEvalError("OCR requires the optional chis-eval[pdf,ocr] dependencies") from exc

    input_path = Path(pdf_path)
    target = Path(output_dir)
    image_dir = target / "pages"
    raw_dir = target / "ocr_raw"
    cleaned_dir = target / "ocr_cleaned"
    for directory in (image_dir, raw_dir, cleaned_dir):
        directory.mkdir(parents=True, exist_ok=True)

    engine = PaddleOCR(use_angle_cls=True, lang=language, show_log=False)
    document = fitz.open(input_path)
    results: list[OcrPageResult] = []
    try:
        for index, page in enumerate(document):
            page_number = index + 1
            image_path = image_dir / f"page_{page_number:04d}.png"
            page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).save(image_path)
            raw_result: Any = engine.ocr(str(image_path), cls=True)
            raw_json_path = raw_dir / f"page_{page_number:04d}.json"
            raw_json_path.write_text(
                json.dumps(raw_result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            lines, confidences = _paddle_lines(raw_result)
            raw_text_path = raw_dir / f"page_{page_number:04d}.txt"
            raw_text_path.write_text("\n".join(lines), encoding="utf-8")
            cleaned_text_path = cleaned_dir / f"page_{page_number:04d}.txt"
            cleaned_text_path.write_text(
                "\n".join(" ".join(line.split()) for line in lines), encoding="utf-8"
            )
            results.append(
                OcrPageResult(
                    page_number=page_number,
                    image_path=image_path.as_posix(),
                    raw_result_path=raw_json_path.as_posix(),
                    raw_text_path=raw_text_path.as_posix(),
                    cleaned_text_path=cleaned_text_path.as_posix(),
                    mean_confidence=mean(confidences) if confidences else None,
                )
            )
    finally:
        document.close()
    return results


def _paddle_lines(raw_result: Any) -> tuple[list[str], list[float]]:
    lines: list[str] = []
    confidences: list[float] = []
    pages = raw_result if isinstance(raw_result, list) else []
    for page in pages:
        if not isinstance(page, list):
            continue
        for item in page:
            try:
                text, confidence = item[1]
                lines.append(str(text))
                confidences.append(float(confidence))
            except (IndexError, TypeError, ValueError):
                continue
    return lines, confidences
