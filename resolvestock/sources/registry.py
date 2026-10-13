"""Fault-tolerant fan-out across configured sources."""

from dataclasses import dataclass, field
from itertools import zip_longest
from resolvestock.licenses import filter_commercial_safe
from resolvestock.models import SearchResult
from resolvestock.sources.base import SearchQuery, Source


@dataclass
class SearchOutcome:
    results: list[SearchResult] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


class SourceRegistry:
    def __init__(self, sources: list[Source]):
        self.sources = sources

    def search(self, query: SearchQuery) -> SearchOutcome:
        outcome, per_source = SearchOutcome(), []
        sources = [
            source for source in self.sources if query.source in (None, source.name)
        ]
        if query.source and not sources:
            outcome.errors[query.source] = "not configured"
        for source in sources:
            try:
                per_source.append(source.search(query))
            except Exception as error:
                outcome.errors[source.name] = str(error)
        merged = [
            result
            for group in zip_longest(*per_source)
            for result in group
            if result is not None
        ]
        if query.commercial_safe_only:
            merged = filter_commercial_safe(merged)
        seen = set()
        outcome.results = [
            item for item in merged if not (item.uid in seen or seen.add(item.uid))
        ]
        return outcome


def build_registry(http, config) -> SourceRegistry:
    from resolvestock.sources.openverse import OpenverseSource
    from resolvestock.sources.wikimedia import WikimediaSource
    from resolvestock.sources.pixabay import PixabaySource

    sources = [OpenverseSource(http), WikimediaSource(http)]
    if config.pixabay_key:
        sources.append(PixabaySource(http, config.pixabay_key))
    return SourceRegistry(sources)
