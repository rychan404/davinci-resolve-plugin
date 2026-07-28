"""Deliberate single-asset downloads with durable provenance sidecars."""

from __future__ import annotations
import dataclasses, json, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import httpx
from resolvestock.models import LibraryItem, SearchResult
from resolvestock.sources.base import USER_AGENT

SIDECAR_SUFFIX = ".provenance.json"
UNSAFE_CHARS = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_length: int = 48) -> str:
    return (
        UNSAFE_CHARS.sub("_", text.strip().lower()).strip("_")[:max_length].rstrip("_")
    )


class Library:
    def __init__(self, root: Path, client: httpx.Client | None = None):
        self.root = Path(root)
        self.client = client or httpx.Client(
            timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        )

    def normalize_filename(self, result: SearchResult, suffix: str) -> str:
        stem = slugify(result.title) or "untitled"
        return f"{stem}_{result.source}_{result.source_id}{suffix}"

    def sidecar_path(self, path: Path) -> Path:
        return path.with_suffix(path.suffix + SIDECAR_SUFFIX)

    def _suffix_for(self, result: SearchResult) -> str:
        return Path(urlparse(result.download_url).path).suffix.lower() or ".bin"

    def download(self, result: SearchResult) -> LibraryItem:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / self.normalize_filename(result, self._suffix_for(result))
        if target.exists() and self.sidecar_path(target).exists():
            return self._read_item(target)
        response = self.client.get(result.download_url)
        response.raise_for_status()
        temporary = target.with_suffix(target.suffix + ".part")
        try:
            temporary.write_bytes(response.content)
            temporary.replace(target)
            downloaded_at = datetime.now(timezone.utc)
            record = dataclasses.asdict(result)
            record["downloaded_at"] = downloaded_at.isoformat()
            self.sidecar_path(target).write_text(
                json.dumps(record, indent=2), encoding="utf-8"
            )
            return LibraryItem(target, downloaded_at, result)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def _read_item(self, path: Path) -> LibraryItem:
        data = json.loads(self.sidecar_path(path).read_text(encoding="utf-8"))
        return LibraryItem(
            path,
            datetime.fromisoformat(data.pop("downloaded_at")),
            SearchResult(**data),
        )

    def items(self) -> list[LibraryItem]:
        if not self.root.exists():
            return []
        found = []
        for sidecar in sorted(self.root.glob(f"*{SIDECAR_SUFFIX}")):
            asset = Path(str(sidecar)[: -len(SIDECAR_SUFFIX)])
            if asset.exists():
                found.append(self._read_item(asset))
        return found
