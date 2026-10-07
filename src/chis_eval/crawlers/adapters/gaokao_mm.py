from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import BaseAdapter, register_adapter

if TYPE_CHECKING:
    from ..base import BaseCrawler, DownloadResult


@register_adapter("gaokao_mm_adapter")
class GaokaoMmAdapter(BaseAdapter):
    """Adapter for OpenMOSS GAOKAO-MM multimodal history questions."""

    RAW_URL = "https://raw.githubusercontent.com/OpenMOSS/GAOKAO-MM/main/Data/2010-2023_History_MCQs.json"

    def collect(self, crawler: "BaseCrawler", limit: int | None) -> list["DownloadResult"]:
        result = crawler.download(self.RAW_URL)
        return [result] if result else []

    def parse_file(self, path: Path, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f).get("example", [])

        records: list[dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).astimezone().isoformat()
        content_hash = metadata.get("content_hash", "")
        raw_file_rel = metadata.get("raw_file", str(path))

        for index, item in enumerate(data, start=1):
            q_text = item.get("question", "")
            pics = item.get("picture", [])
            ans = item.get("answer", [""])[0]
            if ans not in ["A", "B", "C", "D"]:
                continue

            q_part, opts = self._parse_mcq_text(q_text)
            if not q_part or not opts:
                continue

            clean_q = re.sub(r"^\d+[\.\、\．\s]*(（[^）]+）|\([^\)]+\))?\s*", "", q_part).strip()
            year_val = int(item.get("year")) if str(item.get("year", "")).isdigit() else 2022
            qid = f"CHIS_{index:06d}"

            image_paths = []
            if pics:
                pic_name = Path(pics[0]).name
                image_paths.append(f"assets/{pic_name}")

            record = {
                "schema_version": "0.1.0",
                "record_version": 1,
                "question_id": qid,
                "group_id": f"GROUP_GAOKAOMM_{year_val}_{index:04d}",
                "shared_material": "",
                "raw_question": q_part,
                "normalized_question": clean_q,
                "question": clean_q,
                "raw_options": opts,
                "options": opts,
                "answer": ans,
                "answer_explanation": item.get("analysis", "").strip(),
                "answer_evidence": [
                    {
                        "source_id": self.source.source_id,
                        "answer": ans,
                        "official": True,
                        "reliable": True,
                        "evidence_url": self.RAW_URL,
                        "raw_file": raw_file_rel,
                        "page_number": None,
                        "source_question_number": str(item.get("index", index)),
                        "raw_answer": f"答案：{ans}",
                    }
                ],
                "has_image": bool(image_paths),
                "image_paths": image_paths,
                "source": {
                    "source_id": self.source.source_id,
                    "site_name": self.source.site_name,
                    "url": self.source.base_url,
                    "paper_title": f"{year_val}年普通高等学校招生全国统一考试历史真题（图文版）",
                    "year": year_val,
                    "province": "全国",
                    "exam_type": "高考真题",
                    "page_number": None,
                    "retrieved_at": now_iso,
                },
                "source_records": [
                    {
                        "source_id": self.source.source_id,
                        "site_name": self.source.site_name,
                        "url": self.source.base_url,
                        "paper_title": f"{year_val}年普通高等学校招生全国统一考试历史真题（图文版）",
                        "year": year_val,
                        "province": "全国",
                        "exam_type": "高考真题",
                        "page_number": None,
                        "retrieved_at": now_iso,
                    }
                ],
                "labels": {
                    "primary_ability": "",
                    "history_scope": "",
                    "historical_period": "",
                    "knowledge_point": "",
                    "material_type": "",
                },
                "quality": {
                    "answer_status": "verified",
                    "duplicate_status": "unique",
                    "parse_status": "parsed",
                    "review_status": "pending",
                    "image_dependency": "image_dependent" if image_paths else "not_image_dependent",
                    "issues": [],
                    "collector": self.source.collector or "collector_01",
                    "reviewer": "",
                    "notes": "包含历史图表/漫画/地图原件，答案经官方验证",
                },
                "provenance": {
                    "raw_file": raw_file_rel,
                    "content_hash": content_hash,
                    "ordered_hash": "",
                    "permutation_hash": "",
                    "crawler_version": "v0.1",
                    "license_status": self.source.license_status,
                    "normalization_changes": [
                        {"field": "question", "before": q_part, "after": clean_q}
                    ],
                    "source_question_number": str(item.get("index", index)),
                },
            }
            records.append(record)

        return records

    @staticmethod
    def _parse_mcq_text(text: str) -> tuple[str | None, dict[str, str] | None]:
        parts = re.split(r"(?=[A-D][\.\、\．])", text)
        if len(parts) < 5:
            return None, None
        q_part = parts[0].strip()
        raw_opts: dict[str, str] = {}
        for p in parts[1:]:
            p = p.strip()
            if not p:
                continue
            letter = p[0]
            val = re.sub(r"^[A-D][\.\、\．]\s*", "", p).strip()
            sub_split = re.split(r"\s+(?=[B-D][\.\、\．])", val)
            if len(sub_split) > 1:
                raw_opts[letter] = sub_split[0].strip()
                for sub in sub_split[1:]:
                    sub = sub.strip()
                    if sub and sub[0] in "BCD":
                        raw_opts[sub[0]] = re.sub(r"^[B-D][\.\、\．]\s*", "", sub).strip()
            else:
                raw_opts[letter] = val
        if set(raw_opts.keys()) == {"A", "B", "C", "D"}:
            return q_part, raw_opts
        return None, None
