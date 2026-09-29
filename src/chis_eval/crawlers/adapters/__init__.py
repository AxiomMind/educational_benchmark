from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from ...config import SourceEntry
from ...errors import AdapterNotFoundError

if TYPE_CHECKING:
    from ..base import BaseCrawler, DownloadResult


class BaseAdapter(ABC):
    """A site-specific adapter. Generic crawler code contains no site selectors."""

    def __init__(self, source: SourceEntry):
        self.source = source

    @abstractmethod
    def collect(self, crawler: "BaseCrawler", limit: int | None) -> list["DownloadResult"]:
        """Discover and download up to ``limit`` detail documents."""

    @abstractmethod
    def parse_file(self, path: Path, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse one saved raw file into question records."""


AdapterType = TypeVar("AdapterType", bound=type[BaseAdapter])
_ADAPTERS: dict[str, type[BaseAdapter]] = {}


def register_adapter(name: str) -> Callable[[AdapterType], AdapterType]:
    def decorator(adapter_class: AdapterType) -> AdapterType:
        if name in _ADAPTERS:
            raise ValueError(f"Adapter already registered: {name}")
        _ADAPTERS[name] = adapter_class
        return adapter_class

    return decorator


def get_adapter(name: str, source: SourceEntry) -> BaseAdapter:
    if not name:
        raise AdapterNotFoundError(
            f"Source {source.source_id!r} has no adapter configured; add one only after inspecting the real source"
        )
    try:
        adapter_class = _ADAPTERS[name]
    except KeyError as exc:
        raise AdapterNotFoundError(f"Adapter is not implemented: {name}") from exc
    return adapter_class(source)
