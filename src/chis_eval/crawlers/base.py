from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from ..config import CrawlDefaults, SourceEntry
from ..errors import ChisEvalError
from ..storage.crawl_state import CrawlState
from ..storage.raw_store import save_raw_response


@dataclass(frozen=True)
class DownloadResult:
    url: str
    raw_file: str
    content_hash: str
    status_code: int
    skipped_cached: bool = False


class BaseCrawler:
    """Serial, rate-limited and resumable downloader shared by all adapters."""

    RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}

    def __init__(
        self,
        source: SourceEntry,
        defaults: CrawlDefaults,
        raw_root: str | Path = "data/raw",
        state_path: str | Path = "data/state/crawl_state.sqlite3",
        dry_run: bool = False,
        client: httpx.Client | None = None,
    ):
        if defaults.concurrency != 1:
            logging.getLogger(__name__).warning(
                "V0.1 downloader remains serial even though concurrency=%s is configured",
                defaults.concurrency,
            )
        self.source = source
        self.defaults = defaults
        self.raw_root = Path(raw_root)
        self.state = CrawlState(state_path)
        self.dry_run = dry_run
        self.logger = logging.getLogger(f"chis_eval.crawler.{source.source_id}")
        self._last_request_monotonic: float | None = None
        self._owns_client = client is None
        self.client = client or httpx.Client(
            follow_redirects=True,
            timeout=defaults.timeout_seconds,
            headers={"User-Agent": defaults.user_agent},
        )

    def close(self) -> None:
        self.state.close()
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "BaseCrawler":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def download(self, url: str) -> DownloadResult | None:
        self._assert_url_in_scope(url)
        cached = self.state.get(self.source.source_id, url)
        if cached and cached["status"] == "success" and cached.get("raw_file"):
            if Path(cached["raw_file"]).exists():
                self.logger.info("Cache hit: %s", url)
                return DownloadResult(
                    url=url,
                    raw_file=cached["raw_file"],
                    content_hash=cached["content_hash"],
                    status_code=cached.get("http_status") or 200,
                    skipped_cached=True,
                )

        if self.dry_run:
            self.logger.info("Dry run: would download %s", url)
            return None

        last_error: Exception | None = None
        for retry_index in range(self.defaults.max_retries + 1):
            self._wait_for_rate_limit()
            self.state.mark_attempt(self.source.source_id, url)
            try:
                response = self.client.get(url)
                if response.status_code in self.RETRYABLE_STATUS_CODES:
                    raise _RetryableHttpError(response.status_code, response.headers.get("Retry-After"))
                response.raise_for_status()
                raw_file, digest = save_raw_response(
                    self.raw_root,
                    self.source.source_id,
                    str(response.url),
                    response.content,
                    response.status_code,
                    {key.lower(): value for key, value in response.headers.items()},
                )
                self.state.mark_success(
                    self.source.source_id, url, response.status_code, raw_file, digest
                )
                return DownloadResult(url, raw_file, digest, response.status_code)
            except _RetryableHttpError as exc:
                last_error = exc
                if retry_index < self.defaults.max_retries:
                    self._backoff(retry_index, exc.retry_after)
                    continue
                self.state.mark_failure(
                    self.source.source_id, url, "retry_exhausted", str(exc), exc.status_code
                )
            except httpx.TimeoutException as exc:
                last_error = exc
                if retry_index < self.defaults.max_retries:
                    self._backoff(retry_index)
                    continue
                self.state.mark_failure(self.source.source_id, url, "timeout", str(exc))
            except httpx.HTTPStatusError as exc:
                last_error = exc
                self.state.mark_failure(
                    self.source.source_id,
                    url,
                    "http_error",
                    str(exc),
                    exc.response.status_code,
                )
            except httpx.RequestError as exc:
                last_error = exc
                if retry_index < self.defaults.max_retries:
                    self._backoff(retry_index)
                    continue
                self.state.mark_failure(self.source.source_id, url, "request_error", str(exc))
            break

        self.logger.error("Download failed: %s (%s)", url, last_error)
        return None

    def _assert_url_in_scope(self, url: str) -> None:
        candidate = (urlparse(url).hostname or "").lower()
        base = (urlparse(self.source.base_url).hostname or "").lower()
        allowed = {base, *(domain.lower() for domain in self.source.allowed_domains)}
        if not candidate or not any(candidate == domain or candidate.endswith("." + domain) for domain in allowed):
            raise ChisEvalError(f"Out-of-scope domain for {self.source.source_id}: {candidate}")

    def _wait_for_rate_limit(self) -> None:
        if self._last_request_monotonic is not None:
            target_interval = random.uniform(
                self.defaults.request_interval_min_seconds,
                self.defaults.request_interval_max_seconds,
            )
            elapsed = time.monotonic() - self._last_request_monotonic
            if elapsed < target_interval:
                time.sleep(target_interval - elapsed)
        self._last_request_monotonic = time.monotonic()

    @staticmethod
    def _backoff(retry_index: int, retry_after: str | None = None) -> None:
        if retry_after:
            try:
                delay = min(float(retry_after), 60.0)
            except ValueError:
                delay = min(2**retry_index, 60.0)
        else:
            delay = min(2**retry_index, 60.0)
        time.sleep(delay)


class _RetryableHttpError(Exception):
    def __init__(self, status_code: int, retry_after: str | None):
        super().__init__(f"Retryable HTTP status {status_code}")
        self.status_code = status_code
        self.retry_after = retry_after
