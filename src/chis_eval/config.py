from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigurationError, SourceNotApprovedError


LICENSE_STATUSES = {"allowed", "research_only", "unknown", "restricted"}
SOURCE_STATUSES = {"draft", "pending_review", "approved", "disabled", "rejected"}
SOURCE_TYPES = {"html", "pdf", "mixed"}


@dataclass(frozen=True)
class CrawlDefaults:
    request_interval_min_seconds: float = 2.0
    request_interval_max_seconds: float = 5.0
    concurrency: int = 1
    max_retries: int = 3
    timeout_seconds: float = 30.0
    user_agent: str = "CHisEval/0.1 research crawler"

    def validate(self) -> None:
        if self.request_interval_min_seconds < 2:
            raise ConfigurationError("Minimum request interval must be at least 2 seconds")
        if self.request_interval_max_seconds < self.request_interval_min_seconds:
            raise ConfigurationError("Maximum request interval cannot be below minimum")
        if not 1 <= self.concurrency <= 2:
            raise ConfigurationError("Crawler concurrency must be 1 or 2")
        if self.max_retries < 0:
            raise ConfigurationError("max_retries cannot be negative")
        if not self.user_agent.strip():
            raise ConfigurationError("A clear User-Agent is required")


@dataclass(frozen=True)
class SourceEntry:
    source_id: str
    site_name: str
    base_url: str
    source_type: str
    exam_type: str
    has_answer: bool
    year_range: Any
    estimated_questions: int | None
    login_required: bool
    robots_checked: bool
    terms_checked: bool
    license_status: str
    redistribution_allowed: bool
    collector: str
    status: str
    notes: str = ""
    adapter: str = ""
    approved_by: str = ""
    approved_at: str = ""
    terms_url: str = ""
    license_evidence: str = ""
    robots_checked_at: str = ""
    start_urls: tuple[str, ...] = field(default_factory=tuple)
    allowed_domains: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceEntry":
        required = {
            "source_id",
            "site_name",
            "base_url",
            "source_type",
            "exam_type",
            "has_answer",
            "year_range",
            "estimated_questions",
            "login_required",
            "robots_checked",
            "terms_checked",
            "license_status",
            "redistribution_allowed",
            "collector",
            "status",
            "notes",
        }
        missing = sorted(required - data.keys())
        if missing:
            raise ConfigurationError(f"Source entry is missing fields: {', '.join(missing)}")
        try:
            entry = cls(
                **{
                    key: value
                    for key, value in data.items()
                    if key in cls.__dataclass_fields__
                    and key not in {"start_urls", "allowed_domains"}
                },
                start_urls=tuple(data.get("start_urls", ())),
                allowed_domains=tuple(data.get("allowed_domains", ())),
            )
        except TypeError as exc:
            raise ConfigurationError(f"Invalid source entry: {exc}") from exc
        entry.validate()
        return entry

    def validate(self) -> None:
        if not self.source_id or not self.source_id.replace("_", "").replace("-", "").isalnum():
            raise ConfigurationError("source_id must contain only letters, numbers, '_' or '-'")
        if self.source_type not in SOURCE_TYPES:
            raise ConfigurationError(f"Unsupported source_type: {self.source_type}")
        if self.license_status not in LICENSE_STATUSES:
            raise ConfigurationError(f"Unsupported license_status: {self.license_status}")
        if self.status not in SOURCE_STATUSES:
            raise ConfigurationError(f"Unsupported source status: {self.status}")
        if not self.base_url.startswith(("http://", "https://")):
            raise ConfigurationError(f"Invalid base_url for {self.source_id}")


@dataclass(frozen=True)
class SourceRegistry:
    defaults: CrawlDefaults
    sources: dict[str, SourceEntry]

    @classmethod
    def load(cls, path: str | Path) -> "SourceRegistry":
        registry_path = Path(path)
        if not registry_path.exists():
            raise ConfigurationError(f"Source registry not found: {registry_path}")
        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
        if raw.get("version") != 1:
            raise ConfigurationError("source_registry.yaml must use version: 1")
        defaults = CrawlDefaults(**(raw.get("defaults") or {}))
        defaults.validate()
        entries: dict[str, SourceEntry] = {}
        for source_data in raw.get("sources") or []:
            entry = SourceEntry.from_dict(source_data)
            if entry.source_id in entries:
                raise ConfigurationError(f"Duplicate source_id: {entry.source_id}")
            entries[entry.source_id] = entry
        return cls(defaults=defaults, sources=entries)

    def require_source(self, source_id: str) -> SourceEntry:
        try:
            return self.sources[source_id]
        except KeyError as exc:
            raise ConfigurationError(f"Unknown source_id: {source_id}") from exc

    def assert_crawl_allowed(self, source_id: str) -> SourceEntry:
        source = self.require_source(source_id)
        reasons: list[str] = []
        if source.status != "approved":
            reasons.append("status is not approved")
        if source.login_required:
            reasons.append("login is required")
        if not source.robots_checked:
            reasons.append("robots policy has not been checked")
        if not source.terms_checked:
            reasons.append("terms have not been checked")
        if source.license_status == "restricted":
            reasons.append("licence is restricted")
        if reasons:
            raise SourceNotApprovedError(
                f"Source {source_id!r} cannot be crawled: " + "; ".join(reasons)
            )
        return source
