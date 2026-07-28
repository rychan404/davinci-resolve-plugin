"""Pixabay adapter; searches only, never mass-downloads."""

from resolvestock.models import SearchResult
from resolvestock.sources.base import CachedHttp, SearchQuery, Source

ENDPOINT = "https://pixabay.com/api/"


class PixabaySource(Source):
    name, requires_key = "pixabay", True

    def __init__(self, http: CachedHttp, api_key: str):
        self.http, self.api_key = http, api_key

    def search(self, query: SearchQuery) -> list[SearchResult]:
        params = {
            "key": self.api_key,
            "q": query.text,
            "page": query.page,
            "per_page": query.per_page,
            "image_type": "vector" if query.vectors_only else "all",
            "safesearch": "true",
        }
        if query.transparent_only:
            params["colors"] = "transparent"
        return self.parse(self.http.get_json(ENDPOINT, params))

    def parse(self, payload: dict) -> list[SearchResult]:
        return [
            SearchResult(
                self.name,
                str(hit.get("id", "")),
                hit.get("tags") or "untitled",
                hit.get("previewURL") or "",
                hit.get("largeImageURL")
                or hit.get("webformatURL")
                or hit.get("previewURL")
                or "",
                "vector" if "vector" in (hit.get("type") or "").lower() else "image",
                hit.get("imageWidth"),
                hit.get("imageHeight"),
                None,
                "pixabay",
                "https://pixabay.com/service/license-summary/",
                f"{hit.get('tags') or 'untitled'} by {hit.get('user')} (Pixabay)"
                if hit.get("user")
                else f"{hit.get('tags') or 'untitled'} (Pixabay)",
                hit.get("pageURL") or "",
            )
            for hit in payload.get("hits", [])
        ]
