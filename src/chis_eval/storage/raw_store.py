from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from ..models import utc_now_iso


def save_raw_response(
    root: str | Path,
    source_id: str,
    url: str,
    body: bytes,
    status_code: int,
    headers: dict[str, str],
) -> tuple[str, str]:
    """Save response bytes and sidecar metadata without altering the content."""
    digest = hashlib.sha256(body).hexdigest()
    url_digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    suffix = _safe_suffix(url, headers.get("content-type", ""))
    source_root = Path(root) / source_id
    source_root.mkdir(parents=True, exist_ok=True)
    body_path = source_root / f"{url_digest}{suffix}"
    metadata_path = source_root / f"{url_digest}.metadata.json"
    body_path.write_bytes(body)
    metadata_path.write_text(
        json.dumps(
            {
                "source_id": source_id,
                "url": url,
                "status_code": status_code,
                "retrieved_at": utc_now_iso(),
                "content_hash": digest,
                "content_type": headers.get("content-type", ""),
                "raw_file": body_path.as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return body_path.as_posix(), digest


def _safe_suffix(url: str, content_type: str) -> str:
    lower_type = content_type.lower()
    if "pdf" in lower_type:
        return ".pdf"
    if "html" in lower_type:
        return ".html"
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".html", ".htm", ".pdf", ".txt", ".json"}:
        return suffix
    return ".bin"
