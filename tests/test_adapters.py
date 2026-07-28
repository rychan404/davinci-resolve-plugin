import httpx
from resolvestock.cache import ResponseCache
from resolvestock.sources.base import CachedHttp, SearchQuery
from resolvestock.sources.openverse import OpenverseSource
from resolvestock.sources.pixabay import PixabaySource
from resolvestock.sources.wikimedia import WikimediaSource


def source(tmp_path, adapter, payload):
    http = CachedHttp(
        ResponseCache(tmp_path / "cache.db"),
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
        ),
    )
    return adapter(http)


def test_openverse_normalizes_svg_and_attribution(tmp_path):
    adapter = source(
        tmp_path,
        OpenverseSource,
        {
            "results": [
                {
                    "id": "1",
                    "title": "Arrow",
                    "url": "https://e/a.svg",
                    "thumbnail": "https://e/a.png",
                    "license": "by",
                    "creator": "Jane",
                    "filetype": "svg",
                }
            ]
        },
    )
    parsed = adapter.search(SearchQuery("arrow"))
    assert parsed[0].media_type == "vector" and parsed[0].license_id == "cc-by"


def test_wikimedia_reads_extmetadata(tmp_path):
    payload = {
        "query": {
            "pages": {
                "1": {
                    "pageid": 1,
                    "title": "File:X.png",
                    "imageinfo": [
                        {
                            "url": "https://e/x.png",
                            "mime": "image/png",
                            "extmetadata": {
                                "LicenseShortName": {"value": "CC0"},
                                "Artist": {"value": "<b>Jane</b>"},
                            },
                        }
                    ],
                }
            }
        }
    }
    parsed = source(tmp_path, WikimediaSource, payload).search(SearchQuery("x"))
    assert parsed[0].license_id == "cc0" and "Jane" in parsed[0].attribution


def test_pixabay_uses_largest_asset_and_transparent_filter(tmp_path):
    captured = []

    def handler(request):
        captured.append(dict(request.url.params))
        return httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "id": 1,
                        "tags": "arrow",
                        "largeImageURL": "https://e/l.png",
                        "previewURL": "https://e/p.png",
                    }
                ]
            },
        )

    adapter = PixabaySource(
        CachedHttp(
            ResponseCache(tmp_path / "cache.db"),
            httpx.Client(transport=httpx.MockTransport(handler)),
        ),
        "key",
    )
    assert (
        adapter.search(SearchQuery("arrow", transparent_only=True))[0].download_url
        == "https://e/l.png"
    )
    assert captured[0]["colors"] == "transparent"
