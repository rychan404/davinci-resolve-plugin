import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from resolvestock.config import Config
from resolvestock.models import LibraryItem, SearchResult
from resolvestock.sources.registry import SearchOutcome
from resolvestock.ui.grid import (
    ResultsGrid,
    ThumbnailFetcher,
    ThumbnailLoader,
    pixmap_from_bytes,
)
from resolvestock.ui.main_window import MainWindow
from resolvestock.ui.tray import LibraryTray


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def make_result(source_id="1"):
    return SearchResult(
        source="openverse",
        source_id=source_id,
        title="Smoke",
        preview_url="",
        download_url="https://example.invalid/smoke.png",
        media_type="image",
        width=100,
        height=100,
        has_alpha=True,
        license_id="cc-by",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        attribution="Smoke by Jane (Openverse)",
        source_page_url="https://example.invalid/page",
    )


def make_item(tmp_path, name="asset.png"):
    path = tmp_path / name
    path.write_bytes(b"not a real image")
    return LibraryItem(path, datetime.now(timezone.utc), make_result(name))


def test_tray_drag_carries_only_local_file_urls(app, tmp_path):
    tray = LibraryTray()
    item = make_item(tmp_path)
    tray.set_items([item])
    tray.selectAll()
    mime = tray.mimeData(tray.selectedItems())
    assert mime.hasUrls()
    assert Path(mime.urls()[0].toLocalFile()) == item.local_path
    assert tray.selected_paths() == [item.local_path]


def test_grid_is_not_a_drag_source_and_emits_downloads(app):
    grid = ResultsGrid()
    received = []
    grid.download_requested.connect(received.append)
    asset = make_result()
    grid.set_results([asset])
    grid.itemDoubleClicked.emit(grid.item(0))
    assert not grid.dragEnabled()
    assert grid.results() == [asset]
    assert received == [asset]


def test_grid_renders_svg_previews_and_marks_bad_previews(app):
    svg = b"""<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10'>
    <rect width='10' height='10' fill='red'/></svg>"""
    assert not pixmap_from_bytes(svg).isNull()
    asset = make_result()
    asset = SearchResult(
        **{**asset.__dict__, "preview_url": "https://example.invalid/p"}
    )
    grid = ResultsGrid()
    grid.set_results([asset])
    grid._apply_thumbnail(asset.preview_url, b"not an image")
    assert "Thumbnail unavailable" in grid.item(0).toolTip()


class FakeClock:
    """Deterministic stand-in for time.sleep/time.monotonic."""

    def __init__(self):
        self.now, self.slept = 0.0, []

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds

    def monotonic(self):
        return self.now


class ManualPool:
    """QThreadPool stand-in that runs jobs only when the test says so."""

    def __init__(self):
        self.jobs = []

    def setMaxThreadCount(self, count):
        self.max_thread_count = count

    def start(self, job):
        self.jobs.append(job)

    def run_all(self):
        jobs, self.jobs = self.jobs, []
        for job in jobs:
            job.run()


class RecordingFetcher:
    def __init__(self, payload=b"bytes"):
        self.payload, self.urls = payload, []

    def fetch(self, url):
        self.urls.append(url)
        return self.payload


def build_fetcher(handler, clock, **kwargs):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return ThumbnailFetcher(
        client=client, sleep=clock.sleep, clock=clock.monotonic, **kwargs
    )


def test_thumbnail_fetcher_retries_when_the_host_rate_limits(app):
    codes = [429, 200]

    def handler(request):
        code = codes.pop(0)
        if code == 429:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(200, content=b"payload")

    clock = FakeClock()
    fetcher = build_fetcher(handler, clock, min_interval=0)
    assert fetcher.fetch("https://upload.example.org/a.jpg") == b"payload"
    assert codes == []
    assert clock.slept == [1.0]


def test_thumbnail_fetcher_reports_failure_after_exhausting_retries(app):
    attempts = []

    def handler(request):
        attempts.append(request.url)
        return httpx.Response(429, headers={"Retry-After": "1"})

    clock = FakeClock()
    fetcher = build_fetcher(handler, clock, min_interval=0, max_attempts=3)
    with pytest.raises(httpx.HTTPStatusError):
        fetcher.fetch("https://upload.example.org/a.jpg")
    assert len(attempts) == 3


def test_thumbnail_fetcher_paces_requests_to_the_same_host(app):
    clock = FakeClock()
    fetcher = build_fetcher(
        lambda request: httpx.Response(200, content=b"ok"), clock, min_interval=0.5
    )
    fetcher.fetch("https://upload.example.org/a.jpg")
    fetcher.fetch("https://upload.example.org/b.jpg")
    assert clock.slept == [0.5]


def test_thumbnail_fetcher_paces_hosts_independently(app):
    clock = FakeClock()
    fetcher = build_fetcher(
        lambda request: httpx.Response(200, content=b"ok"), clock, min_interval=0.5
    )
    fetcher.fetch("https://upload.example.org/a.jpg")
    fetcher.fetch("https://cdn.example.net/b.jpg")
    assert clock.slept == []


def test_thumbnail_fetcher_backs_the_whole_host_off_after_a_429(app):
    codes = [429, 200, 200]

    def handler(request):
        if codes.pop(0) == 429:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, content=b"ok")

    clock = FakeClock()
    fetcher = build_fetcher(handler, clock, min_interval=0.1)
    fetcher.fetch("https://upload.example.org/a.jpg")
    clock.slept.clear()
    fetcher.fetch("https://upload.example.org/b.jpg")
    # The 429 widened the host's spacing, so later URLs pay for it too.
    assert clock.slept == [2.0]


def test_thumbnail_fetcher_recovers_its_pace_after_the_host_stops_pushing_back(app):
    # One 429 widens the spacing; a short run of successes must bring it back
    # down, otherwise a single early hiccup slows the whole rest of a search.
    codes = [429] + [200] * 6

    def handler(request):
        if codes.pop(0) == 429:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, content=b"ok")

    clock = FakeClock()
    fetcher = build_fetcher(handler, clock, min_interval=0.2)
    for index in range(6):
        fetcher.fetch(f"https://upload.example.org/{index}.jpg")

    interval = fetcher._hosts["upload.example.org"]["interval"]
    # After 429 and 6 relaxes (0.7^6), the interval should be near 0.2
    assert interval == pytest.approx(0.2, abs=0.04)


def test_thumbnail_loader_drops_jobs_from_a_superseded_search(app):
    pool, fetcher = ManualPool(), RecordingFetcher()
    loader = ThumbnailLoader(fetcher=fetcher, pool=pool)
    loader.begin_generation()
    loader.load("https://upload.example.org/stale.jpg")
    loader.begin_generation()
    loader.load("https://upload.example.org/fresh.jpg")
    pool.run_all()
    assert fetcher.urls == ["https://upload.example.org/fresh.jpg"]


def test_thumbnail_loader_keeps_jobs_alive_until_they_finish(app):
    pool, fetcher = ManualPool(), RecordingFetcher()
    loader = ThumbnailLoader(fetcher=fetcher, pool=pool)
    loader.begin_generation()
    loader.load("https://upload.example.org/a.jpg")
    assert len(loader._active_jobs) == 1
    pool.run_all()
    assert loader._active_jobs == set()


def test_thumbnail_loader_stop_abandons_pending_jobs(app):
    pool, fetcher = ManualPool(), RecordingFetcher()
    loader = ThumbnailLoader(fetcher=fetcher, pool=pool)
    loader.begin_generation()
    loader.load("https://upload.example.org/a.jpg")
    loader.stop()
    pool.run_all()
    assert fetcher.urls == []
    assert loader._active_jobs == set()


def test_closing_the_window_stops_thumbnail_work(app, tmp_path):
    window = MainWindow(
        FakeRegistry(),
        FakeLibrary(tmp_path / "library"),
        Config.load(tmp_path / "config.json"),
        )
    loader, fetcher = window.grid.loader, RecordingFetcher()
    loader.pool, loader.fetcher = ManualPool(), fetcher
    loader.begin_generation()
    loader.load("https://upload.example.org/a.jpg")
    window.close()
    loader.pool.run_all()
    assert fetcher.urls == []
    assert loader._active_jobs == set()


def test_grid_marks_results_without_a_preview_as_unavailable(app):
    grid = ResultsGrid(loader=ThumbnailLoader(fetcher=RecordingFetcher(), pool=ManualPool()))
    grid.set_results([make_result()])
    assert "Thumbnail unavailable" in grid.item(0).toolTip()


def test_grid_restarts_the_generation_for_each_search(app):
    pool, fetcher = ManualPool(), RecordingFetcher()
    grid = ResultsGrid(loader=ThumbnailLoader(fetcher=fetcher, pool=pool))
    asset = SearchResult(
        **{**make_result().__dict__, "preview_url": "https://upload.example.org/a.jpg"}
    )
    grid.set_results([asset])
    grid.set_results([asset])
    pool.run_all()
    assert fetcher.urls == ["https://upload.example.org/a.jpg"]


class FakeRegistry:
    def __init__(self):
        self.queries = []

    def search(self, query):
        self.queries.append(query)
        return SearchOutcome(results=[make_result()])


class FakeLibrary:
    def __init__(self, root):
        self.root = Path(root)
        self.downloaded = []

    def download(self, result):
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{result.source_id}.png"
        path.write_bytes(b"asset")
        item = LibraryItem(path, datetime.now(timezone.utc), result)
        self.downloaded.append(item)
        return item

    def items(self):
        return self.downloaded


def test_main_window_wires_search_download_and_credits(app, tmp_path):
    config = Config.load(tmp_path / "config.json")
    registry, library = FakeRegistry(), FakeLibrary(tmp_path / "library")
    window = MainWindow(registry, library, config)
    assert window.commercial_safe_checkbox.isChecked()
    window.search_input.setText("smoke")
    window.transparent_checkbox.setChecked(True)
    window.run_search()
    assert registry.queries[0].transparent_only
    assert window.grid.count() == 1
    window.download(make_result(), threaded=False)
    assert window.tray.count() == 1
    assert window._active_downloads == set()
    credits = window.export_credits(tmp_path / "CREDITS.txt")
    assert "Smoke by Jane" in credits.read_text(encoding="utf-8")


def test_threaded_download_keeps_its_worker_alive_until_completion(app, tmp_path):
    window = MainWindow(
        FakeRegistry(),
        FakeLibrary(tmp_path / "library"),
        Config.load(tmp_path / "config.json"),
    )
    window.download(make_result(), threaded=True)
    assert len(window._active_downloads) == 1
    deadline = time.monotonic() + 2
    while window._active_downloads and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert window._active_downloads == set()
    assert window.tray.count() == 1


def test_empty_main_window_search_stays_local(app, tmp_path):
    registry = FakeRegistry()
    window = MainWindow(
        registry, FakeLibrary(tmp_path / "library"), Config.load(tmp_path / "c")
    )
    window.search_input.setText(" ")
    window.run_search()
    assert registry.queries == []
    assert "enter a search term" == window.status_label.text()
