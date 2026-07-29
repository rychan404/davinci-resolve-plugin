# Graph Report - davinci-resolve-plugin  (2026-07-29)

## Corpus Check
- 32 files · ~21,447 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 311 nodes · 802 edges · 24 communities (17 shown, 7 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 102 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `10e41342`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- CachedHttp
- LibraryTray
- FakeClock
- test_ui.py
- LibraryItem
- File Structure
- Stock Asset Sourcing App — Specification
- ResultsGrid
- ThumbnailFetcher
- resolvestock
- CLAUDE.md
- resolvestock/__init__.py
- sources/__init__.py
- ui/__init__.py
- resolvestock
- Thumbnail Loading Responsiveness Implementation Plan
- MainWindow
- SearchResult
- test_core.py
- registry.py
- SearchQuery
- WikimediaSource
- .__init__
- .__init__

## God Nodes (most connected - your core abstractions)
1. `SearchResult` - 53 edges
2. `ResultsGrid` - 35 edges
3. `SearchQuery` - 32 edges
4. `MainWindow` - 28 edges
5. `ManualPool` - 28 edges
6. `CachedHttp` - 25 edges
7. `RecordingFetcher` - 25 edges
8. `ThumbnailLoader` - 24 edges
9. `ResponseCache` - 23 edges
10. `LibraryItem` - 23 edges

## Surprising Connections (you probably didn't know these)
- `_Source` --uses--> `ResponseCache`  [INFERRED]
  tests/test_core.py → resolvestock/cache.py
- `FakeClock` --uses--> `Config`  [INFERRED]
  tests/test_ui.py → resolvestock/config.py
- `ManualPool` --uses--> `Config`  [INFERRED]
  tests/test_ui.py → resolvestock/config.py
- `RecordingFetcher` --uses--> `Config`  [INFERRED]
  tests/test_ui.py → resolvestock/config.py
- `_Source` --uses--> `Library`  [INFERRED]
  tests/test_core.py → resolvestock/library.py

## Import Cycles
- None detected.

## Communities (24 total, 7 thin omitted)

### Community 0 - "CachedHttp"
Cohesion: 0.15
Nodes (12): ResponseCache, CachedHttp, Client, OpenverseSource, Source, Openverse image-search adapter., source(), test_openverse_keeps_page_size_within_the_anonymous_limit() (+4 more)

### Community 1 - "LibraryTray"
Cohesion: 0.09
Nodes (17): QMimeData, QPixmap, build_credits(), Path, Attribution credits for downloaded assets., write_credits(), get_license(), Remote search grid with asynchronous thumbnails. (+9 more)

### Community 2 - "FakeClock"
Cohesion: 0.26
Nodes (12): build_fetcher(), FakeClock, Deterministic stand-in for time.sleep/time.monotonic., test_thumbnail_fetcher_backs_the_whole_host_off_after_a_429(), test_thumbnail_fetcher_does_not_widen_host_pacing_after_a_424(), test_thumbnail_fetcher_paces_hosts_independently(), test_thumbnail_fetcher_paces_requests_to_the_same_host(), test_thumbnail_fetcher_recovers_its_pace_after_the_host_stops_pushing_back() (+4 more)

### Community 3 - "test_ui.py"
Cohesion: 0.15
Nodes (28): fixture, pixmap_from_bytes(), Invalidate jobs queued for the previous search., Abandon outstanding previews. QThreadPool waits for its whole backlog on…, Decode raster previews and render SVG previews Qt cannot load directly., ThumbnailLoader, app(), grid_with_results() (+20 more)

### Community 4 - "LibraryItem"
Cohesion: 0.24
Nodes (9): Library, Client, Path, Deliberate single-asset downloads with durable provenance sidecars., slugify(), LibraryItem, result(), test_credits_omits_cc0_and_includes_attribution_required_assets() (+1 more)

### Community 5 - "File Structure"
Cohesion: 0.10
Nodes (20): Deferred — not in this plan, File Structure, Global Constraints, Repository rename, Stock Asset Sourcing App v1 — Implementation Plan, Task 10: Credits export, Task 11: Library tray — the drag source into Resolve, Task 12: Results grid with async thumbnails (+12 more)

### Community 6 - "Stock Asset Sourcing App — Specification"
Cohesion: 0.13
Nodes (14): 10. Feature list — v1, 11. Open questions, 12. Success criteria, 13. Repository note, 1. Problem, 2. Target user, 3. What this is not, 4. Verified platform constraints (+6 more)

### Community 7 - "ResultsGrid"
Cohesion: 0.21
Nodes (4): QListWidget, Tiles whose preview has settled, and tiles actually requested., Fetch previews for tiles on screen, and for a margin either side. Requesting…, ResultsGrid

### Community 8 - "ThumbnailFetcher"
Cohesion: 0.13
Nodes (6): QObject, QRunnable, Fetch previews at a pace the image CDNs tolerate. A search asks for dozens of…, ThumbnailFetcher, _ThumbnailJob, _ThumbnailSignals

### Community 9 - "resolvestock"
Cohesion: 0.25
Nodes (7): DaVinci Resolve integration, Development, Install, resolvestock, Sources, Why, Workflow

### Community 15 - "Thumbnail Loading Responsiveness Implementation Plan"
Cohesion: 0.20
Nodes (9): Existing test helpers you will reuse, File Structure, Global Constraints, Known Risks, Task 1: Recover request pace faster after a rate-limit hiccup, Task 2: Show pending, loaded, and failed tiles distinctly, Task 3: Fetch only the previews the user can see, Thumbnail Loading Responsiveness Implementation Plan (+1 more)

### Community 16 - "MainWindow"
Cohesion: 0.14
Nodes (12): QMainWindow, Config, Path, MainWindow, Path, FakeLibrary, FakeRegistry, test_closing_the_window_stops_thumbnail_work() (+4 more)

### Community 17 - "SearchResult"
Cohesion: 0.21
Nodes (9): ABC, Core data types shared by every layer., SearchResult, Shared source contracts and cached HTTP access., Source, PixabaySource, Source, Pixabay adapter; searches only, never mass-downloads. (+1 more)

### Community 18 - "test_core.py"
Cohesion: 0.24
Nodes (9): make_key(), SQLite response cache. The default 24-hour TTL satisfies Pixabay terms., filter_commercial_safe(), is_commercial_safe(), License, normalize_license_id(), License identity and conservative commercial-safety rules., test_cache_hides_secrets_and_round_trips() (+1 more)

### Community 19 - "registry.py"
Cohesion: 0.26
Nodes (9): format_results(), main(), Terminal source-layer harness., Persistent user settings., build_registry(), Fault-tolerant fan-out across configured sources., SearchOutcome, main() (+1 more)

### Community 20 - "SearchQuery"
Cohesion: 0.57
Nodes (4): SearchQuery, SourceRegistry, _Source, test_registry_interleaves_deduplicates_and_keeps_source_failures()

### Community 21 - "WikimediaSource"
Cohesion: 0.40
Nodes (3): Source, strip_html(), WikimediaSource

## Knowledge Gaps
- **46 isolated node(s):** `resolvestock`, `graphify`, `Why`, `Install`, `Sources` (+41 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SearchResult` connect `SearchResult` to `CachedHttp`, `LibraryTray`, `FakeClock`, `test_ui.py`, `LibraryItem`, `ResultsGrid`, `ThumbnailFetcher`, `MainWindow`, `test_core.py`, `registry.py`, `SearchQuery`, `WikimediaSource`?**
  _High betweenness centrality (0.188) - this node is a cross-community bridge._
- **Why does `ResultsGrid` connect `ResultsGrid` to `LibraryTray`, `FakeClock`, `test_ui.py`, `ThumbnailFetcher`, `MainWindow`, `SearchResult`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Why does `MainWindow` connect `MainWindow` to `LibraryTray`, `FakeClock`, `test_ui.py`, `ResultsGrid`, `registry.py`, `SearchQuery`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `SearchResult` (e.g. with `Library` and `License`) actually correct?**
  _`SearchResult` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `ResultsGrid` (e.g. with `SearchResult` and `_DownloadJob`) actually correct?**
  _`ResultsGrid` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `SearchQuery` (e.g. with `ResponseCache` and `SearchResult`) actually correct?**
  _`SearchQuery` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `MainWindow` (e.g. with `SearchQuery` and `ResultsGrid`) actually correct?**
  _`MainWindow` has 8 INFERRED edges - model-reasoned connections that need verification._