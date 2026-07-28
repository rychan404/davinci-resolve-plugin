import httpx
import json
from pathlib import Path
from resolvestock.cache import ResponseCache
from resolvestock.sources.base import CachedHttp, SearchQuery
from resolvestock.sources.openverse import OpenverseSource
from resolvestock.sources.pixabay import PixabaySource
from resolvestock.sources.wikimedia import WikimediaSource


FIXTURES = Path(__file__).parent / "fixtures"


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
