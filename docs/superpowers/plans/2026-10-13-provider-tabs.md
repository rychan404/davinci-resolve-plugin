# Provider Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user search a single stock provider from a tab row (`All | Openverse | Wikimedia | Pixabay`), querying only that provider.

**Architecture:** `SearchQuery` gains a trailing `source: str | None = None` field; `SourceRegistry.search` skips sources whose name doesn't match and reports `"not configured"` for an unknown name. `MainWindow` adds a `QTabBar` built from `registry.sources` that feeds `build_query` and re-runs the search on tab change. The CLI gets a matching `--source` option.

**Tech Stack:** Python 3.11, PySide6 (Qt Widgets), httpx, pytest.

**Spec:** `docs/superpowers/specs/2026-10-13-provider-tabs-design.md`

## Global Constraints

- Python >= 3.11; runtime dependencies stay `PySide6>=6.11` and `httpx>=0.27`. No new dependencies.
- `SearchQuery.source` must be appended **after** `photos_only`. `cli.py` and `test_search_query_keeps_commercial_safety_as_its_sixth_field` depend on positional order.
- `source=None` means "all configured sources" and must behave exactly like today's search.
- Source names are the adapters' `name` attributes: `"openverse"`, `"wikimedia"`, `"pixabay"`. Tab labels are `name.capitalize()`; the first tab is `"All"`.
- Unknown/unconfigured source → no results and `errors == {name: "not configured"}`.
- Qt tests run headless (`QT_QPA_PLATFORM=offscreen` at top of `tests/test_ui.py`). No real network I/O in tests.
- Run tests from the repo root with `.venv/Scripts/python -m pytest` (Windows) or `.venv/bin/python -m pytest` (macOS/Linux). Baseline: 53 passed.
- Do not change `USER_AGENT` in `resolvestock/sources/base.py`.
- Commit messages: Conventional Commits, no co-author/attribution trailer.

## Review Focus

- Whitespace-only search text + tab switch → no search and status label unchanged (pinned in Task 2 empty-text test using `"   "`).
- Filters chosen before switching tabs (e.g. Transparent only) → still applied to the new tab's search (pinned in Task 2 tab-switch test).
- Pressing Enter / Search while a provider tab is selected → searches only that provider (pinned in Task 2 `run_search` test).
- CLI `--source` with a name outside the choices → argparse rejects it (exit code 2) rather than silently searching all (pinned in Task 1).
- A selected provider that fails (network/429) → its error still surfaces via `outcome.errors`; the other, skipped sources must not appear in errors (pinned in Task 1 skip test, where the skipped source is a failing fake).

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `resolvestock/sources/base.py` | `SearchQuery` contract | Modify — add `source` field |
| `resolvestock/sources/registry.py` | Fan-out across sources | Modify — skip non-matching sources, report unconfigured |
| `resolvestock/cli.py` | Terminal search harness | Modify — `--source` option |
| `README.md` | Usage docs | Modify — document `--source` |
| `resolvestock/ui/main_window.py` | Search window | Modify — provider `QTabBar` |
| `tests/test_core.py` | Core/CLI tests | Modify — registry + CLI tests |
| `tests/test_ui.py` | Window tests | Modify — `FakeRegistry.sources`, tab tests |

No new files.

### Existing test helpers you will reuse

- `tests/test_core.py`: `result(source, source_id, license_id)` builds a `SearchResult`; `_Source(name, values=None, error=None)` is a fake `Source` that returns `values` or raises `error`.
- `tests/test_ui.py`: `app` fixture (QApplication), `make_result()`, `FakeRegistry` (records `queries`), `FakeLibrary(root)`, `Config.load(path)`.

---

### Task 1: Provider selection in the query, registry, and CLI

**Files:**
- Modify: `resolvestock/sources/base.py:22-33` (`SearchQuery`)
- Modify: `resolvestock/sources/registry.py:20-39` (`SourceRegistry.search`)
- Modify: `resolvestock/cli.py:31-40` (`build_parser`), `resolvestock/cli.py:50-59` (`main`)
- Modify: `README.md:51-52` (CLI options line)
- Test: `tests/test_core.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `SearchQuery.source: str | None = None` (last field). `SourceRegistry.search(query)` honors it. `SourceRegistry.sources: list[Source]` (existing attribute, each with `.name: str`) — Task 2 builds tabs from it. CLI `args.source: str | None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_core.py`:

```python
def test_registry_searches_only_the_selected_source():
    outcome = SourceRegistry(
        [
            _Source("a", error=RuntimeError("should not be called")),
            _Source("b", [result("b", "1")]),
        ]
    ).search(SearchQuery("smoke", source="b"))
    assert [entry.uid for entry in outcome.results] == ["b:1"]
    assert outcome.errors == {}


def test_registry_reports_an_unconfigured_source():
    outcome = SourceRegistry([_Source("a", [result("a", "1")])]).search(
        SearchQuery("smoke", source="pixabay")
    )
    assert outcome.results == []
    assert outcome.errors == {"pixabay": "not configured"}


def test_cli_can_restrict_a_search_to_one_source():
    from resolvestock.cli import build_parser

    parser = build_parser()
    assert parser.parse_args(["smoke", "--source", "wikimedia"]).source == "wikimedia"
    assert parser.parse_args(["smoke"]).source is None


def test_cli_rejects_an_unknown_source():
    import pytest
    from resolvestock.cli import build_parser

    with pytest.raises(SystemExit) as raised:
        build_parser().parse_args(["smoke", "--source", "flickr"])
    assert raised.value.code == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_core.py -k "selected_source or unconfigured_source or one_source or unknown_source" -v`
Expected: the two registry tests FAIL with `TypeError: SearchQuery.__init__() got an unexpected keyword argument 'source'`; `test_cli_can_restrict_a_search_to_one_source` FAILS with `error: unrecognized arguments: --source wikimedia` (SystemExit). `test_cli_rejects_an_unknown_source` may already pass (argparse rejects the unknown flag with exit 2); that's fine.

- [ ] **Step 3: Add the `source` field to `SearchQuery`**

In `resolvestock/sources/base.py`, add one line at the end of the dataclass, after `photos_only`:

```python
    photos_only: bool = False
    # None searches every configured source; a name searches only that one.
    source: str | None = None
```

- [ ] **Step 4: Filter sources in the registry**

In `resolvestock/sources/registry.py`, replace the start of `SourceRegistry.search` (the line `outcome, per_source = SearchOutcome(), []` through the `for source in self.sources:` loop header) so it reads:

```python
    def search(self, query: SearchQuery) -> SearchOutcome:
        outcome, per_source = SearchOutcome(), []
        sources = [
            source for source in self.sources if query.source in (None, source.name)
        ]
        if query.source and not sources:
            outcome.errors[query.source] = "not configured"
        for source in sources:
            try:
                per_source.append(source.search(query))
            except Exception as error:
                outcome.errors[source.name] = str(error)
```

Leave the rest of the method (interleave, commercial-safe filter, dedupe) unchanged.

- [ ] **Step 5: Add `--source` to the CLI**

In `resolvestock/cli.py` `build_parser`, add after the `--photos` line:

```python
    parser.add_argument("--source", choices=["openverse", "wikimedia", "pixabay"])
```

In `main`, add to the `SearchQuery(...)` call after `photos_only=args.photos,`:

```python
            source=args.source,
```

No other CLI change: an unconfigured source yields no results, `format_results` prints `! pixabay failed: not configured`, and `main` returns 1.

- [ ] **Step 6: Document the option**

In `README.md`, change the options line:

```markdown
Options: `--transparent`, `--vectors`, `--photos`, `--include-restricted`
(include NC/SA/unknown licenses), `--source openverse|wikimedia|pixabay`
(search one provider), `--page N`, `--per-page N`.
```

- [ ] **Step 7: Run the full suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 57 passed (53 baseline + 4 new), including the unchanged `test_search_query_keeps_commercial_safety_as_its_sixth_field`.

- [ ] **Step 8: Commit**

```bash
git add resolvestock/sources/base.py resolvestock/sources/registry.py resolvestock/cli.py README.md tests/test_core.py
git commit -m "feat: search a single provider via SearchQuery.source and --source"
```

---

### Task 2: Provider tabs in the main window

**Files:**
- Modify: `resolvestock/ui/main_window.py` (imports `:5-16`, `__init__` `:41-112`, `build_query` `:118-125`)
- Test: `tests/test_ui.py` (`FakeRegistry` `:455-462`, new tests appended at end)

**Interfaces:**
- Consumes: `SearchQuery.source: str | None` and `registry.sources` (list of objects with `.name: str`) from Task 1.
- Produces: `MainWindow.source_tabs: QTabBar` — tab 0 `"All"` with data `None`, then one tab per source with data `source.name`. `MainWindow._on_source_tab_changed(index: int) -> None`.

- [ ] **Step 1: Give `FakeRegistry` sources**

`MainWindow` will read `registry.sources`, so every existing window test needs it. In `tests/test_ui.py`, add `from types import SimpleNamespace` to the stdlib imports at the top, and change `FakeRegistry.__init__` to:

```python
class FakeRegistry:
    def __init__(self, names=("openverse", "wikimedia")):
        self.queries = []
        self.sources = [SimpleNamespace(name=name) for name in names]
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_ui.py`:

```python
def _window(registry, tmp_path):
    return MainWindow(
        registry, FakeLibrary(tmp_path / "library"), Config.load(tmp_path / "config.json")
    )


def test_source_tabs_list_all_then_each_configured_provider(app, tmp_path):
    window = _window(FakeRegistry(("openverse", "wikimedia", "pixabay")), tmp_path)
    tabs = window.source_tabs
    assert [tabs.tabText(i) for i in range(tabs.count())] == [
        "All",
        "Openverse",
        "Wikimedia",
        "Pixabay",
    ]
    assert tabs.currentIndex() == 0
    assert [tabs.tabData(i) for i in range(tabs.count())] == [
        None,
        "openverse",
        "wikimedia",
        "pixabay",
    ]


def test_switching_tabs_reruns_the_search_against_that_provider(app, tmp_path):
    registry = FakeRegistry()
    window = _window(registry, tmp_path)
    window.search_input.setText("smoke")
    window.transparent_checkbox.setChecked(True)
    window.source_tabs.setCurrentIndex(2)
    assert registry.queries[-1].source == "wikimedia"
    assert registry.queries[-1].transparent_only
    window.source_tabs.setCurrentIndex(0)
    assert registry.queries[-1].source is None
    assert len(registry.queries) == 2


def test_search_uses_the_selected_provider_tab(app, tmp_path):
    registry = FakeRegistry()
    window = _window(registry, tmp_path)
    window.source_tabs.setCurrentIndex(1)  # empty text: no search yet
    window.search_input.setText("smoke")
    window.run_search()
    assert [query.source for query in registry.queries] == ["openverse"]


def test_switching_tabs_with_no_search_text_does_nothing(app, tmp_path):
    registry = FakeRegistry()
    window = _window(registry, tmp_path)
    window.search_input.setText("   ")
    window.source_tabs.setCurrentIndex(1)
    assert registry.queries == []
    assert window.status_label.text() == "ready"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_ui.py -k "source_tabs or switching_tabs or selected_provider_tab" -v`
Expected: all four FAIL with `AttributeError: 'MainWindow' object has no attribute 'source_tabs'`.

- [ ] **Step 4: Build the tab bar**

In `resolvestock/ui/main_window.py`, add `QTabBar` to the `PySide6.QtWidgets` import list (alphabetical, after `QSplitter`):

```python
    QSplitter,
    QTabBar,
    QVBoxLayout,
```

In `MainWindow.__init__`, after `filters.addWidget(self.credits_button)`, add:

```python
        self.source_tabs = QTabBar()
        self.source_tabs.addTab("All")
        for source in registry.sources:
            self.source_tabs.setTabData(
                self.source_tabs.addTab(source.name.capitalize()), source.name
            )
        # Connected after the tabs exist: addTab on an empty bar emits
        # currentChanged, which must not trigger a search during construction.
        self.source_tabs.currentChanged.connect(self._on_source_tab_changed)
```

Tab 0's data is never set, so `tabData(0)` returns `None` — exactly the "all sources" value.

In the layout block, insert the tab bar between the filters row and the results label:

```python
        layout.addLayout(filters)
        layout.addWidget(self.source_tabs)
        layout.addWidget(QLabel("Results — double click to download"))
```

- [ ] **Step 5: Feed the tab into the query and re-search on change**

In `build_query`, add after `photos_only=...`:

```python
            source=self.source_tabs.tabData(self.source_tabs.currentIndex()),
```

Add this method directly after `build_query`:

```python
    def _on_source_tab_changed(self, _index: int) -> None:
        # run_search guards empty text too, but would overwrite the status
        # with "enter a search term" on a plain tab click.
        if self.search_input.text().strip():
            self.run_search()
```

- [ ] **Step 6: Run the full suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 61 passed (57 after Task 1 + 4 new). Existing window tests still pass because `FakeRegistry` now has `sources`.

- [ ] **Step 7: Manual check in the real app**

Run: `.venv/Scripts/resolvestock`
Search `smoke` on `All`, then click `Wikimedia`: results update and every tile is from Wikimedia (status bar shows a new count). Clear the search box and click `Openverse`: nothing happens. Without a Pixabay key in `~/.resolvestock/config.json`, there is no `Pixabay` tab.

- [ ] **Step 8: Commit**

```bash
git add resolvestock/ui/main_window.py tests/test_ui.py
git commit -m "feat: add provider tabs to the search window"
```
