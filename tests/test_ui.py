import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from resolvestock.config import Config
from resolvestock.models import LibraryItem, SearchResult
from resolvestock.sources.registry import SearchOutcome
from resolvestock.ui.grid import ResultsGrid, pixmap_from_bytes
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
