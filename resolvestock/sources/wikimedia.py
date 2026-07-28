"""Wikimedia Commons adapter."""

from __future__ import annotations
import re
from resolvestock.licenses import normalize_license_id
from resolvestock.models import SearchResult
from resolvestock.sources.base import CachedHttp, SearchQuery, Source

ENDPOINT = "https://commons.wikimedia.org/w/api.php"
TAG_PATTERN = re.compile(r"<[^>]+>")


def strip_html(value: str) -> str:
    return TAG_PATTERN.sub("", value).strip()


class WikimediaSource(Source):
    name = "wikimedia"

    def __init__(self, http: CachedHttp):
        self.http = http

    def search(self, query: SearchQuery) -> list[SearchResult]:
        terms = query.text
        if query.vectors_only:
            terms = f"filetype:drawing {terms}"
        elif query.transparent_only:
            terms = f"filemime:png {terms}"
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": terms,
            "gsrnamespace": 6,
            "gsrlimit": query.per_page,
            "gsroffset": (query.page - 1) * query.per_page,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 320,
        }
        return self.parse(self.http.get_json(ENDPOINT, params))

    def parse(self, payload: dict) -> list[SearchResult]:
        results = []
        for page in (payload.get("query", {}).get("pages", {}) or {}).values():
            infos = page.get("imageinfo") or []
            if not infos:
                continue
            info, meta = infos[0], infos[0].get("extmetadata") or {}
            mime = (info.get("mime") or "").lower()
            title = page.get("title", "").removeprefix("File:") or "untitled"
            artist = strip_html((meta.get("Artist") or {}).get("value", ""))
            results.append(
                SearchResult(
                    self.name,
                    str(page.get("pageid", "")),
                    title,
                    info.get("thumburl") or info.get("url") or "",
                    info.get("url") or "",
                    "vector" if mime == "image/svg+xml" else "image",
                    info.get("width"),
                    info.get("height"),
                    mime in {"image/png", "image/svg+xml", "image/webp", "image/gif"}
                    if mime
                    else None,
                    normalize_license_id(
                        (meta.get("LicenseShortName") or {}).get("value", "")
                    ),
                    (meta.get("LicenseUrl") or {}).get("value", ""),
                    f"{title} by {artist} (Wikimedia Commons)"
                    if artist
                    else f"{title} (Wikimedia Commons)",
                    info.get("descriptionurl") or "",
                )
            )
        return results
