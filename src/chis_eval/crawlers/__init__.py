from .adapters import BaseAdapter, get_adapter, register_adapter
from .base import BaseCrawler, DownloadResult

__all__ = ["BaseAdapter", "BaseCrawler", "DownloadResult", "get_adapter", "register_adapter"]
