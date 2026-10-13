# Provider Tabs Design

## Goal

Let the user search one stock provider at a time from a tab row, instead of
always fanning out to every configured source. An `All` tab keeps today's
behavior.

## Agreed behavior

- Tabs: `All | Openverse | Wikimedia | Pixabay`. `All` is selected on launch.
- Only the selected tab's provider is queried; other providers receive no
  request. `All` queries every configured source exactly as today.
- Tabs come from the registry's configured sources, so `Pixabay` appears only
  when a Pixabay key is configured.
- Switching tabs re-runs the current search immediately against the new tab.
  If the search box is empty, switching tabs does nothing.
- Existing filters (transparent, vectors, photos, commercial-safe) apply
  unchanged within every tab.

## Approach

Add the provider choice to `SearchQuery`, the object that already carries
every search filter, and have `SourceRegistry` skip non-matching sources.
Adapters do not change.

Rejected: a separate `registry.search(query, only=...)` argument (a second
filter channel every caller must thread through), and one registry per tab
(three objects to express one condition).

## Components

### `resolvestock/sources/base.py`

`SearchQuery` gains a final field:

```python
source: str | None = None  # None = all configured sources
```

It must be appended after `photos_only`: `cli.py` and
`test_search_query_keeps_commercial_safety_as_its_sixth_field` rely on the
existing positional order.

### `resolvestock/sources/registry.py`

`SourceRegistry.search` iterates only sources where
`query.source in (None, source.name)`. Interleaving, deduplication, and the
commercial-safe filter are unchanged.

If `query.source` is set but no registered source has that name (e.g.
`pixabay` without a key), the outcome has no results and
`errors[query.source] == "not configured"`. The UI and CLI already render
`outcome.errors`, so the user sees why the search came back empty.

### `resolvestock/ui/main_window.py`

- A `QTabBar` (`self.source_tabs`) sits between the filter row and the
  "Results — double click to download" label.
- Tab 0 is `All` with tab data `None`; then one tab per
  `registry.sources` entry, labeled `source.name.capitalize()`, with tab data
  `source.name`.
- `build_query` sets `source=self.source_tabs.tabData(self.source_tabs.currentIndex())`.
- `currentChanged` connects to a handler that calls `run_search()` only when
  `self.search_input.text().strip()` is non-empty. `run_search` already
  guards empty text, but that guard writes "enter a search term" to the
  status bar, which a tab click should not do.

### `resolvestock/cli.py`

New option `--source` with `choices=["openverse", "wikimedia", "pixabay"]`,
default `None`, passed through as `SearchQuery(source=args.source)`. Choosing
an unconfigured source prints the registry's "not configured" error and exits
1 (the existing no-results exit code).

### `README.md`

Add `--source NAME` to the CLI options line.

## Data flow

Tab click → `currentChanged` → (text non-empty) `run_search()` →
`build_query()` reads the tab's source name → `registry.search(query)` calls
only the matching source → grid and status bar update as today.

Response caching is per HTTP request, so returning to a tab already searched
with the same text and filters is served from the 24-hour cache.

## Error handling

- Selected provider fails (network, 429): the existing per-source error
  reporting shows `name: error` in the status bar / CLI output.
- Selected provider not configured: `"not configured"` error as above. In the
  UI this cannot happen, since tabs come from configured sources; it guards
  the CLI.

## Testing

All tests run without network, using the existing `_Source` fake in
`tests/test_core.py` and the window fixtures in `tests/test_ui.py`.

`tests/test_core.py`:
- Registry with sources `a`, `b`: `SearchQuery("smoke", source="b")` returns
  only `b` results and never calls `a.search`.
- `SearchQuery("smoke", source="missing")` yields no results and
  `errors == {"missing": "not configured"}`.
- `build_parser().parse_args(["smoke", "--source", "wikimedia"]).source == "wikimedia"`.
- Existing positional-field test still passes unchanged.

`tests/test_ui.py`:
- Tab labels are `All` followed by the registry's source names, capitalized.
- With text in the search box, selecting a provider tab runs a search whose
  query has `source` set to that provider's name; selecting `All` runs one
  with `source=None`.
- With an empty search box, switching tabs performs no search and leaves the
  status label unchanged.

## Out of scope

- Remembering the selected tab across sessions.
- Per-tab result counts or badges.
- Showing disabled tabs for unconfigured providers.
