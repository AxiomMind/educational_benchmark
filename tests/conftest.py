from __future__ import annotations

from copy import deepcopy

import pytest

from chis_eval.models import build_question_record


@pytest.fixture
def valid_record() -> dict:
    return build_question_record(
        {
            "question_id": "CHIS_000001",
            "group_id": "GROUP_000001",
            "raw_question": "1. 中国古代某制度的主要作用是",
            "normalized_question": "中国古代某制度的主要作用是",
            "question": "中国古代某制度的主要作用是",
            "raw_options": {"A": "加强中央集权", "B": "地方独立", "C": "废除农业", "D": "取消政府"},
            "options": {"A": "加强中央集权", "B": "地方独立", "C": "废除农业", "D": "取消政府"},
            "answer": "A",
            "answer_evidence": [
                {"source_id": "official_fixture", "answer": "A", "official": True}
            ],
            "source": {
                "source_id": "fixture",
                "site_name": "Synthetic fixture",
                "url": "https://example.test/paper/1",
                "paper_title": "Synthetic paper",
                "year": 2024,
                "province": "测试",
                "exam_type": "模拟测试",
                "retrieved_at": "2026-09-29T00:00:00+00:00",
            },
            "source_records": [
                {
                    "source_id": "fixture",
                    "site_name": "Synthetic fixture",
                    "url": "https://example.test/paper/1",
                    "paper_title": "Synthetic paper",
                    "year": 2024,
                    "province": "测试",
                    "exam_type": "模拟测试",
                    "page_number": None,
                    "retrieved_at": "2026-09-29T00:00:00+00:00",
                }
            ],
            "provenance": {"license_status": "allowed"},
        }
    )


@pytest.fixture
def clone_record():
    return deepcopy
