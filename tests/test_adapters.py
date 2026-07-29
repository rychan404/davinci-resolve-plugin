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


def pixabay(tmp_path, fixture="pixabay_transparent.json"):
    captured = []
    payload = json.loads((FIXTURES / fixture).read_text())

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
    return adapter, captured


def test_pixabay_uses_largest_asset_and_transparent_filter(tmp_path):
    adapter, captured = pixabay(tmp_path)
    assert adapter.search(SearchQuery("arrow", transparent_only=True))[
        0
    ].download_url == ("https://example.invalid/large.png")
    assert captured[0]["colors"] == "transparent"


def test_pixabay_stops_before_the_reachable_result_ceiling(tmp_path):
    # Pixabay exposes at most 500 results per query and answers 400 beyond
    # them, which the registry would surface as a raw transport error.
    adapter, captured = pixabay(tmp_path)
    assert adapter.search(SearchQuery("arrow", page=14, per_page=40)) == []
    assert captured == []


def test_pixabay_keeps_page_size_within_the_documented_maximum(tmp_path):
    # per_page above 200 is another 400.
    adapter, captured = pixabay(tmp_path)
    adapter.search(SearchQuery("arrow", per_page=500))
    assert captured[0]["per_page"] == "200"


def test_pixabay_truncates_queries_to_the_documented_maximum(tmp_path):
    # q longer than 100 characters is another 400.
    adapter, captured = pixabay(tmp_path)
    adapter.search(SearchQuery("dog " * 40))
    assert len(captured[0]["q"]) <= 100


def test_pixabay_asks_for_photos_when_the_query_wants_photos(tmp_path):
    # image_type=all mixes illustrations and clipart into photo results.
    adapter, captured = pixabay(tmp_path, "pixabay_photos.json")
    adapter.search(SearchQuery("retriever", photos_only=True))
    assert captured[0]["image_type"] == "photo"


def test_pixabay_reports_alpha_for_assets_delivered_as_png(tmp_path):
    adapter, _ = pixabay(tmp_path)
    assert adapter.search(SearchQuery("arrow"))[0].has_alpha is True


def test_pixabay_reports_no_alpha_for_photographs(tmp_path):
    adapter, _ = pixabay(tmp_path, "pixabay_photos.json")
    assert adapter.search(SearchQuery("retriever"))[0].has_alpha is False


def test_pixabay_titles_use_the_first_tag_not_the_whole_tag_list(tmp_path):
    adapter, _ = pixabay(tmp_path, "pixabay_photos.json")
    assert adapter.search(SearchQuery("retriever"))[0].title == "golden retriever"


def test_pixabay_skips_hits_without_an_id(tmp_path):
    # An empty source_id makes uid "pixabay:", so the registry's dedupe would
    # discard every id-less hit but the first.
    adapter, _ = pixabay(tmp_path, "pixabay_photos.json")
    assert [result.source_id for result in adapter.search(SearchQuery("retriever"))] == [
        "2002"
    ]
