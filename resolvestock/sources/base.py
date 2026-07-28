"""Shared source contracts and cached HTTP access."""

from __future__ import annotations
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
import httpx
from resolvestock.cache import ResponseCache, make_key
from resolvestock.models import SearchResult

# Wikimedia rejects contactless agents with a 429 robot-policy error, so the
# project URL has to travel with every request.
HOMEPAGE = "https://github.com/rychan404/davinci-resolve-plugin"
USER_AGENT = f"resolvestock/0.1 ({HOMEPAGE}) python-httpx"


@dataclass(frozen=True)
class SearchQuery:
    text: str
    page: int = 1
    per_page: int = 40
    transparent_only: bool = False
    vectors_only: bool = False
    commercial_safe_only: bool = True


class CachedHttp:
    def __init__(self, cache: ResponseCache, client: httpx.Client | None = None):
        self.cache, self.client = (
            cache,
            client
            or httpx.Client(
                timeout=15, headers={"User-Agent": USER_AGENT}, follow_redirects=True
            ),
        )

    def get_json(self, url: str, params: dict) -> dict:
        key = make_key(url, params)
        cached = self.cache.get(key)
        if cached is not None:
            return json.loads(cached)
        response = self.client.get(url, params=params)
        response.raise_for_status()
        self.cache.set(key, response.text)
        return response.json()


class Source(ABC):
    name: str
    requires_key = False

    @abstractmethod
    def search(self, query: SearchQuery) -> list[SearchResult]: ...
