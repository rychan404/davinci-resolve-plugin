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
MIN_HOST_INTERVAL = 0.2
RELAX_FACTOR = 0.7
MAX_ATTEMPTS = 6
MAX_BACKOFF = 8.0
PREVIEW_URL_ROLE = Qt.UserRole + 1
PREVIEW_STATE_ROLE = Qt.UserRole + 2
PRELOAD_MARGIN = 200
INITIAL_BATCH = 24


RETRYABLE_STATUSES = {429, 424}


class ThumbnailFetcher:
    """Fetch previews at a pace the image CDNs tolerate.

    A search asks for dozens of thumbnails at once, and Commons' CDN answers a
    burst like that with 429 and a Retry-After of a second or two. Spacing
    requests per host and retrying on 429 turns a transient throttle back into a
    visible thumbnail instead of a permanently empty tile. The spacing widens
    whenever a host pushes back and relaxes again once it stops.

    Commons also answers occasional single files with 424 (Failed Dependency)
    when its own thumbnail render failed, unrelated to rate limiting. That is
    usually transient too, so it gets a plain retry with a short flat delay —
    without widening the whole host's pacing, since the problem is specific to
    one file rather than a signal every other request should slow down.
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
            if response.status_code not in RETRYABLE_STATUSES:
                response.raise_for_status()
                self._relax(host)
                return response.content
            if attempt == self.max_attempts:
                response.raise_for_status()
            if response.status_code == 429:
                self._throttle(host, self._retry_after(response))
            else:
                self.sleep(self._retry_after(response))
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
            # Ease off geometrically. Halving oscillated straight back into the
            # limit back when a contactless User-Agent bought only an 8-request
            # burst; with contact details the budget is ~31, so recovery this
            # brisk is safe and keeps one early 429 from slowing a whole search.
            state["interval"] = max(self.min_interval, state["interval"] * RELAX_FACTOR)

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
    preview_progress = Signal(int, int)

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
        self._resolved_urls, self._resolved_tiles = set(), 0
        self._requested_urls, self._requested_tiles = set(), 0
        self.loader = loader or ThumbnailLoader()
        self.loader.setParent(self)
        self.loader.signals.loaded.connect(self._apply_thumbnail)
        self.loader.signals.failed.connect(self._mark_thumbnail_failed)
        self.itemDoubleClicked.connect(self._emit_download)
        self.verticalScrollBar().valueChanged.connect(self.request_visible_previews)

    def set_results(self, results: list[SearchResult]) -> None:
        self.clear()
        self._results.clear()
        self._items_by_url.clear()
        self._resolved_urls.clear()
        self._requested_urls.clear()
        self._resolved_tiles, self._requested_tiles = 0, 0
        self.loader.begin_generation()
        pending = self.style().standardIcon(QStyle.SP_BrowserReload)
        for result in results:
            entry = QListWidgetItem(f"{result.title}\n[{result.source}]")
            entry.setData(Qt.UserRole, result.uid)
            entry.setData(PREVIEW_URL_ROLE, result.preview_url)
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
            self._set_state(entry, "pending", pending)
            self.addItem(entry)
            self._results[result.uid] = result
            if not result.preview_url:
                self._mark_entry_failed(entry, "This result has no preview image.")
                # No loader work is coming for this tile, so it already counts
                # toward the denominator alongside tiles that get requested.
                self._requested_tiles += 1
                self._count_resolved(1)
                continue
            self._items_by_url.setdefault(result.preview_url, []).append(entry)
        self.preview_progress.emit(self._resolved_tiles, self._requested_tiles)
        self.request_visible_previews()

    def results(self) -> list[SearchResult]:
        return [
            self._results[self.item(index).data(Qt.UserRole)]
            for index in range(self.count())
        ]

    def preview_counts(self) -> tuple[int, int]:
        """Tiles whose preview has settled, and tiles actually requested."""
        return self._resolved_tiles, self._requested_tiles

    def request_visible_previews(self) -> None:
        """Fetch previews for tiles on screen, and for a margin either side.

        Requesting all forty results of a search at once queues them behind one
        host's pace gate, so tiles nobody is looking at delay the ones in view.
        """
        for url in self._visible_preview_urls():
            if url in self._requested_urls:
                continue
            self._requested_urls.add(url)
            # A single preview URL can back multiple grid entries, and each
            # entry is a separate tile the progress readout must account for.
            self._requested_tiles += len(self._items_by_url.get(url, []))
            self.loader.load(url)

    def _visible_preview_urls(self) -> list[str]:
        if not self.isVisible() or self.viewport().height() <= 0:
            # Never shown, or laid out yet — fall back to a first screenful.
            # A never-shown top-level QListWidget already reports a nonzero
            # default viewport size, so height() alone cannot detect this case;
            # isVisible() stays False until show() + processEvents() run.
            return self._preview_urls()[:INITIAL_BATCH]
        visible = self.viewport().rect().adjusted(0, -PRELOAD_MARGIN, 0, PRELOAD_MARGIN)
        urls = []
        for index in range(self.count()):
            entry = self.item(index)
            url = entry.data(PREVIEW_URL_ROLE)
            if url and self.visualItemRect(entry).intersects(visible):
                urls.append(url)
        return urls

    def _preview_urls(self) -> list[str]:
        seen, urls = set(), []
        for index in range(self.count()):
            url = self.item(index).data(PREVIEW_URL_ROLE)
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
        return urls

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.request_visible_previews()

    def _set_state(self, entry, state: str, icon) -> None:
        entry.setData(PREVIEW_STATE_ROLE, state)
        entry.setIcon(icon)

    def _count_resolved(self, tiles: int) -> None:
        self._resolved_tiles += tiles
        self.preview_progress.emit(self._resolved_tiles, self._requested_tiles)

    def _apply_thumbnail(self, url: str, data: bytes) -> None:
        pixmap = pixmap_from_bytes(data)
        if pixmap.isNull():
            self._mark_thumbnail_failed(
                url, "The preview format could not be rendered."
            )
            return
        entries = self._items_by_url.get(url, [])
        for entry in entries:
            self._set_state(entry, "loaded", QIcon(pixmap))
        if entries and url not in self._resolved_urls:
            self._resolved_urls.add(url)
            self._count_resolved(len(entries))

    def _mark_thumbnail_failed(self, url: str, message: str) -> None:
        entries = self._items_by_url.get(url, [])
        for entry in entries:
            self._mark_entry_failed(entry, message)
        if entries and url not in self._resolved_urls:
            self._resolved_urls.add(url)
            self._count_resolved(len(entries))

    def _mark_entry_failed(self, entry, message: str) -> None:
        entry.setToolTip(f"{entry.toolTip()}\n\nThumbnail unavailable: {message}")
        self._set_state(
            entry, "failed", self.style().standardIcon(QStyle.SP_MessageBoxWarning)
        )

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
