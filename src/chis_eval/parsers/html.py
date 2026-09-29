from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..models import build_question_record, utc_now_iso
from .answer import extract_answer


@dataclass(frozen=True)
class HtmlSelectorSpec:
    """Selectors supplied by a real site adapter after source inspection."""

    group: str
    question_block: str
    question: str
    option: str
    shared_material: str = ""
    answer: str = ""
    explanation: str = ""
    image: str = "img"
    option_label_attribute: str = "data-option"


@dataclass(frozen=True)
class ParserContext:
    source_id: str
    site_name: str
    url: str
    raw_file: str
    content_hash: str
    license_status: str = "unknown"
    collector: str = ""
    paper_title: str = ""
    year: int | None = None
    province: str = ""
    exam_type: str = ""
    retrieved_at: str = ""


def parse_html(
    html: str,
    selectors: HtmlSelectorSpec,
    context: ParserContext,
    question_start: int = 1,
    group_start: int = 1,
) -> list[dict[str, Any]]:
    """Parse adapter-selected HTML blocks while preserving group material."""
    soup = BeautifulSoup(html, "lxml")
    groups: list[Tag] = list(soup.select(selectors.group))
    if not groups:
        return []

    records: list[dict[str, Any]] = []
    question_number = question_start
    for group_offset, group in enumerate(groups):
        group_id = f"GROUP_{group_start + group_offset:06d}"
        material = _selected_text(group, selectors.shared_material)
        blocks = group.select(selectors.question_block)
        for block in blocks:
            raw_question = _selected_text(block, selectors.question)
            raw_options = _extract_options(block, selectors)
            answer_text = _selected_text(block, selectors.answer)
            answer = extract_answer(answer_text)
            explanation = _selected_text(block, selectors.explanation)
            images = [image.get("src", "") for image in block.select(selectors.image)]
            images = [value for value in images if value]
            answer_status = "single_source" if answer else "missing"
            record = build_question_record(
                {
                    "question_id": f"CHIS_{question_number:06d}",
                    "group_id": group_id,
                    "shared_material": material,
                    "raw_question": raw_question,
                    "normalized_question": raw_question,
                    "question": raw_question,
                    "raw_options": raw_options,
                    "options": dict(raw_options),
                    "answer": answer,
                    "answer_explanation": explanation,
                    "answer_evidence": ([{"source_id": context.source_id, "answer": answer}] if answer else []),
                    "has_image": bool(images),
                    "image_paths": [],
                    "source": _source_dict(context),
                    "source_records": [_source_dict(context)],
                    "quality": {
                        "answer_status": answer_status,
                        "parse_status": "parsed",
                        "collector": context.collector,
                        "issues": (
                            [
                                {
                                    "code": "unresolved_image_reference",
                                    "severity": "warning",
                                    "message": "; ".join(images),
                                }
                            ]
                            if images
                            else []
                        ),
                    },
                    "provenance": {
                        "raw_file": context.raw_file,
                        "content_hash": context.content_hash,
                        "license_status": context.license_status,
                    },
                }
            )
            records.append(record)
            question_number += 1
    return records


def _selected_text(parent: Tag, selector: str) -> str:
    if not selector:
        return ""
    element = parent.select_one(selector)
    return element.get_text(" ", strip=True) if element else ""


def _extract_options(block: Tag, selectors: HtmlSelectorSpec) -> dict[str, str]:
    options: dict[str, str] = {}
    for element in block.select(selectors.option):
        raw_text = element.get_text(" ", strip=True)
        label = (element.get(selectors.option_label_attribute) or "").strip().upper()
        if label not in {"A", "B", "C", "D"}:
            match = re.match(r"^\s*([A-DＡ-Ｄa-dａ-ｄ])[\.．、:：)）\s]+(.+)$", raw_text)
            if not match:
                continue
            label = extract_answer(match.group(1))
            raw_text = match.group(2).strip()
        else:
            raw_text = re.sub(
                rf"^\s*{re.escape(label)}[\.．、:：)）\s]+", "", raw_text, flags=re.IGNORECASE
            )
        options[label] = raw_text
    return {letter: options.get(letter, "") for letter in "ABCD"}


def _source_dict(context: ParserContext) -> dict[str, Any]:
    return {
        "source_id": context.source_id,
        "site_name": context.site_name,
        "url": context.url,
        "paper_title": context.paper_title,
        "year": context.year,
        "province": context.province,
        "exam_type": context.exam_type,
        "page_number": None,
        "retrieved_at": context.retrieved_at or utc_now_iso(),
    }
