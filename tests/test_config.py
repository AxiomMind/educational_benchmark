from __future__ import annotations

from pathlib import Path

import pytest

from chis_eval.config import SourceRegistry
from chis_eval.errors import SourceNotApprovedError


def _registry_text(status: str = "approved", license_status: str = "research_only") -> str:
    return f"""
version: 1
defaults:
  request_interval_min_seconds: 2
  request_interval_max_seconds: 5
  concurrency: 1
  max_retries: 2
  timeout_seconds: 10
  user_agent: CHisEval-test
sources:
  - source_id: fixture_html
    site_name: Fixture
    base_url: https://example.test
    source_type: html
    exam_type: mock
    has_answer: true
    year_range: 2024
    estimated_questions: 10
    login_required: false
    robots_checked: true
    terms_checked: true
    license_status: {license_status}
    redistribution_allowed: false
    collector: tester
    status: {status}
    notes: synthetic
    adapter: fixture
    start_urls:
      - https://example.test/list
"""


def test_registry_allows_only_approved_source(tmp_path: Path) -> None:
    path = tmp_path / "registry.yaml"
    path.write_text(_registry_text(), encoding="utf-8")
    registry = SourceRegistry.load(path)
    source = registry.assert_crawl_allowed("fixture_html")
    assert source.redistribution_allowed is False
    assert source.start_urls == ("https://example.test/list",)


def test_registry_rejects_draft_and_restricted(tmp_path: Path) -> None:
    path = tmp_path / "registry.yaml"
    path.write_text(_registry_text(status="draft", license_status="restricted"), encoding="utf-8")
    registry = SourceRegistry.load(path)
    with pytest.raises(SourceNotApprovedError, match="not approved"):
        registry.assert_crawl_allowed("fixture_html")
