from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ..models import utc_now_iso


class CrawlState:
    """SQLite-backed URL state used for caching and resumable crawling."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS crawl_urls (
                source_id TEXT NOT NULL,
                url TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                http_status INTEGER,
                raw_file TEXT,
                content_hash TEXT,
                error_type TEXT,
                error_message TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (source_id, url)
            )
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "CrawlState":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def get(self, source_id: str, url: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM crawl_urls WHERE source_id = ? AND url = ?", (source_id, url)
        ).fetchone()
        return dict(row) if row else None

    def succeeded(self, source_id: str, url: str) -> bool:
        row = self.get(source_id, url)
        return bool(row and row["status"] == "success" and row["raw_file"])

    def successful_files(self, source_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM crawl_urls WHERE source_id = ? AND status = 'success' ORDER BY updated_at"
        parameters: list[Any] = [source_id]
        if limit is not None:
            query += " LIMIT ?"
            parameters.append(limit)
        return [dict(row) for row in self.connection.execute(query, parameters).fetchall()]

    def mark_attempt(self, source_id: str, url: str) -> None:
        self.connection.execute(
            """
            INSERT INTO crawl_urls (source_id, url, status, attempts, updated_at)
            VALUES (?, ?, 'pending', 1, ?)
            ON CONFLICT(source_id, url) DO UPDATE SET
              status = 'pending', attempts = attempts + 1, updated_at = excluded.updated_at
            """,
            (source_id, url, utc_now_iso()),
        )
        self.connection.commit()

    def mark_success(
        self,
        source_id: str,
        url: str,
        http_status: int,
        raw_file: str,
        content_hash: str,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO crawl_urls
              (source_id, url, status, attempts, http_status, raw_file, content_hash, updated_at)
            VALUES (?, ?, 'success', 1, ?, ?, ?, ?)
            ON CONFLICT(source_id, url) DO UPDATE SET
              status = 'success', http_status = excluded.http_status,
              raw_file = excluded.raw_file, content_hash = excluded.content_hash,
              error_type = NULL, error_message = NULL, updated_at = excluded.updated_at
            """,
            (source_id, url, http_status, raw_file, content_hash, utc_now_iso()),
        )
        self.connection.commit()

    def mark_failure(
        self,
        source_id: str,
        url: str,
        error_type: str,
        error_message: str,
        http_status: int | None = None,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO crawl_urls
              (source_id, url, status, attempts, http_status, error_type, error_message, updated_at)
            VALUES (?, ?, 'failed', 1, ?, ?, ?, ?)
            ON CONFLICT(source_id, url) DO UPDATE SET
              status = 'failed', http_status = excluded.http_status,
              error_type = excluded.error_type, error_message = excluded.error_message,
              updated_at = excluded.updated_at
            """,
            (source_id, url, http_status, error_type, error_message[:2000], utc_now_iso()),
        )
        self.connection.commit()
