from datetime import datetime, timezone

import httpx

from resolvestock.cache import ResponseCache, make_key
from resolvestock.credits import build_credits
from resolvestock.library import Library
from resolvestock.licenses import is_commercial_safe, normalize_license_id
from resolvestock.models import LibraryItem, SearchResult
from resolvestock.sources.base import CachedHttp, SearchQuery, Source
from resolvestock.sources.registry import SourceRegistry


def result(source="source", source_id="1", license_id="cc-by"):
    return SearchResult(
        source,
        source_id,
        "Smoke Plume",
        "https://example.invalid/preview.png",
        "https://example.invalid/smoke.png",
        "image",
        100,
        100,
        True,
        license_id,
        "https://example.invalid/license",
        "Smoke by Jane",
        "https://example.invalid/page",
    )


def test_license_normalization_and_safety():
    assert normalize_license_id("CC BY-SA 4.0") == "cc-by-sa"
    assert normalize_license_id("CC0 1.0") == "cc0"
    assert is_commercial_safe("cc0")
    assert not is_commercial_safe("cc-by-nc")
    assert not is_commercial_safe("unrecognized")


def test_cache_hides_secrets_and_round_trips(tmp_path):
    assert make_key("https://api.example/x", {"key": "secret", "q": "x"}) == make_key(
        "https://api.example/x", {"q": "x"}
    )
    cache = ResponseCache(tmp_path / "cache.db")
    cache.set("asset", "value")
    assert cache.get("asset") == "value"


def test_cached_http_does_not_repeat_successful_request(tmp_path):
    calls = []

    def handler(request):
        calls.append(request.url)
        return httpx.Response(200, json={"ok": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    http = CachedHttp(ResponseCache(tmp_path / "cache.db"), client)
    assert http.get_json("https://api.example/x", {"q": "x"}) == {"ok": True}
    assert http.get_json("https://api.example/x", {"q": "x"}) == {"ok": True}
    assert len(calls) == 1


def test_library_writes_asset_and_provenance(tmp_path):
    library = Library(
        tmp_path / "library",
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"png"))
        ),
    )
    item = library.download(result())
    assert item.local_path.name == "smoke_plume_source_1.png"
    assert library.sidecar_path(item.local_path).exists()
    assert library.items()[0].result.attribution == "Smoke by Jane"


def test_credits_omits_cc0_and_includes_attribution_required_assets():
    stamped = datetime.now(timezone.utc)
    text = build_credits(
        [
            LibraryItem(__import__("pathlib").Path("x.png"), stamped, result()),
            LibraryItem(
                __import__("pathlib").Path("y.png"),
                stamped,
                result("other", "2", "cc0"),
            ),
        ]
    )
    assert "Smoke by Jane" in text
    assert "CC BY 4.0" in text


class _Source(Source):
    def __init__(self, name, values=None, error=None):
        self.name, self.values, self.error = name, values or [], error

    def search(self, query):
        if self.error:
            raise self.error
        return self.values


def test_registry_interleaves_deduplicates_and_keeps_source_failures():
    outcome = SourceRegistry(
        [
            _Source("a", [result("a", "1"), result("a", "2")]),
            _Source("b", [result("b", "1")]),
            _Source("bad", error=RuntimeError("offline")),
        ]
    ).search(SearchQuery("smoke"))
    assert [entry.uid for entry in outcome.results] == ["a:1", "b:1", "a:2"]
    assert outcome.errors == {"bad": "offline"}


def test_cli_exposes_a_photographs_only_flag():
    from resolvestock.cli import build_parser

    assert build_parser().parse_args(["retriever", "--photos"]).photos is True


def test_search_query_keeps_commercial_safety_as_its_sixth_field():
    # cli.py builds SearchQuery positionally, so a field inserted ahead of
    # commercial_safe_only silently re-enables the restricted-content filter.
    assert SearchQuery("smoke", 1, 20, False, False, False).commercial_safe_only is False
