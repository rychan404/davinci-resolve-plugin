"""Openverse image-search adapter."""

from resolvestock.licenses import normalize_license_id
from resolvestock.models import SearchResult
from resolvestock.sources.base import CachedHttp, SearchQuery, Source

ENDPOINT = "https://api.openverse.org/v1/images/"


class OpenverseSource(Source):
    name = "openverse"

    def __init__(self, http: CachedHttp):
        self.http = http

    def search(self, query: SearchQuery) -> list[SearchResult]:
        params = {"q": query.text, "page": query.page, "page_size": query.per_page}
        if query.vectors_only:
            params["extension"] = "svg"
        elif query.transparent_only:
            params["extension"] = "png,svg"
        if query.commercial_safe_only:
            params["license_type"] = "commercial,modification"
        return self.parse(self.http.get_json(ENDPOINT, params))

    def parse(self, payload: dict) -> list[SearchResult]:
        found = []
        for record in payload.get("results", []):
            filetype = (record.get("filetype") or "").lower()
            title, creator = (
                record.get("title") or "untitled",
                record.get("creator") or "",
            )
            found.append(
                SearchResult(
                    self.name,
                    str(record.get("id", "")),
                    title,
                    record.get("thumbnail") or record.get("url") or "",
                    record.get("url") or "",
                    "vector" if filetype == "svg" else "image",
                    record.get("width"),
                    record.get("height"),
                    filetype in {"png", "svg", "gif", "webp"} if filetype else None,
                    normalize_license_id(record.get("license") or ""),
                    record.get("license_url") or "",
                    f"{title} by {creator} (Openverse)"
                    if creator
                    else f"{title} (Openverse)",
                    record.get("foreign_landing_url") or record.get("url") or "",
                )
            )
        return found
