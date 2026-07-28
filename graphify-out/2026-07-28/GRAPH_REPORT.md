# Graph Report - davinci-resolve-plugin  (2026-07-28)

## Corpus Check
- 31 files · ~16,794 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 271 nodes · 684 edges · 14 communities (9 shown, 5 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 102 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `43a45d06`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SearchResult
- licenses.py
- test_ui.py
- MainWindow
- test_core.py
- File Structure
- Stock Asset Sourcing App — Specification
- ThumbnailFetcher
- resolvestock
- CLAUDE.md
- resolvestock/__init__.py
- sources/__init__.py
- ui/__init__.py
- resolvestock

## God Nodes (most connected - your core abstractions)
1. `SearchResult` - 51 edges
2. `SearchQuery` - 31 edges
3. `ResultsGrid` - 25 edges
4. `CachedHttp` - 24 edges
5. `MainWindow` - 24 edges
6. `LibraryItem` - 23 edges
7. `ResponseCache` - 22 edges
8. `LibraryTray` - 20 edges
9. `ThumbnailFetcher` - 19 edges
10. `ThumbnailLoader` - 19 edges

## Surprising Connections (you probably didn't know these)
- `FakeLibrary` --uses--> `Config`  [INFERRED]
  tests/test_ui.py → resolvestock/config.py
- `FakeRegistry` --uses--> `Config`  [INFERRED]
  tests/test_ui.py → resolvestock/config.py
- `_Source` --uses--> `SearchResult`  [INFERRED]
  tests/test_core.py → resolvestock/models.py
- `FakeClock` --uses--> `SearchResult`  [INFERRED]
  tests/test_ui.py → resolvestock/models.py
- `FakeLibrary` --uses--> `SearchResult`  [INFERRED]
  tests/test_ui.py → resolvestock/models.py

## Import Cycles
- None detected.

## Communities (14 total, 5 thin omitted)

### Community 0 - "SearchResult"
Cohesion: 0.12
Nodes (30): ABC, format_results(), main(), Terminal source-layer harness., normalize_license_id(), SearchResult, CachedHttp, Shared source contracts and cached HTTP access. (+22 more)

### Community 1 - "licenses.py"
Cohesion: 0.19
Nodes (13): build_credits(), Path, Attribution credits for downloaded assets., write_credits(), filter_commercial_safe(), get_license(), is_commercial_safe(), License (+5 more)

### Community 2 - "test_ui.py"
Cohesion: 0.09
Nodes (31): fixture, Config, Persistent user settings., pixmap_from_bytes(), QListWidget, QObject, Decode raster previews and render SVG previews Qt cannot load directly., ResultsGrid (+23 more)

### Community 3 - "MainWindow"
Cohesion: 0.07
Nodes (19): QMainWindow, QMimeData, QPixmap, Path, main(), _DownloadJob, _DownloadSignals, MainWindow (+11 more)

### Community 4 - "test_core.py"
Cohesion: 0.10
Nodes (19): make_key(), Path, SQLite response cache. The default 24-hour TTL satisfies Pixabay terms., ResponseCache, Library, Client, Path, Deliberate single-asset downloads with durable provenance sidecars. (+11 more)

### Community 5 - "File Structure"
Cohesion: 0.10
Nodes (20): Deferred — not in this plan, File Structure, Global Constraints, Repository rename, Stock Asset Sourcing App v1 — Implementation Plan, Task 10: Credits export, Task 11: Library tray — the drag source into Resolve, Task 12: Results grid with async thumbnails (+12 more)

### Community 6 - "Stock Asset Sourcing App — Specification"
Cohesion: 0.13
Nodes (14): 10. Feature list — v1, 11. Open questions, 12. Success criteria, 13. Repository note, 1. Problem, 2. Target user, 3. What this is not, 4. Verified platform constraints (+6 more)

### Community 8 - "ThumbnailFetcher"
Cohesion: 0.14
Nodes (5): QRunnable, Invalidate jobs queued for the previous search., Fetch previews at a pace the image CDNs tolerate. A search asks for dozens of…, ThumbnailFetcher, _ThumbnailJob

### Community 9 - "resolvestock"
Cohesion: 0.25
Nodes (7): DaVinci Resolve integration, Development, Install, resolvestock, Sources, Why, Workflow

## Knowledge Gaps
- **39 isolated node(s):** `resolvestock`, `graphify`, `Why`, `Install`, `Sources` (+34 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SearchResult` connect `SearchResult` to `licenses.py`, `test_ui.py`, `MainWindow`, `test_core.py`, `ThumbnailFetcher`?**
  _High betweenness centrality (0.196) - this node is a cross-community bridge._
- **Why does `SearchQuery` connect `SearchResult` to `licenses.py`, `MainWindow`, `test_core.py`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Why does `MainWindow` connect `MainWindow` to `SearchResult`, `licenses.py`, `test_ui.py`, `test_core.py`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `SearchResult` (e.g. with `Library` and `License`) actually correct?**
  _`SearchResult` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `SearchQuery` (e.g. with `ResponseCache` and `SearchResult`) actually correct?**
  _`SearchQuery` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `ResultsGrid` (e.g. with `SearchResult` and `_DownloadJob`) actually correct?**
  _`ResultsGrid` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `CachedHttp` (e.g. with `ResponseCache` and `SearchResult`) actually correct?**
  _`CachedHttp` has 6 INFERRED edges - model-reasoned connections that need verification._