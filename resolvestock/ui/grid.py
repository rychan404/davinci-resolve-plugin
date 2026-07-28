"""Remote search grid with asynchronous thumbnails."""

import threading
import time
from urllib.parse import urlsplit

import httpx
from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QStyle
from resolvestock.licenses import get_license
from resolvestock.models import SearchResult
from resolvestock.sources.base import USER_AGENT

ACCEPT = "image/avif,image/webp,image/png,image/jpeg,image/svg+xml,*/*"
THUMBNAIL_THREADS = 3
MIN_HOST_INTERVAL = 0.5
MAX_ATTEMPTS = 6
MAX_BACKOFF = 8.0


class ThumbnailFetcher:
    """Fetch previews at a pace the image CDNs tolerate.

    A search asks for dozens of thumbnails at once, and Commons' CDN answers a
    burst like that with 429 and a Retry-After of a second or two. Spacing
    requests per host and retrying on 429 turns a transient throttle back into a
    visible thumbnail instead of a permanently empty tile. The spacing widens
    whenever a host pushes back and relaxes again once it stops.
    """

    def __init__(
        self,
        client=None,
        max_attempts=MAX_ATTEMPTS,
        min_interval=MIN_HOST_INTERVAL,
        max_backoff=MAX_BACKOFF,
        sleep=time.sleep,
        clock=time.monotonic,
    ):
        self.client = client or httpx.Client(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": ACCEPT},
            limits=httpx.Limits(
                max_connections=THUMBNAIL_THREADS,
                max_keepalive_connections=THUMBNAIL_THREADS,
            ),
        )
        self.max_attempts, self.min_interval = max_attempts, min_interval
        self.max_backoff, self.sleep, self.clock = max_backoff, sleep, clock
        self._lock, self._hosts = threading.Lock(), {}

    def fetch(self, url: str) -> bytes:
        host = urlsplit(url).netloc
        for attempt in range(1, self.max_attempts + 1):
            self._wait_for_turn(host)
            response = self.client.get(url)
            if response.status_code != 429:
                response.raise_for_status()
                self._relax(host)
                return response.content
            if attempt == self.max_attempts:
                response.raise_for_status()
            self._throttle(host, self._retry_after(response))
        raise AssertionError("unreachable")

    def close(self) -> None:
        self.client.close()

    def _state(self, host: str) -> dict:
        return self._hosts.setdefault(
            host, {"ready": None, "interval": self.min_interval}
        )

    def _wait_for_turn(self, host: str) -> None:
        with self._lock:
            state, now = self._state(host), self.clock()
            ready = now if state["ready"] is None else state["ready"]
            state["ready"] = max(ready, now) + state["interval"]
        if (delay := ready - now) > 0:
            self.sleep(delay)

    def _throttle(self, host: str, seconds: float) -> None:
        with self._lock:
            state, now = self._state(host), self.clock()
            # Retry-After understates how long these CDNs stay annoyed, so widen
            # the spacing geometrically until the host stops pushing back.
            state["interval"] = min(
                self.max_backoff, max(state["interval"] * 2, seconds)
            )
            ready = now if state["ready"] is None else state["ready"]
            state["ready"] = max(ready, now + seconds)

    def _relax(self, host: str) -> None:
        with self._lock:
            state = self._state(host)
            # Ease off slowly; halving here just walks straight back into the limit.
            state["interval"] = max(self.min_interval, state["interval"] * 0.9)

    def _retry_after(self, response) -> float:
        try:
            seconds = float(response.headers.get("Retry-After", ""))
        except ValueError:  # Absent, or an HTTP-date we do not need to parse.
            seconds = 1.0
        return min(self.max_backoff, max(seconds, 0.1))


class _ThumbnailSignals(QObject):
    loaded = Signal(str, bytes)
    failed = Signal(str, str)


class _ThumbnailJob(QRunnable):
    def __init__(self, url, generation, loader):
        super().__init__()
        self.url, self.generation, self.loader = url, generation, loader

    def run(self):
        try:
            if not self.loader.is_current(self.generation):
                return  # A newer search replaced these tiles; skip the request.
            data = self.loader.fetcher.fetch(self.url)
        except Exception as error:  # A missing preview must not break a search.
            self.loader.signals.failed.emit(self.url, str(error))
        else:
            self.loader.signals.loaded.emit(self.url, data)
        finally:
            # Retiring only after the emit keeps this job — and through it the
            # loader that owns the signals — alive while the signal is queued.
            self.loader.retire(self)


class ThumbnailLoader(QObject):
    def __init__(self, parent=None, fetcher=None, pool=None):
        super().__init__(parent)
        self.fetcher = fetcher or ThumbnailFetcher()
        # A dedicated pool so a slow CDN cannot starve downloads of the global one.
        self.pool = pool or QThreadPool(self)
        self.pool.setMaxThreadCount(THUMBNAIL_THREADS)
        self.signals = _ThumbnailSignals(self)
        self._generation, self._active_jobs = 0, set()

    def begin_generation(self) -> int:
        """Invalidate jobs queued for the previous search."""
        self._generation += 1
        return self._generation

    def stop(self) -> None:
        """Abandon outstanding previews.

        QThreadPool waits for its whole backlog on destruction, so without this
        a queued search can hold the window open for as long as the retries run.
        Invalidating the generation makes those jobs return without a request.
        """
        self.begin_generation()

    def is_current(self, generation: int) -> bool:
        return generation == self._generation

    def load(self, url: str) -> None:
        job = _ThumbnailJob(url, self._generation, self)
        self._active_jobs.add(job)
        self.pool.start(job)

    def retire(self, job) -> None:
        self._active_jobs.discard(job)


class ResultsGrid(QListWidget):
    download_requested = Signal(object)

    def __init__(self, parent=None, loader=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QSize(160, 120))
        self.setGridSize(QSize(180, 170))
        self.setResizeMode(QListWidget.Adjust)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setDragEnabled(False)
        self.setWordWrap(True)
        self._results, self._items_by_url = {}, {}
        self.loader = loader or ThumbnailLoader()
        self.loader.setParent(self)
        self.loader.signals.loaded.connect(self._apply_thumbnail)
        self.loader.signals.failed.connect(self._mark_thumbnail_failed)
        self.itemDoubleClicked.connect(self._emit_download)

    def set_results(self, results: list[SearchResult]) -> None:
        self.clear()
        self._results.clear()
        self._items_by_url.clear()
        self.loader.begin_generation()
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
            if not result.preview_url:
                self._mark_entry_failed(entry, "This result has no preview image.")
                continue
            entries = self._items_by_url.setdefault(result.preview_url, [])
            entries.append(entry)
            if len(entries) == 1:
                self.loader.load(result.preview_url)

    def results(self) -> list[SearchResult]:
        return [
            self._results[self.item(index).data(Qt.UserRole)]
            for index in range(self.count())
        ]

    def _apply_thumbnail(self, url: str, data: bytes) -> None:
        pixmap = pixmap_from_bytes(data)
        if pixmap.isNull():
            self._mark_thumbnail_failed(
                url, "The preview format could not be rendered."
            )
            return
        for entry in self._items_by_url.get(url, []):
            entry.setIcon(QIcon(pixmap))

    def _mark_thumbnail_failed(self, url: str, message: str) -> None:
        for entry in self._items_by_url.get(url, []):
            self._mark_entry_failed(entry, message)

    def _mark_entry_failed(self, entry, message: str) -> None:
        entry.setToolTip(f"{entry.toolTip()}\n\nThumbnail unavailable: {message}")

    def _emit_download(self, entry):
        if result := self._results.get(entry.data(Qt.UserRole)):
            self.download_requested.emit(result)


def pixmap_from_bytes(data: bytes) -> QPixmap:
    """Decode raster previews and render SVG previews Qt cannot load directly."""
    pixmap = QPixmap()
    if pixmap.loadFromData(data):
        return pixmap
    renderer = QSvgRenderer(data)
    if not renderer.isValid():
        return pixmap
    size = renderer.defaultSize()
    if size.isEmpty():
        size = QSize(320, 240)
    image = QImage(size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return QPixmap.fromImage(image)
