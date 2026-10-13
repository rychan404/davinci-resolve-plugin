"""Shared source contracts and cached HTTP access."""

from __future__ import annotations
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
import httpx
from resolvestock.cache import ResponseCache, make_key
from resolvestock.models import SearchResult

# Wikimedia rejects contactless agents with a 429 robot-policy error, so the
# project URL has to travel with every request.
HOMEPAGE = "https://github.com/rychan404/davinci-resolve-plugin"
USER_AGENT = f"resolvestock/0.1 ({HOMEPAGE}) python-httpx"

# Search runs on the UI thread, so a 429 earns one short wait, not a long stall.
# ponytail: single capped retry; move search off the UI thread if longer waits matter.
MAX_RETRY_WAIT = 5.0


@dataclass(frozen=True)
class SearchQuery:
    text: str
    page: int = 1
    per_page: int = 40
    transparent_only: bool = False
    vectors_only: bool = False
    commercial_safe_only: bool = True
    # Appended deliberately: cli.py constructs this positionally, so new fields
    # have to land after commercial_safe_only.
    photos_only: bool = False


class CachedHttp:
    def __init__(
        self,
        cache: ResponseCache,
        client: httpx.Client | None = None,
        sleep=time.sleep,
    ):
        self.sleep = sleep
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
        if response.status_code == 429 and (wait := _retry_wait(response)) is not None:
            self.sleep(wait)
            response = self.client.get(url, params=params)
        response.raise_for_status()
        self.cache.set(key, response.text)
        return response.json()


def _retry_wait(response: httpx.Response) -> float | None:
    """Seconds to wait before retrying, or None when the wait is too long."""
    # Pixabay reports its window reset in X-RateLimit-Reset, not Retry-After.
    header = response.headers.get("Retry-After") or response.headers.get(
        "X-RateLimit-Reset", "1"
    )
    try:
        seconds = max(float(header), 0.1)
    except ValueError:  # An HTTP-date we do not need to parse.
        seconds = 1.0
    return seconds if seconds <= MAX_RETRY_WAIT else None


class Source(ABC):
    name: str
    requires_key = False

    @abstractmethod
    def search(self, query: SearchQuery) -> list[SearchResult]: ...
