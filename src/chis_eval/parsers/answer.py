from __future__ import annotations

import re


_ANSWER_PATTERNS = (
    re.compile(r"(?:参考)?答案\s*[:：]?\s*([A-DＡ-Ｄa-dａ-ｄ])", re.IGNORECASE),
    re.compile(r"^\s*([A-DＡ-Ｄa-dａ-ｄ])\s*$", re.IGNORECASE),
)


def extract_answer(text: str | None) -> str:
    if not text:
        return ""
    for pattern in _ANSWER_PATTERNS:
        match = pattern.search(text)
        if match:
            return _normalise_answer_letter(match.group(1))
    return ""


def _normalise_answer_letter(value: str) -> str:
    translation = str.maketrans("ＡＢＣＤａｂｃｄ", "ABCDabcd")
    return value.translate(translation).upper()
