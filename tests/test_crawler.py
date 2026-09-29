from pathlib import Path

import httpx
import pytest

from chis_eval.config import CrawlDefaults, SourceEntry
from chis_eval.crawlers.base import BaseCrawler
from chis_eval.errors import ChisEvalError


def _source() -> SourceEntry:
    return SourceEntry(
        source_id="fixture",
        site_name="Fixture",
        base_url="https://example.test",
        source_type="html",
        exam_type="mock",
        has_answer=True,
        year_range="2024",
        estimated_questions=1,
        login_required=False,
        robots_checked=True,
        terms_checked=True,
        license_status="research_only",
        redistribution_allowed=False,
        collector="tester",
        status="approved",
    )


def test_crawler_saves_raw_response_and_reuses_cache(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, text="<html>fixture</html>", headers={"content-type": "text/html"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    defaults = CrawlDefaults(2, 2, 1, 0, 10, "CHisEval-test")
    with BaseCrawler(
        _source(),
        defaults,
        raw_root=tmp_path / "raw",
        state_path=tmp_path / "state.sqlite3",
        client=client,
    ) as crawler:
        first = crawler.download("https://example.test/item/1")
        second = crawler.download("https://example.test/item/1")
    client.close()
    assert first is not None and Path(first.raw_file).exists()
    assert second is not None and second.skipped_cached is True
    assert calls == 1


def test_crawler_rejects_out_of_scope_domain(tmp_path: Path) -> None:
    defaults = CrawlDefaults(2, 2, 1, 0, 10, "CHisEval-test")
    with BaseCrawler(
        _source(), defaults, raw_root=tmp_path / "raw", state_path=tmp_path / "state.sqlite3", dry_run=True
    ) as crawler:
        with pytest.raises(ChisEvalError, match="Out-of-scope"):
            crawler.download("https://unrelated.invalid/item")
