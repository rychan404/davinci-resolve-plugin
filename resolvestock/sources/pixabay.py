"""Pixabay adapter; searches only, never mass-downloads."""

from resolvestock.models import SearchResult
from resolvestock.sources.base import CachedHttp, SearchQuery, Source

ENDPOINT = "https://pixabay.com/api/"
# Pixabay answers 400 rather than an empty page once a request leaves the
# documented ranges, and the registry would report that as a failed source.
MIN_PER_PAGE, MAX_PER_PAGE = 3, 200
MAX_QUERY_CHARS = 100
# Only the first 500 hits of any query are reachable, whatever totalHits says.
RESULT_CEILING = 500
ALPHA_EXTENSIONS = {"png", "svg", "gif", "webp"}


def image_type_for(query: SearchQuery) -> str:
    if query.vectors_only:
        return "vector"
    return "photo" if query.photos_only else "all"


def extension_of(url: str) -> str:
    return url.rsplit(".", 1)[-1].lower() if "." in url.rsplit("/", 1)[-1] else ""


class PixabaySource(Source):
    name, requires_key = "pixabay", True

    def __init__(self, http: CachedHttp, api_key: str):
        self.http, self.api_key = http, api_key

    def search(self, query: SearchQuery) -> list[SearchResult]:
        per_page = min(max(query.per_page, MIN_PER_PAGE), MAX_PER_PAGE)
        if (query.page - 1) * per_page >= RESULT_CEILING:
            return []
        params = {
            "key": self.api_key,
            "q": query.text[:MAX_QUERY_CHARS].strip(),
            "page": query.page,
            "per_page": per_page,
            "image_type": image_type_for(query),
            "safesearch": "true",
        }
        if query.transparent_only:
            params["colors"] = "transparent"
        return self.parse(self.http.get_json(ENDPOINT, params))

    def parse(self, payload: dict) -> list[SearchResult]:
        results = []
        for hit in payload.get("hits", []):
            source_id = str(hit.get("id") or "")
            if not source_id:
                # An empty id collapses uid to "pixabay:", which the registry's
                # dedupe would then treat as one repeated result.
                continue
            tags = hit.get("tags") or ""
            title = tags.split(",")[0].strip() or "untitled"
            download_url = (
                hit.get("largeImageURL")
                or hit.get("webformatURL")
                or hit.get("previewURL")
                or ""
            )
            user = hit.get("user")
            results.append(
                SearchResult(
                    self.name,
                    source_id,
                    title,
                    hit.get("previewURL") or "",
                    download_url,
                    "vector"
                    if "vector" in (hit.get("type") or "").lower()
                    else "image",
                    hit.get("imageWidth"),
                    hit.get("imageHeight"),
                    extension_of(download_url) in ALPHA_EXTENSIONS
                    if extension_of(download_url)
                    else None,
                    "pixabay",
                    "https://pixabay.com/service/license-summary/",
                    f"{title} by {user} (Pixabay)" if user else f"{title} (Pixabay)",
                    hit.get("pageURL") or "",
                )
            )
        return results
