"""Remote search grid with asynchronous thumbnails."""

import httpx
from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QStyle
from resolvestock.licenses import get_license
from resolvestock.models import SearchResult
from resolvestock.sources.base import USER_AGENT


class _ThumbnailSignals(QObject):
    loaded = Signal(str, bytes)


class _ThumbnailJob(QRunnable):
    def __init__(self, url, signals):
        super().__init__()
        self.url, self.signals = url, signals

    def run(self):
        try:
            response = httpx.get(
                self.url,
                timeout=15,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            self.signals.loaded.emit(self.url, response.content)
        except Exception:
            pass


class ThumbnailLoader(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pool = QThreadPool.globalInstance()
        self.signals = _ThumbnailSignals()

    def load(self, url: str) -> None:
        self.pool.start(_ThumbnailJob(url, self.signals))


class ResultsGrid(QListWidget):
    download_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QSize(160, 120))
        self.setGridSize(QSize(180, 170))
        self.setResizeMode(QListWidget.Adjust)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setDragEnabled(False)
        self.setWordWrap(True)
        self._results, self._items_by_url = {}, {}
        self.loader = ThumbnailLoader(self)
        self.loader.signals.loaded.connect(self._apply_thumbnail)
        self.itemDoubleClicked.connect(self._emit_download)

    def set_results(self, results: list[SearchResult]) -> None:
        self.clear()
        self._results.clear()
        self._items_by_url.clear()
        placeholder = self.style().standardIcon(QStyle.SP_FileIcon)
        for result in results:
            entry = QListWidgetItem(f"{result.title}\n[{result.source}]")
            entry.setData(Qt.UserRole, result.uid)
            size = (
                f"{result.width}x{result.height}"
                if result.width and result.height
                else "size unknown"
            )
            entry.setToolTip(
                f"{result.title}\n{size}\n"
                f"{get_license(result.license_id).name}\n"
                f"alpha={result.has_alpha}\n{result.source_page_url}"
            )
            entry.setIcon(placeholder)
            self.addItem(entry)
            self._results[result.uid] = result
            if result.preview_url:
                self._items_by_url[result.preview_url] = entry
                self.loader.load(result.preview_url)

    def results(self) -> list[SearchResult]:
        return [
            self._results[self.item(index).data(Qt.UserRole)]
            for index in range(self.count())
        ]

    def _apply_thumbnail(self, url, data):
        entry = self._items_by_url.get(url)
        pixmap = QPixmap()
        if entry is not None and pixmap.loadFromData(data):
            entry.setIcon(QIcon(pixmap))

    def _emit_download(self, entry):
        if result := self._results.get(entry.data(Qt.UserRole)):
            self.download_requested.emit(result)
