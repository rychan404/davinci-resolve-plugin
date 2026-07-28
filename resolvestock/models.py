"""Core data types shared by every layer."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MediaType = str


@dataclass(frozen=True)
class SearchResult:
    source: str
    source_id: str
    title: str
    preview_url: str
    download_url: str
    media_type: MediaType
    width: int | None
    height: int | None
    has_alpha: bool | None
    license_id: str
    license_url: str
    attribution: str
    source_page_url: str

    @property
    def uid(self) -> str:
        return f"{self.source}:{self.source_id}"


@dataclass(frozen=True)
class LibraryItem:
    local_path: Path
    downloaded_at: datetime
    result: SearchResult
