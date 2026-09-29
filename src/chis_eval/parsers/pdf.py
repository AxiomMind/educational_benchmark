from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..errors import ChisEvalError, OcrRequiredError


@dataclass(frozen=True)
class PdfExtractionResult:
    pdf_kind: str
    page_count: int
    raw_text_path: str
    cleaned_text_path: str
    page_texts: tuple[str, ...]


def classify_page_texts(
    page_texts: list[str] | tuple[str, ...], minimum_chars_per_text_page: int = 30
) -> str:
    """Classify a PDF from already-extracted page text as text, scan, or mixed."""
    if not page_texts:
        return "scan"
    text_flags = [len("".join(text.split())) >= minimum_chars_per_text_page for text in page_texts]
    if all(text_flags):
        return "text"
    if not any(text_flags):
        return "scan"
    return "mixed"


def extract_pdf_text(
    pdf_path: str | Path,
    output_dir: str | Path,
    minimum_chars_per_text_page: int = 30,
) -> PdfExtractionResult:
    """Extract an existing text layer and preserve both raw and lightly cleaned text."""
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise ChisEvalError("PyMuPDF is required; install chis-eval[pdf]") from exc

    input_path = Path(pdf_path)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    document = fitz.open(input_path)
    try:
        page_texts = tuple(page.get_text("text") for page in document)
    finally:
        document.close()
    pdf_kind = classify_page_texts(page_texts, minimum_chars_per_text_page)
    if pdf_kind == "scan":
        raise OcrRequiredError(f"No usable text layer detected in {input_path}; OCR is required")

    raw_path = target / f"{input_path.stem}.raw.txt"
    cleaned_path = target / f"{input_path.stem}.cleaned.txt"
    raw_combined = "\n\n".join(
        f"--- PAGE {number} ---\n{text}" for number, text in enumerate(page_texts, start=1)
    )
    cleaned_combined = "\n\n".join(_light_clean(text) for text in page_texts)
    raw_path.write_text(raw_combined, encoding="utf-8")
    cleaned_path.write_text(cleaned_combined, encoding="utf-8")
    return PdfExtractionResult(
        pdf_kind=pdf_kind,
        page_count=len(page_texts),
        raw_text_path=raw_path.as_posix(),
        cleaned_text_path=cleaned_path.as_posix(),
        page_texts=page_texts,
    )


def _light_clean(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.replace("\r\n", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()
