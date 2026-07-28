import httpx
import json
import re
from pathlib import Path
from resolvestock.cache import ResponseCache
from resolvestock.sources.base import CachedHttp, SearchQuery, USER_AGENT
from resolvestock.sources.openverse import OpenverseSource
from resolvestock.sources.pixabay import PixabaySource
from resolvestock.sources.wikimedia import WikimediaSource


FIXTURES = Path(__file__).parent / "fixtures"


def test_openverse_keeps_page_size_within_the_anonymous_limit(tmp_path):
    # Openverse answers 401 to anonymous requests for more than 20 per page,
    # which silently drops the whole source out of a search.
    captured = {}

    def handler(request):
        captured.update(dict(request.url.params))
        return httpx.Response(200, json={"results": []})

    http = CachedHttp(
        ResponseCache(tmp_path / "cache.db"),
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    OpenverseSource(http).search(SearchQuery("piano", per_page=40))
    assert captured["page_size"] == "20"


def test_user_agent_identifies_the_tool_and_a_way_to_reach_it():
    # Wikimedia serves 429 "does not comply with our robot policy" to agents
    # that carry no contact details:
    # https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy
    assert USER_AGENT.startswith("resolvestock/")
    assert re.search(r"https?://\S+|\S+@\S+", USER_AGENT)


def source(tmp_path, adapter, payload):
    http = CachedHttp(
        ResponseCache(tmp_path / "cache.db"),
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
        ),
    )
    return adapter(http)


def test_openverse_normalizes_svg_and_attribution(tmp_path):
    payload = json.loads((FIXTURES / "openverse_transparent.json").read_text())
    adapter = source(tmp_path, OpenverseSource, payload)
    parsed = adapter.search(SearchQuery("arrow"))
    assert parsed[0].media_type == "vector" and parsed[0].license_id == "cc-by"


def test_wikimedia_reads_extmetadata(tmp_path):
    payload = json.loads((FIXTURES / "wikimedia_search.json").read_text())
    parsed = source(tmp_path, WikimediaSource, payload).search(SearchQuery("x"))
    assert parsed[0].license_id == "cc-by" and "Fixture Author" in parsed[0].attribution


def test_pixabay_uses_largest_asset_and_transparent_filter(tmp_path):
    captured = []
    payload = json.loads((FIXTURES / "pixabay_transparent.json").read_text())

    def handler(request):
        captured.append(dict(request.url.params))
        return httpx.Response(200, json=payload)

    adapter = PixabaySource(
        CachedHttp(
            ResponseCache(tmp_path / "cache.db"),
            httpx.Client(transport=httpx.MockTransport(handler)),
        ),
        "key",
    )
    assert adapter.search(SearchQuery("arrow", transparent_only=True))[
        0
    ].download_url == ("https://example.invalid/large.png")
    assert captured[0]["colors"] == "transparent"
