# Graph Report - davinci-resolve-plugin  (2026-07-28)

## Corpus Check
- 31 files · ~17,036 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 278 nodes · 707 edges · 15 communities (9 shown, 6 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 102 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `43a45d06`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SearchQuery
- ResultsGrid
- ThumbnailFetcher
- test_ui.py
- SearchResult
- File Structure
- Stock Asset Sourcing App — Specification
- .export_credits
- _ThumbnailJob
- resolvestock
- CLAUDE.md
- resolvestock/__init__.py
- sources/__init__.py
- ui/__init__.py
- resolvestock

## God Nodes (most connected - your core abstractions)
1. `SearchResult` - 51 edges
2. `SearchQuery` - 32 edges
3. `MainWindow` - 26 edges
4. `CachedHttp` - 25 edges
5. `ResultsGrid` - 25 edges
6. `ResponseCache` - 23 edges
7. `LibraryItem` - 23 edges
8. `ThumbnailLoader` - 21 edges
9. `ManualPool` - 21 edges
10. `LibraryTray` - 20 edges

## Surprising Connections (you probably didn't know these)
- `_Source` --uses--> `ResponseCache`  [INFERRED]
  tests/test_core.py → resolvestock/cache.py
- `FakeClock` --uses--> `Config`  [INFERRED]
  tests/test_ui.py → resolvestock/config.py
- `FakeClock` --uses--> `SearchResult`  [INFERRED]
  tests/test_ui.py → resolvestock/models.py
- `FakeLibrary` --uses--> `SearchResult`  [INFERRED]
  tests/test_ui.py → resolvestock/models.py
- `FakeRegistry` --uses--> `SearchResult`  [INFERRED]
  tests/test_ui.py → resolvestock/models.py

## Import Cycles
- None detected.

## Communities (15 total, 6 thin omitted)

### Community 0 - "SearchQuery"
Cohesion: 0.08
Nodes (38): ABC, make_key(), Path, SQLite response cache. The default 24-hour TTL satisfies Pixabay terms., ResponseCache, format_results(), main(), Terminal source-layer harness. (+30 more)

### Community 1 - "ResultsGrid"
Cohesion: 0.11
Nodes (11): QPixmap, pixmap_from_bytes(), QListWidget, Invalidate jobs queued for the previous search., Abandon outstanding previews. QThreadPool waits for its whole backlog on…, Decode raster previews and render SVG previews Qt cannot load directly., ResultsGrid, _DownloadJob (+3 more)

### Community 2 - "ThumbnailFetcher"
Cohesion: 0.16
Nodes (10): Fetch previews at a pace the image CDNs tolerate. A search asks for dozens of…, ThumbnailFetcher, build_fetcher(), FakeClock, Deterministic stand-in for time.sleep/time.monotonic., test_thumbnail_fetcher_backs_the_whole_host_off_after_a_429(), test_thumbnail_fetcher_paces_hosts_independently(), test_thumbnail_fetcher_paces_requests_to_the_same_host() (+2 more)

### Community 3 - "test_ui.py"
Cohesion: 0.09
Nodes (30): fixture, QMainWindow, QMimeData, Config, Path, ThumbnailLoader, MainWindow, LibraryTray (+22 more)

### Community 4 - "SearchResult"
Cohesion: 0.11
Nodes (27): build_credits(), Path, Attribution credits for downloaded assets., write_credits(), Library, Client, Path, Deliberate single-asset downloads with durable provenance sidecars. (+19 more)

### Community 5 - "File Structure"
Cohesion: 0.10
Nodes (20): Deferred — not in this plan, File Structure, Global Constraints, Repository rename, Stock Asset Sourcing App v1 — Implementation Plan, Task 10: Credits export, Task 11: Library tray — the drag source into Resolve, Task 12: Results grid with async thumbnails (+12 more)

### Community 6 - "Stock Asset Sourcing App — Specification"
Cohesion: 0.13
Nodes (14): 10. Feature list — v1, 11. Open questions, 12. Success criteria, 13. Repository note, 1. Problem, 2. Target user, 3. What this is not, 4. Verified platform constraints (+6 more)

### Community 8 - "_ThumbnailJob"
Cohesion: 0.18
Nodes (4): QObject, QRunnable, _ThumbnailJob, _ThumbnailSignals

### Community 9 - "resolvestock"
Cohesion: 0.25
Nodes (7): DaVinci Resolve integration, Development, Install, resolvestock, Sources, Why, Workflow

## Knowledge Gaps
- **39 isolated node(s):** `resolvestock`, `graphify`, `Why`, `Install`, `Sources` (+34 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SearchResult` connect `SearchResult` to `SearchQuery`, `ResultsGrid`, `ThumbnailFetcher`, `test_ui.py`, `_ThumbnailJob`?**
  _High betweenness centrality (0.196) - this node is a cross-community bridge._
- **Why does `MainWindow` connect `test_ui.py` to `SearchQuery`, `ResultsGrid`, `ThumbnailFetcher`, `SearchResult`, `.export_credits`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Why does `SearchQuery` connect `SearchQuery` to `ResultsGrid`, `test_ui.py`, `SearchResult`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `SearchResult` (e.g. with `Library` and `License`) actually correct?**
  _`SearchResult` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `SearchQuery` (e.g. with `ResponseCache` and `SearchResult`) actually correct?**
  _`SearchQuery` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `MainWindow` (e.g. with `SearchQuery` and `ResultsGrid`) actually correct?**
  _`MainWindow` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `CachedHttp` (e.g. with `ResponseCache` and `SearchResult`) actually correct?**
  _`CachedHttp` has 6 INFERRED edges - model-reasoned connections that need verification._