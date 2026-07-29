# Graph Report - davinci-resolve-plugin  (2026-07-28)

## Corpus Check
- 32 files · ~21,118 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 307 nodes · 785 edges · 16 communities (11 shown, 5 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 102 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `edde691b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SearchResult
- MainWindow
- FakeClock
- test_ui.py
- test_core.py
- File Structure
- Stock Asset Sourcing App — Specification
- .set_results
- ThumbnailFetcher
- resolvestock
- CLAUDE.md
- resolvestock/__init__.py
- sources/__init__.py
- ui/__init__.py
- resolvestock
- Thumbnail Loading Responsiveness Implementation Plan

## God Nodes (most connected - your core abstractions)
1. `SearchResult` - 53 edges
2. `ResultsGrid` - 35 edges
3. `SearchQuery` - 32 edges
4. `MainWindow` - 28 edges
5. `ManualPool` - 27 edges
6. `CachedHttp` - 25 edges
7. `ThumbnailLoader` - 24 edges
8. `RecordingFetcher` - 24 edges
9. `ResponseCache` - 23 edges
10. `LibraryItem` - 23 edges

## Surprising Connections (you probably didn't know these)
- `_Source` --uses--> `ResponseCache`  [INFERRED]
  tests/test_core.py → resolvestock/cache.py
- `FakeClock` --uses--> `Config`  [INFERRED]
  tests/test_ui.py → resolvestock/config.py
- `_Source` --uses--> `SearchResult`  [INFERRED]
  tests/test_core.py → resolvestock/models.py
- `FakeClock` --uses--> `SearchResult`  [INFERRED]
  tests/test_ui.py → resolvestock/models.py
- `FakeLibrary` --uses--> `SearchResult`  [INFERRED]
  tests/test_ui.py → resolvestock/models.py

## Import Cycles
- None detected.

## Communities (16 total, 5 thin omitted)

### Community 0 - "SearchResult"
Cohesion: 0.08
Nodes (43): ABC, make_key(), Path, SQLite response cache. The default 24-hour TTL satisfies Pixabay terms., ResponseCache, format_results(), main(), Terminal source-layer harness. (+35 more)

### Community 1 - "MainWindow"
Cohesion: 0.11
Nodes (11): QMainWindow, QMimeData, _DownloadJob, _DownloadSignals, MainWindow, Path, QObject, QRunnable (+3 more)

### Community 2 - "FakeClock"
Cohesion: 0.28
Nodes (9): build_fetcher(), FakeClock, Deterministic stand-in for time.sleep/time.monotonic., test_thumbnail_fetcher_backs_the_whole_host_off_after_a_429(), test_thumbnail_fetcher_paces_hosts_independently(), test_thumbnail_fetcher_paces_requests_to_the_same_host(), test_thumbnail_fetcher_recovers_its_pace_after_the_host_stops_pushing_back(), test_thumbnail_fetcher_reports_failure_after_exhausting_retries() (+1 more)

### Community 3 - "test_ui.py"
Cohesion: 0.10
Nodes (38): fixture, Config, Path, Persistent user settings., pixmap_from_bytes(), QListWidget, Tiles whose preview has settled, and tiles in the grid., Decode raster previews and render SVG previews Qt cannot load directly. (+30 more)

### Community 4 - "test_core.py"
Cohesion: 0.12
Nodes (21): QPixmap, build_credits(), Path, Attribution credits for downloaded assets., write_credits(), Library, Client, Path (+13 more)

### Community 5 - "File Structure"
Cohesion: 0.10
Nodes (20): Deferred — not in this plan, File Structure, Global Constraints, Repository rename, Stock Asset Sourcing App v1 — Implementation Plan, Task 10: Credits export, Task 11: Library tray — the drag source into Resolve, Task 12: Results grid with async thumbnails (+12 more)

### Community 6 - "Stock Asset Sourcing App — Specification"
Cohesion: 0.13
Nodes (14): 10. Feature list — v1, 11. Open questions, 12. Success criteria, 13. Repository note, 1. Problem, 2. Target user, 3. What this is not, 4. Verified platform constraints (+6 more)

### Community 7 - ".set_results"
Cohesion: 0.17
Nodes (3): Invalidate jobs queued for the previous search., Abandon outstanding previews. QThreadPool waits for its whole backlog on…, Fetch previews for tiles on screen, and for a margin either side. Requesting…

### Community 8 - "ThumbnailFetcher"
Cohesion: 0.13
Nodes (7): QObject, QRunnable, Remote search grid with asynchronous thumbnails., Fetch previews at a pace the image CDNs tolerate. A search asks for dozens of…, ThumbnailFetcher, _ThumbnailJob, _ThumbnailSignals

### Community 9 - "resolvestock"
Cohesion: 0.25
Nodes (7): DaVinci Resolve integration, Development, Install, resolvestock, Sources, Why, Workflow

### Community 15 - "Thumbnail Loading Responsiveness Implementation Plan"
Cohesion: 0.20
Nodes (9): Existing test helpers you will reuse, File Structure, Global Constraints, Known Risks, Task 1: Recover request pace faster after a rate-limit hiccup, Task 2: Show pending, loaded, and failed tiles distinctly, Task 3: Fetch only the previews the user can see, Thumbnail Loading Responsiveness Implementation Plan (+1 more)

## Knowledge Gaps
- **46 isolated node(s):** `resolvestock`, `graphify`, `Why`, `Install`, `Sources` (+41 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SearchResult` connect `SearchResult` to `FakeClock`, `test_ui.py`, `test_core.py`, `.set_results`, `ThumbnailFetcher`?**
  _High betweenness centrality (0.188) - this node is a cross-community bridge._
- **Why does `ResultsGrid` connect `test_ui.py` to `SearchResult`, `MainWindow`, `FakeClock`, `test_core.py`, `.set_results`, `ThumbnailFetcher`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Why does `MainWindow` connect `MainWindow` to `SearchResult`, `FakeClock`, `test_ui.py`, `test_core.py`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `SearchResult` (e.g. with `Library` and `License`) actually correct?**
  _`SearchResult` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `ResultsGrid` (e.g. with `SearchResult` and `_DownloadJob`) actually correct?**
  _`ResultsGrid` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `SearchQuery` (e.g. with `ResponseCache` and `SearchResult`) actually correct?**
  _`SearchQuery` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `MainWindow` (e.g. with `SearchQuery` and `ResultsGrid`) actually correct?**
  _`MainWindow` has 8 INFERRED edges - model-reasoned connections that need verification._