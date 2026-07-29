# Thumbnail Loading Responsiveness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make search thumbnails feel fast and legible — recover request pace quickly after a rate-limit hiccup, show which tiles are still loading, and only fetch previews the user can actually see.

**Architecture:** Three independent changes to the existing thumbnail pipeline in `resolvestock/ui/grid.py`. (1) `ThumbnailFetcher` gets a faster, still-stable pace recovery so one early 429 no longer slows an entire search. (2) `ResultsGrid` tracks a per-tile preview state (pending / loaded / failed), paints a distinct icon for each, and emits a `preview_progress` signal that `MainWindow` renders in the status bar. (3) `ResultsGrid` stops enqueueing every preview up front and instead requests only the tiles intersecting the viewport, adding more as the user scrolls.

**Tech Stack:** Python 3.11, PySide6 (Qt Widgets), httpx, pytest.

## Global Constraints

- Python >= 3.11; dependencies limited to `PySide6>=6.11` and `httpx>=0.27` (`pyproject.toml`). Do not add new runtime dependencies.
- All Qt tests run headless: `QT_QPA_PLATFORM=offscreen` is set at the top of `tests/test_ui.py`. Never introduce a test that requires a real display.
- Run the suite with `.venv/bin/python -m pytest` from the repo root. Full suite must stay green (28 tests passing at plan time).
- Tests must not perform real network I/O. Use `httpx.MockTransport` for HTTP-level tests and the existing `RecordingFetcher` / `ManualPool` fakes for loader-level tests.
- After changing code, run `graphify update .` to refresh the knowledge graph (per `CLAUDE.md`).
- Do not change the `USER_AGENT` in `resolvestock/sources/base.py`. Wikimedia serves `429 "does not comply with our robot policy"` without contact details in it; that string is load-bearing.
- Existing public names that must keep working: `ThumbnailFetcher.fetch`, `ThumbnailLoader.load`, `ThumbnailLoader.begin_generation`, `ThumbnailLoader.stop`, `ThumbnailLoader.is_current`, `ThumbnailLoader.retire`, `ResultsGrid.set_results`, `ResultsGrid.results`, `pixmap_from_bytes`.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `resolvestock/ui/grid.py` | Thumbnail fetching, loader, results grid | Modify — all three features land here |
| `resolvestock/ui/main_window.py` | Search/download window, status bar | Modify — render progress in the status label |
| `tests/test_ui.py` | Grid, loader, fetcher, window tests | Modify — new tests for all three features |

No new files. `grid.py` is ~265 lines and cohesive (fetch → load → display); splitting it is out of scope for this plan.

### Existing test helpers you will reuse

These already exist in `tests/test_ui.py` — do not redefine them:

- `FakeClock` — `.sleep(seconds)` records into `.slept` and advances `.now`; `.monotonic()` returns `.now`.
- `ManualPool` — `.start(job)` appends to `.jobs`; `.run_all()` runs and clears them; `.setMaxThreadCount(n)` is a no-op.
- `RecordingFetcher` — `.fetch(url)` records into `.urls` and returns `.payload` (default `b"bytes"`).
- `build_fetcher(handler, clock, **kwargs)` — wraps `httpx.MockTransport(handler)` in a `ThumbnailFetcher` with the fake clock.
- `make_result(source_id="1")` — a `SearchResult` with `preview_url=""`.
- `FakeRegistry`, `FakeLibrary` — for `MainWindow` tests.
- `app` fixture — module-scoped `QApplication`.

---

## Task 1: Recover request pace faster after a rate-limit hiccup

**Problem being fixed:** `_throttle` doubles the host interval on a 429, but `_relax` only multiplies by `0.9` per success. From a 2.0s interval it takes ~13 successful fetches to return to 0.5s, and from the 8.0s cap it takes ~27. One early 429 therefore slows the entire remainder of a search. The `0.9` factor was tuned when the User-Agent was non-compliant and the host's burst budget was 8 requests; with the compliant User-Agent the measured budget is 31, so a gentler-than-necessary recovery is now costing latency for no benefit.

**Files:**
- Modify: `resolvestock/ui/grid.py:18` (constants), `resolvestock/ui/grid.py:95-99` (`_relax`)
- Test: `tests/test_ui.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: module constants `MIN_HOST_INTERVAL: float = 0.2` and `RELAX_FACTOR: float = 0.7` in `resolvestock/ui/grid.py`. `ThumbnailFetcher.__init__` keeps its existing signature `(client=None, max_attempts=MAX_ATTEMPTS, min_interval=MIN_HOST_INTERVAL, max_backoff=MAX_BACKOFF, sleep=time.sleep, clock=time.monotonic)`. No new parameters.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ui.py`, directly after `test_thumbnail_fetcher_backs_the_whole_host_off_after_a_429`:

```python
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
    assert interval == pytest.approx(0.2, abs=0.01)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_ui.py::test_thumbnail_fetcher_recovers_its_pace_after_the_host_stops_pushing_back -v`

Expected: FAIL. With the current `0.9` factor the interval after 5 successes is `2.0 * 0.9**5 ≈ 1.18`, so the assertion reports roughly `1.18 != 0.2 ± 0.01`.

- [ ] **Step 3: Change the constants**

In `resolvestock/ui/grid.py`, replace the constant block (currently lines 16-20):

```python
ACCEPT = "image/avif,image/webp,image/png,image/jpeg,image/svg+xml,*/*"
THUMBNAIL_THREADS = 3
MIN_HOST_INTERVAL = 0.2
RELAX_FACTOR = 0.7
MAX_ATTEMPTS = 6
MAX_BACKOFF = 8.0
```

- [ ] **Step 4: Use the new factor in `_relax`**

In `resolvestock/ui/grid.py`, replace the whole `_relax` method:

```python
    def _relax(self, host: str) -> None:
        with self._lock:
            state = self._state(host)
            # Ease off geometrically. Halving oscillated straight back into the
            # limit back when a contactless User-Agent bought only an 8-request
            # burst; with contact details the budget is ~31, so recovery this
            # brisk is safe and keeps one early 429 from slowing a whole search.
            state["interval"] = max(self.min_interval, state["interval"] * RELAX_FACTOR)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_ui.py::test_thumbnail_fetcher_recovers_its_pace_after_the_host_stops_pushing_back -v`

Expected: PASS. After the 429 the interval is 2.0; five successes give `2.0 * 0.7**5 ≈ 0.336`, then the sixth clamps at `0.2`.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: `29 passed`. `test_thumbnail_fetcher_paces_requests_to_the_same_host` and `test_thumbnail_fetcher_paces_hosts_independently` pass `min_interval` explicitly, so the new default does not disturb them.

- [ ] **Step 7: Verify against the live CDN**

Write this to your scratchpad as `verify_live.py` (it is a measurement tool, not a committed test — it performs real network I/O):

```python
import os, sys, time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from resolvestock.cache import ResponseCache
from resolvestock.config import Config
from resolvestock.sources.base import CachedHttp, SearchQuery
from resolvestock.sources.registry import build_registry
from resolvestock.ui.grid import ResultsGrid

term = sys.argv[1] if len(sys.argv) > 1 else "piano"
app = QApplication.instance() or QApplication([])
http = CachedHttp(ResponseCache(Path(os.environ["SCRATCH"]) / "verify_cache.sqlite"))
outcome = build_registry(http, Config(Path("/nonexistent"))).search(
    SearchQuery(term, per_page=40)
)
print(f"query={term!r} results={len(outcome.results)} errors={list(outcome.errors)}")

grid = ResultsGrid()
grid.resize(1100, 5000)   # tall viewport so every tile counts as visible
grid.show()
app.processEvents()
grid.set_results(outcome.results)
start = time.monotonic()
while grid.loader._active_jobs and time.monotonic() - start < 180:
    app.processEvents()
    time.sleep(0.02)
app.processEvents()
grid.loader.stop()
rendered = sum(
    1
    for i in range(grid.count())
    if "Thumbnail unavailable" not in grid.item(i).toolTip()
)
print(f"elapsed: {time.monotonic() - start:.1f}s")
print(f"TILES WITH A REAL THUMBNAIL: {rendered}/{grid.count()}")
```

Run it twice, on different terms, waiting ~60s between runs so the host's budget refills:

```bash
export SCRATCH=<your scratchpad dir>
.venv/bin/python -u "$SCRATCH/verify_live.py" piano
.venv/bin/python -u "$SCRATCH/verify_live.py" "vintage bicycle"
```

Expected: every run reports all tiles rendered (`34/34`, `17/17`, …) with `errors=[]`. Baseline before this task was `34/34` in ~11s; this task should be at or below that.

**If any run drops tiles**, the pace is now too aggressive: raise `RELAX_FACTOR` toward `0.8` or `MIN_HOST_INTERVAL` back toward `0.35`, re-run both terms, and record the values that hold. Do not proceed to Task 2 with a configuration that drops tiles.

- [ ] **Step 8: Commit**

```bash
git add resolvestock/ui/grid.py tests/test_ui.py
git commit -m "perf: recover thumbnail request pace faster after a 429"
```

---

## Task 2: Show pending, loaded, and failed tiles distinctly

**Problem being fixed:** A tile mid-fetch and a tile that permanently failed look identical — both keep the generic `SP_FileIcon` placeholder, and the only difference is text buried in a tooltip. Nothing tells the user that work is still in progress.

**Files:**
- Modify: `resolvestock/ui/grid.py` (`ResultsGrid`: new roles, signal, state tracking)
- Modify: `resolvestock/ui/main_window.py:73-79` (connect the signal), `resolvestock/ui/main_window.py:118-130` (`run_search`)
- Test: `tests/test_ui.py`

**Interfaces:**
- Consumes: constants from Task 1.
- Produces:
  - `PREVIEW_URL_ROLE = Qt.UserRole + 1` and `PREVIEW_STATE_ROLE = Qt.UserRole + 2` — module-level ints in `resolvestock/ui/grid.py`.
  - Per-item state string stored at `PREVIEW_STATE_ROLE`, one of `"pending"`, `"loaded"`, `"failed"`.
  - `ResultsGrid.preview_progress = Signal(int, int)` — emits `(resolved_tiles, total_tiles)` whenever a tile resolves, and once at the end of `set_results`.
  - `ResultsGrid.preview_counts() -> tuple[int, int]` — returns `(resolved, total)`.
  - `MainWindow._show_preview_progress(resolved: int, total: int) -> None` and attribute `MainWindow._search_message: str`.

- [ ] **Step 1: Write the failing test for per-tile state**

Add to `tests/test_ui.py`, after `test_grid_marks_results_without_a_preview_as_unavailable`:

```python
def test_grid_tracks_each_tile_from_pending_to_loaded(app):
    pool, fetcher = ManualPool(), RecordingFetcher(payload=PNG_BYTES)
    grid = ResultsGrid(loader=ThumbnailLoader(fetcher=fetcher, pool=pool))
    asset = SearchResult(
        **{**make_result().__dict__, "preview_url": "https://upload.example.org/a.jpg"}
    )
    grid.set_results([asset])
    assert grid.item(0).data(PREVIEW_STATE_ROLE) == "pending"
    assert grid.preview_counts() == (0, 1)

    pool.run_all()
    app.processEvents()
    assert grid.item(0).data(PREVIEW_STATE_ROLE) == "loaded"
    assert grid.preview_counts() == (1, 1)


def test_grid_counts_a_result_with_no_preview_as_already_resolved(app):
    grid = ResultsGrid(
        loader=ThumbnailLoader(fetcher=RecordingFetcher(), pool=ManualPool())
    )
    grid.set_results([make_result()])
    assert grid.item(0).data(PREVIEW_STATE_ROLE) == "failed"
    assert grid.preview_counts() == (1, 1)
```

`PNG_BYTES` is a 1x1 PNG that `pixmap_from_bytes` can actually decode — a `RecordingFetcher` returning `b"bytes"` would resolve to `"failed"`, not `"loaded"`. Add this near the top of `tests/test_ui.py`, just below the imports:

```python
import base64

# Smallest decodable PNG, so a fake fetch produces a real QPixmap.
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
```

Extend the `resolvestock.ui.grid` import in `tests/test_ui.py` to include the new names:

```python
from resolvestock.ui.grid import (
    PREVIEW_STATE_ROLE,
    ResultsGrid,
    ThumbnailFetcher,
    ThumbnailLoader,
    pixmap_from_bytes,
)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_ui.py -v -k "pending_to_loaded or already_resolved"`

Expected: FAIL at collection with `ImportError: cannot import name 'PREVIEW_STATE_ROLE' from 'resolvestock.ui.grid'`.

- [ ] **Step 3: Add the roles and icon constants**

In `resolvestock/ui/grid.py`, add below the existing constants (after `MAX_BACKOFF = 8.0`):

```python
PREVIEW_URL_ROLE = Qt.UserRole + 1
PREVIEW_STATE_ROLE = Qt.UserRole + 2
```

- [ ] **Step 4: Add the signal and state bookkeeping to `ResultsGrid`**

In `resolvestock/ui/grid.py`, add the signal beside the existing one on `ResultsGrid`:

```python
class ResultsGrid(QListWidget):
    download_requested = Signal(object)
    preview_progress = Signal(int, int)
```

In `ResultsGrid.__init__`, replace the line `self._results, self._items_by_url = {}, {}` with:

```python
        self._results, self._items_by_url = {}, {}
        self._resolved_urls, self._resolved_tiles, self._total_tiles = set(), 0, 0
```

Add these three methods to `ResultsGrid`, immediately after `results()`:

```python
    def preview_counts(self) -> tuple[int, int]:
        """Tiles whose preview has settled, and tiles in the grid."""
        return self._resolved_tiles, self._total_tiles

    def _set_state(self, entry, state: str, icon) -> None:
        entry.setData(PREVIEW_STATE_ROLE, state)
        entry.setIcon(icon)

    def _count_resolved(self, tiles: int) -> None:
        self._resolved_tiles += tiles
        self.preview_progress.emit(self._resolved_tiles, self._total_tiles)
```

- [ ] **Step 5: Rewrite `set_results` to seed the states**

In `resolvestock/ui/grid.py`, replace the whole `set_results` method:

```python
    def set_results(self, results: list[SearchResult]) -> None:
        self.clear()
        self._results.clear()
        self._items_by_url.clear()
        self._resolved_urls.clear()
        self._resolved_tiles, self._total_tiles = 0, len(results)
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
                self._count_resolved(1)
                continue
            entries = self._items_by_url.setdefault(result.preview_url, [])
            entries.append(entry)
            if len(entries) == 1:
                self.loader.load(result.preview_url)
        self.preview_progress.emit(self._resolved_tiles, self._total_tiles)
```

- [ ] **Step 6: Make the resolution handlers record state**

In `resolvestock/ui/grid.py`, replace `_apply_thumbnail`, `_mark_thumbnail_failed`, and `_mark_entry_failed`:

```python
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
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_ui.py -v -k "pending_to_loaded or already_resolved"`

Expected: PASS, both tests.

- [ ] **Step 8: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: `31 passed`. Note `test_grid_renders_svg_previews_and_marks_bad_previews` still passes — it asserts on the tooltip, which `_mark_entry_failed` still appends to.

- [ ] **Step 9: Write the failing test for the status bar**

Add to `tests/test_ui.py`, after `test_main_window_wires_search_download_and_credits`:

```python
def test_window_status_reports_preview_progress(app, tmp_path):
    window = MainWindow(
        FakeRegistry(),
        FakeLibrary(tmp_path / "library"),
        Config.load(tmp_path / "config.json"),
    )
    window._search_message = "1 result(s)"
    window._show_preview_progress(3, 10)
    assert window.status_label.text() == "1 result(s) — 3/10 previews loaded"

    window._show_preview_progress(10, 10)
    assert window.status_label.text() == "1 result(s)"
```

- [ ] **Step 10: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_ui.py::test_window_status_reports_preview_progress -v`

Expected: FAIL with `AttributeError: 'MainWindow' object has no attribute '_show_preview_progress'`.

- [ ] **Step 11: Wire the signal into `MainWindow`**

In `resolvestock/ui/main_window.py`, in `__init__` immediately after the existing line `self.grid.download_requested.connect(self.download)`, add:

```python
        self._search_message = "ready"
        self.grid.preview_progress.connect(self._show_preview_progress)
```

Add this method to `MainWindow`, directly after `run_search`:

```python
    def _show_preview_progress(self, resolved: int, total: int) -> None:
        if total and resolved < total:
            self.status_label.setText(
                f"{self._search_message} — {resolved}/{total} previews loaded"
            )
        else:
            self.status_label.setText(self._search_message)
```

In `resolvestock/ui/main_window.py`, replace the last two lines of `run_search` (currently the `if outcome.errors:` block's trailing `self.status_label.setText(message)`) so the message is retained. The full tail of `run_search` becomes:

```python
        message = f"{len(outcome.results)} result(s)"
        if outcome.errors:
            message += " — some sources failed — " + "; ".join(
                f"{name}: {error}" for name, error in outcome.errors.items()
            )
        self._search_message = message
        resolved, total = self.grid.preview_counts()
        self._show_preview_progress(resolved, total)
```

Note the ordering inside `run_search`: `self.grid.set_results(outcome.results)` runs before this block and emits `preview_progress` while `self._search_message` still holds the *previous* search's text. Re-reading the counts here and calling `_show_preview_progress` explicitly corrects the label.

- [ ] **Step 12: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_ui.py::test_window_status_reports_preview_progress -v`

Expected: PASS.

- [ ] **Step 13: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: `32 passed`.

- [ ] **Step 14: Commit**

```bash
git add resolvestock/ui/grid.py resolvestock/ui/main_window.py tests/test_ui.py
git commit -m "feat: distinguish pending and failed previews and report progress"
```

---

## Task 3: Fetch only the previews the user can see

**Problem being fixed:** `set_results` enqueues every result's preview immediately. A 40-result search fires 40 requests at one host, all of them serialized behind that host's pace gate, so tiles far down the grid hold the queue even though nobody is looking at them. Requesting only what is on screen cuts total requests and puts the visible tiles first.

**Files:**
- Modify: `resolvestock/ui/grid.py` (`ResultsGrid`: viewport-driven requests)
- Test: `tests/test_ui.py`

**Interfaces:**
- Consumes: `PREVIEW_URL_ROLE`, `PREVIEW_STATE_ROLE`, `preview_counts()`, `_count_resolved()` from Task 2.
- Produces:
  - Module constants `PRELOAD_MARGIN = 200` (pixels of look-ahead above and below the viewport) and `INITIAL_BATCH = 24` (tiles requested when the widget has no usable geometry yet).
  - `ResultsGrid._requested_urls: set[str]` — URLs already handed to the loader.
  - `ResultsGrid.request_visible_previews() -> None` — enqueues unrequested previews intersecting the viewport. Idempotent; safe to call on every scroll event.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ui.py`, after `test_grid_counts_a_result_with_no_preview_as_already_resolved`:

```python
def grid_with_results(count, pool, fetcher):
    grid = ResultsGrid(loader=ThumbnailLoader(fetcher=fetcher, pool=pool))
    results = [
        SearchResult(
            **{
                **make_result(source_id=str(index)).__dict__,
                "preview_url": f"https://upload.example.org/{index}.jpg",
            }
        )
        for index in range(count)
    ]
    grid.set_results(results)
    return grid


def test_grid_requests_a_first_batch_when_it_has_no_geometry_yet(app):
    # The widget was never shown, so visualItemRect cannot say what is visible.
    pool, fetcher = ManualPool(), RecordingFetcher(payload=PNG_BYTES)
    grid_with_results(40, pool, fetcher)
    pool.run_all()
    assert len(fetcher.urls) == 24


def test_grid_requests_only_previews_near_the_viewport(app):
    pool, fetcher = ManualPool(), RecordingFetcher(payload=PNG_BYTES)
    grid = grid_with_results(40, pool, fetcher)
    grid.resize(400, 300)
    grid.show()
    app.processEvents()
    grid.request_visible_previews()
    pool.run_all()
    assert 0 < len(fetcher.urls) < 40


def test_grid_requests_more_previews_as_the_user_scrolls(app):
    pool, fetcher = ManualPool(), RecordingFetcher(payload=PNG_BYTES)
    grid = grid_with_results(40, pool, fetcher)
    grid.resize(400, 300)
    grid.show()
    app.processEvents()
    grid.request_visible_previews()
    pool.run_all()
    first_screen = list(fetcher.urls)

    scrollbar = grid.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())
    app.processEvents()
    pool.run_all()
    assert len(fetcher.urls) > len(first_screen)


def test_grid_does_not_request_the_same_preview_twice(app):
    pool, fetcher = ManualPool(), RecordingFetcher(payload=PNG_BYTES)
    grid = grid_with_results(40, pool, fetcher)
    grid.resize(400, 300)
    grid.show()
    app.processEvents()
    for _ in range(5):
        grid.request_visible_previews()
    pool.run_all()
    assert len(fetcher.urls) == len(set(fetcher.urls))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_ui.py -v -k "first_batch or near_the_viewport or as_the_user_scrolls or same_preview_twice"`

Expected: FAIL. `test_grid_requests_a_first_batch_when_it_has_no_geometry_yet` fails with `assert 40 == 24` (everything is still requested up front); the other three fail with `AttributeError: 'ResultsGrid' object has no attribute 'request_visible_previews'`.

- [ ] **Step 3: Add the constants**

In `resolvestock/ui/grid.py`, add below `PREVIEW_STATE_ROLE`:

```python
PRELOAD_MARGIN = 200
INITIAL_BATCH = 24
```

- [ ] **Step 4: Track requested URLs and connect the scroll signal**

In `resolvestock/ui/grid.py`, in `ResultsGrid.__init__`, replace the bookkeeping line added in Task 2:

```python
        self._resolved_urls, self._resolved_tiles, self._total_tiles = set(), 0, 0
        self._requested_urls = set()
```

At the end of `ResultsGrid.__init__`, after `self.itemDoubleClicked.connect(self._emit_download)`, add:

```python
        self.verticalScrollBar().valueChanged.connect(self.request_visible_previews)
```

- [ ] **Step 5: Stop requesting everything in `set_results`**

In `resolvestock/ui/grid.py`, inside `set_results`, replace these four lines:

```python
            entries = self._items_by_url.setdefault(result.preview_url, [])
            entries.append(entry)
            if len(entries) == 1:
                self.loader.load(result.preview_url)
```

with:

```python
            self._items_by_url.setdefault(result.preview_url, []).append(entry)
```

Then replace the final line of `set_results`:

```python
        self.preview_progress.emit(self._resolved_tiles, self._total_tiles)
```

with:

```python
        self._requested_urls.clear()
        self.preview_progress.emit(self._resolved_tiles, self._total_tiles)
        self.request_visible_previews()
```

- [ ] **Step 6: Implement the viewport-driven request**

In `resolvestock/ui/grid.py`, add these methods to `ResultsGrid`, immediately after `preview_counts()`:

```python
    def request_visible_previews(self) -> None:
        """Fetch previews for tiles on screen, and for a margin either side.

        Requesting all forty results of a search at once queues them behind one
        host's pace gate, so tiles nobody is looking at delay the ones in view.
        """
        for url in self._visible_preview_urls():
            if url in self._requested_urls:
                continue
            self._requested_urls.add(url)
            self.loader.load(url)

    def _visible_preview_urls(self) -> list[str]:
        visible = self.viewport().rect().adjusted(0, -PRELOAD_MARGIN, 0, PRELOAD_MARGIN)
        if self.viewport().height() <= 0:
            # Never shown, or laid out yet — fall back to a first screenful.
            return self._preview_urls()[:INITIAL_BATCH]
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
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_ui.py -v -k "first_batch or near_the_viewport or as_the_user_scrolls or same_preview_twice"`

Expected: PASS, all four.

If `test_grid_requests_only_previews_near_the_viewport` fails with `40 == 40`, the offscreen viewport is taller than expected — shrink the grid to `grid.resize(400, 200)` in that test and re-run. Do not widen `PRELOAD_MARGIN` to make a test pass.

- [ ] **Step 8: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: `36 passed`.

`test_grid_restarts_the_generation_for_each_search` and `test_grid_renders_svg_previews_and_marks_bad_previews` both rely on `set_results` triggering a load on an unshown widget; the `INITIAL_BATCH` fallback in `_visible_preview_urls` keeps that working. If either fails, confirm the fallback branch is reached — `self.viewport().height() <= 0` must be true for a widget that was never shown.

- [ ] **Step 9: Verify the request reduction against the live CDN**

Reuse the `verify_live.py` from Task 1 Step 7, but drop the `grid.resize(1100, 5000)` line and use a realistic window instead:

```python
grid.resize(1100, 600)
```

Run:

```bash
export SCRATCH=<your scratchpad dir>
.venv/bin/python -u "$SCRATCH/verify_live.py" piano
```

Expected: the visible tiles render, and the run finishes markedly faster than the full-grid baseline because only the on-screen previews were fetched. Print `len(grid._requested_urls)` at the end to confirm it is well below `grid.count()`.

- [ ] **Step 10: Refresh the knowledge graph**

Run: `graphify update .`

Expected: a rebuild line such as `[graphify watch] Rebuilt: N nodes, M edges`.

- [ ] **Step 11: Commit**

```bash
git add resolvestock/ui/grid.py tests/test_ui.py graphify-out
git commit -m "perf: fetch previews for visible tiles only"
```

---

## Verification Checklist

Run before calling the work done:

- [ ] `.venv/bin/python -m pytest -q` → `36 passed`, no stray tracebacks in the output
- [ ] Live run on two different search terms renders every visible tile with `errors=[]`
- [ ] Status bar shows `N/M previews loaded` while a search is loading and drops the suffix when it finishes
- [ ] Pending tiles show the reload icon, failed tiles show the warning icon, loaded tiles show the image
- [ ] Scrolling a 40-result search to the bottom fills in the newly visible tiles
- [ ] `graphify update .` has been run

## Known Risks

- **Offscreen geometry.** `visualItemRect` depends on Qt having laid the view out. Tests must `show()` and `processEvents()` before asserting on visibility. The `INITIAL_BATCH` fallback covers the never-shown case.
- **Pace re-tuning is empirical.** Task 1's constants are a starting point measured against Wikimedia on one network. If live runs drop tiles, the fix is to back the constants off, not to raise `MAX_ATTEMPTS`.
- **Openverse thumbnails come from a different host** (`api.openverse.org/v1/images/<id>/thumb/`) than Wikimedia's (`upload.wikimedia.org`). The pace gate is per host, so the two do not contend — but it also means Openverse's own rate limits are untested here. If Openverse tiles start failing, add its host to the live verification and check the 429 body.
