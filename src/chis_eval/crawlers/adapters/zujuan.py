from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup

from . import BaseAdapter, register_adapter

if TYPE_CHECKING:
    from ..base import BaseCrawler, DownloadResult


@register_adapter("zujuan_adapter")
class ZujuanAdapter(BaseAdapter):
    """Adapter for Xueke Zujuan history exam papers.

    Privacy Note: Never hardcodes user session tokens or credentials.
    Reads credentials dynamically from XKW_COOKIE environment variable or
    the local untracked data/xkw_cookies.json file.
    """

    LIST_URL_TEMPLATE = "https://zujuan.xkw.com/gzls/shijuan/tbjx/zj136098/p{}/"

    def __init__(self, source: Any) -> None:
        super().__init__(source)
        self.logger = logging.getLogger("chis_eval.adapter.zujuan")

    def _get_cookie_dict(self) -> dict[str, str]:
        # 1. Check environment variable first
        env_cookie = os.environ.get("XKW_COOKIE", "").strip()
        if env_cookie:
            return {
                k.strip(): v.strip()
                for k, _, v in (part.partition("=") for part in env_cookie.split(";"))
                if k.strip()
            }

        # 2. Check local untracked file (protected by .gitignore)
        local_file = Path("data/xkw_cookies.json")
        if local_file.exists():
            try:
                with local_file.open("r", encoding="utf-8") as f:
                    raw = json.load(f)
                    if isinstance(raw, list):
                        return {c["name"]: c["value"] for c in raw if "name" in c and "value" in c}
            except Exception as exc:
                self.logger.debug("Failed reading local cookie file: %s", exc)

        return {}

    def collect(self, crawler: "BaseCrawler", limit: int | None) -> list["DownloadResult"]:
        max_papers = limit or 10
        cookies = self._get_cookie_dict()
        if cookies:
            crawler.client.cookies.update(cookies)
        else:
            self.logger.info("Running in guest mode without authenticated cookies.")

        results: list["DownloadResult"] = []
        page_num = 1
        seen_pids: set[str] = set()

        while len(results) < max_papers and page_num <= 20:
            list_url = self.LIST_URL_TEMPLATE.format(page_num)
            list_res = crawler.download(list_url)
            if not list_res:
                break

            list_path = Path(list_res.raw_file)
            if not list_path.exists():
                break

            html = list_path.read_text(encoding="utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")
            links = soup.find_all("a", href=re.compile(r"/17p\d+\.html"))

            for a in links:
                if len(results) >= max_papers:
                    break
                href = a.get("href", "")
                m = re.search(r"/17p(\d+)\.html", href)
                if not m:
                    continue
                pid = m.group(1)
                if pid in seen_pids:
                    continue
                seen_pids.add(pid)

                paper_url = f"https://zujuan.xkw.com/17p{pid}.html"
                paper_res = crawler.download(paper_url)
                if paper_res:
                    results.append(paper_res)

            page_num += 1

        return results

    def parse_file(self, path: Path, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        html = path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")

        title_tag = soup.find("h1") or soup.find("title")
        raw_title = title_tag.get_text(strip=True) if title_tag else "高中历史试题"
        paper_title = re.sub(r"-组卷网.*$", "", raw_title).strip()

        year_m = re.search(r"(202\d|201\d)", paper_title)
        year_val = int(year_m.group(1)) if year_m else 2024

        province_val = "全国"
        provinces = [
            "北京", "上海", "天津", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江",
            "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
            "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃",
        ]
        for prov in provinces:
            if prov in paper_title:
                province_val = prov
                break

        pid_match = re.search(r"zujuan_paper_(\d+)|/17p(\d+)", str(path))
        paper_id = (pid_match.group(1) or pid_match.group(2)) if pid_match else "000000"

        now_iso = datetime.now(timezone.utc).astimezone().isoformat()
        content_hash = metadata.get("content_hash", "")
        raw_file_rel = metadata.get("raw_file", str(path))
        page_url = metadata.get("url", f"https://zujuan.xkw.com/17p{paper_id}.html")

        records: list[dict[str, Any]] = []
        ques_divs = soup.find_all("div", class_=re.compile(r"quesdiv"))

        for local_index, qd in enumerate(ques_divs, start=1):
            res = self._parse_mcq_div(qd)
            if not res:
                continue
            q_clean, opts = res

            div_id = qd.get("id", "")
            source_qid_match = re.search(r"\d+", div_id)
            source_qid = source_qid_match.group(0) if source_qid_match else str(local_index)

            qid = f"CHIS_{paper_id}_{local_index:03d}"
            # Ensure valid format for question_id if required by schema, otherwise CHIS_000000
            if not re.match(r"^CHIS_[0-9]{6}$", qid):
                qid = f"CHIS_{int(source_qid) % 1000000:06d}"

            record = {
                "schema_version": "0.1.0",
                "record_version": 1,
                "question_id": qid,
                "group_id": f"GROUP_ZUJUAN_{paper_id}_{local_index:03d}",
                "shared_material": "",
                "raw_question": q_clean,
                "normalized_question": q_clean,
                "question": q_clean,
                "raw_options": opts,
                "options": opts,
                "answer": "",
                "answer_explanation": "",
                "answer_evidence": [],
                "has_image": False,
                "image_paths": [],
                "source": {
                    "source_id": self.source.source_id,
                    "site_name": self.source.site_name,
                    "url": page_url,
                    "paper_title": paper_title,
                    "year": year_val,
                    "province": province_val,
                    "exam_type": "阶段练习与模拟考",
                    "page_number": None,
                    "retrieved_at": now_iso,
                },
                "source_records": [
                    {
                        "source_id": self.source.source_id,
                        "site_name": self.source.site_name,
                        "url": page_url,
                        "paper_title": paper_title,
                        "year": year_val,
                        "province": province_val,
                        "exam_type": "阶段练习与模拟考",
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
                    "answer_status": "missing",
                    "duplicate_status": "unique",
                    "parse_status": "parsed",
                    "review_status": "pending",
                    "image_dependency": "not_image_dependent",
                    "issues": [],
                    "collector": self.source.collector or "collector_01",
                    "reviewer": "",
                    "notes": f"试卷出处: {paper_title} (题号: {source_qid})",
                },
                "provenance": {
                    "raw_file": raw_file_rel,
                    "content_hash": content_hash,
                    "ordered_hash": "",
                    "permutation_hash": "",
                    "crawler_version": "v0.1",
                    "license_status": self.source.license_status,
                    "normalization_changes": [],
                    "source_question_number": source_qid,
                },
            }
            records.append(record)

        return records

    @staticmethod
    def _parse_mcq_div(div: Any) -> tuple[str, dict[str, str]] | None:
        txt = div.get_text("\n", strip=True)
        parts = re.split(r"(?=[A-D][\.\、\．])", txt)
        if len(parts) < 5:
            return None
        q = parts[0].strip()
        q = re.sub(r"^\d+[\.\、\．\s]*(（[^）]+）|\([^\)]+\))?\s*", "", q).strip()
        opts: dict[str, str] = {}
        for p in parts[1:]:
            p = p.strip()
            if not p:
                continue
            letter = p[0]
            val = re.sub(r"^[A-D][\.\、\．]\s*", "", p).strip()
            sub = re.split(r"\s+(?=[B-D][\.\、\．])", val)
            if len(sub) > 1:
                opts[letter] = sub[0].strip()
                for s in sub[1:]:
                    s = s.strip()
                    if s and s[0] in "BCD":
                        opts[s[0]] = re.sub(r"^[B-D][\.\、\．]\s*", "", s).strip()
            else:
                opts[letter] = val
        if set(opts.keys()) == {"A", "B", "C", "D"}:
            if all(len(opts[k]) > 0 for k in "ABCD") and len(q) > 5:
                return q, opts
        return None
