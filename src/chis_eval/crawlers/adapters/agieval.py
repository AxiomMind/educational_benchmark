from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import BaseAdapter, register_adapter

if TYPE_CHECKING:
    from ..base import BaseCrawler, DownloadResult


@register_adapter("agieval_adapter")
class AgiEvalAdapter(BaseAdapter):
    """Adapter for Microsoft Research AGIEval gaokao-history subset."""

    RAW_URL = "https://raw.githubusercontent.com/ruixiangcui/AGIEval/main/data/v1/gaokao-history.jsonl"

    def collect(self, crawler: "BaseCrawler", limit: int | None) -> list["DownloadResult"]:
        result = crawler.download(self.RAW_URL)
        return [result] if result else []

    def parse_file(self, path: Path, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).astimezone().isoformat()
        content_hash = metadata.get("content_hash", "")
        raw_file_rel = metadata.get("raw_file", str(path))

        with path.open("r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        for index, line in enumerate(lines, start=1):
            item = json.loads(line)
            q_str = item.get("question", "").strip()
            raw_opt_list = item.get("options", [])
            ans = item.get("label") or item.get("answer")
            if len(raw_opt_list) != 4 or ans not in ["A", "B", "C", "D"]:
                continue

            clean_q = re.sub(r"^\d+[\.\、\．\s]*(（[^）]+）|\([^\)]+\))?\s*", "", q_str).strip()
            opts: dict[str, str] = {}
            letters = ["A", "B", "C", "D"]
            for i, opt_item in enumerate(raw_opt_list):
                cleaned_opt = re.sub(r"^\(?([A-D])\)?[\.\、\．\s]*", "", opt_item).strip()
                opts[letters[i]] = cleaned_opt

            source_info = item.get("other", {}).get("source", "高考历史试卷")
            year_match = re.search(r"(19\d\d|20\d\d)", source_info)
            year_val = int(year_match.group(1)) if year_match else 2018

            province_val = "全国"
            for p in ["北京", "上海", "天津", "重庆", "江苏", "浙江", "山东", "广东", "福建"]:
                if p in source_info:
                    province_val = p
                    break

            qid = f"CHIS_{index:06d}"

            record = {
                "schema_version": "0.1.0",
                "record_version": 1,
                "question_id": qid,
                "group_id": f"GROUP_AGIEVAL_{year_val}_{index:04d}",
                "shared_material": item.get("passage", "") or "",
                "raw_question": q_str,
                "normalized_question": clean_q,
                "question": clean_q,
                "raw_options": opts,
                "options": opts,
                "answer": ans,
                "answer_explanation": "",
                "answer_evidence": [
                    {
                        "source_id": self.source.source_id,
                        "answer": ans,
                        "official": True,
                        "reliable": True,
                        "evidence_url": self.RAW_URL,
                        "raw_file": raw_file_rel,
                        "page_number": None,
                        "source_question_number": str(index),
                        "raw_answer": f"答案：{ans}",
                    }
                ],
                "has_image": False,
                "image_paths": [],
                "source": {
                    "source_id": self.source.source_id,
                    "site_name": self.source.site_name,
                    "url": self.source.base_url,
                    "paper_title": source_info,
                    "year": year_val,
                    "province": province_val,
                    "exam_type": "高考真题",
                    "page_number": None,
                    "retrieved_at": now_iso,
                },
                "source_records": [
                    {
                        "source_id": self.source.source_id,
                        "site_name": self.source.site_name,
                        "url": self.source.base_url,
                        "paper_title": source_info,
                        "year": year_val,
                        "province": province_val,
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
                    "image_dependency": "not_image_dependent",
                    "issues": [],
                    "collector": self.source.collector or "collector_01",
                    "reviewer": "",
                    "notes": f"试卷出处: {source_info}",
                },
                "provenance": {
                    "raw_file": raw_file_rel,
                    "content_hash": content_hash,
                    "ordered_hash": "",
                    "permutation_hash": "",
                    "crawler_version": "v0.1",
                    "license_status": self.source.license_status,
                    "normalization_changes": [
                        {"field": "question", "before": q_str, "after": clean_q}
                    ],
                    "source_question_number": str(index),
                },
            }
            records.append(record)

        return records
