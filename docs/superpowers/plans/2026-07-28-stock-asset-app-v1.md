# Stock Asset Sourcing App v1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone desktop app that searches free stock sources for transparent cutouts and vectors, downloads them with full license provenance, and drags them straight into DaVinci Resolve's media pool.

**Architecture:** Four layers with strict one-way dependencies — `sources/` (HTTP adapters, one per API, normalizing to a single result type), `cache/` (SQLite response cache), `library/` (download, filename normalization, provenance records), `ui/` (PySide6). The source layer is fully testable from a terminal before any UI exists. Integration with Resolve is native OS drag-and-drop carrying `file://` URLs — no Resolve API is used, so Resolve updates cannot break it.

**Tech Stack:** Python 3.11+, PySide6 6.11+, httpx, sqlite3 (stdlib), pytest, ffmpeg (subprocess, optional).

## Global Constraints

Every task's requirements implicitly include this section.

- **Python 3.11+.** Local interpreter is 3.11.9. Use `X | None` union syntax, not `Optional[X]`.
- **PySide6, never PyQt6.** PySide6 is LGPL; PyQt6 is GPL and would force the whole project GPL.
- **No network calls in tests.** Every adapter test reads a JSON fixture captured from the live API. Capturing a fixture is a one-time manual step, done in the task that needs it.
- **Pixabay responses must be cached for 24 hours.** This is a terms-of-service requirement, not an optimization.
- **No bulk-download feature, ever.** Pixabay's terms ban systematic mass downloads. Every download is one deliberate user action.
- **Commercial-safe filtering defaults to ON.** It excludes `cc-by-nc` and `cc-by-sa`.
- **Qt drags use `Qt.CopyAction` only.** A `MoveAction` would permit the drop target to delete the source file.
- **Every `SearchResult` carries its license and attribution.** No code path may drop provenance.
- **Package name is `resolvestock`.** The repo directory is currently misnamed `davinci-resolve-plugin`; the Python package must not repeat that error.
- Line length 88. Run `python -m pytest -q` from the repo root.

---

## File Structure

**Created by this plan:**

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, dependencies, pytest config |
| `resolvestock/models.py` | `SearchResult`, `LibraryItem` dataclasses |
| `resolvestock/licenses.py` | License identifiers and commercial-safety classification |
| `resolvestock/cache.py` | SQLite response cache with TTL |
| `resolvestock/sources/base.py` | `Source` protocol shared by all adapters |
| `resolvestock/sources/openverse.py` | Openverse adapter (no API key) |
| `resolvestock/sources/wikimedia.py` | Wikimedia Commons adapter (no API key) |
| `resolvestock/sources/pixabay.py` | Pixabay adapter (`colors=transparent`, `image_type=vector`) |
| `resolvestock/sources/registry.py` | Fan-out search across sources, dedupe, filtering |
| `resolvestock/library.py` | Download, filename normalization, provenance sidecar |
| `resolvestock/credits.py` | Credits list export |
| `resolvestock/cli.py` | Terminal search — also the usable-hit-rate test harness |
| `resolvestock/ui/grid.py` | Results grid with async remote thumbnails |
| `resolvestock/ui/tray.py` | Library tray; the drag source into Resolve |
| `resolvestock/ui/main_window.py` | Search bar, filters, wiring |
| `resolvestock/ui/app.py` | Entry point |
| `tests/fixtures/*.json` | Captured live API responses |

**Existing:** `prototype_drag.py` is throwaway. Task 11 ports its drag logic into `ui/tray.py`; delete the prototype in that task's commit.

---

### Task 1: Project scaffold, models, license classification

**Files:**
- Create: `pyproject.toml`, `resolvestock/__init__.py`, `resolvestock/models.py`, `resolvestock/licenses.py`, `resolvestock/sources/__init__.py`, `.gitignore`
- Test: `tests/test_licenses.py`, `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `SearchResult`, `LibraryItem`, `LICENSES: dict[str, License]`, `is_commercial_safe(license_id: str) -> bool`, `filter_commercial_safe(results: Iterable[SearchResult]) -> list[SearchResult]`.

- [ ] **Step 1: Initialize the repo and dependencies**

The directory is not yet a git repo and has no package metadata.

```bash
cd C:/Users/Ryan/Desktop/repos/davinci-resolve-plugin
git init
```

Create `.gitignore`:

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
dist/
build/
*.spec
library/
```

Create `pyproject.toml`:

```toml
[project]
name = "resolvestock"
version = "0.1.0"
description = "Free stock cutouts and vectors, dragged straight into DaVinci Resolve"
requires-python = ">=3.11"
dependencies = [
    "PySide6>=6.11",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
resolvestock = "resolvestock.ui.app:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Install:

```bash
.venv/Scripts/python.exe -m pip install -e ".[dev]"
```

- [ ] **Step 2: Write the failing tests**

`tests/test_licenses.py`:

```python
import pytest

from resolvestock.licenses import (
    LICENSES,
    filter_commercial_safe,
    is_commercial_safe,
    normalize_license_id,
)
from resolvestock.models import SearchResult


def make_result(license_id: str) -> SearchResult:
    return SearchResult(
        source="test",
        source_id="1",
        title="t",
        preview_url="https://example.invalid/p.png",
        download_url="https://example.invalid/d.png",
        media_type="image",
        width=100,
        height=100,
        has_alpha=True,
        license_id=license_id,
        license_url=LICENSES[license_id].url,
        attribution="by Someone",
        source_page_url="https://example.invalid/page",
    )


@pytest.mark.parametrize("license_id", ["cc0", "cc-by", "pixabay", "public-domain"])
def test_permissive_licenses_are_commercial_safe(license_id):
    assert is_commercial_safe(license_id) is True


@pytest.mark.parametrize("license_id", ["cc-by-nc", "cc-by-sa", "cc-by-nc-sa"])
def test_nc_and_sa_licenses_are_not_commercial_safe(license_id):
    assert is_commercial_safe(license_id) is False


def test_unknown_license_is_not_commercial_safe():
    # Unknown means unverified. Never assume permission.
    assert is_commercial_safe("mystery-license") is False


def test_filter_commercial_safe_drops_nc_and_sa():
    results = [make_result("cc0"), make_result("cc-by-nc"), make_result("cc-by")]
    kept = filter_commercial_safe(results)
    assert [r.license_id for r in kept] == ["cc0", "cc-by"]


def test_normalize_license_id_handles_source_variants():
    assert normalize_license_id("CC BY-SA") == "cc-by-sa"
    assert normalize_license_id("by-nc") == "cc-by-nc"
    assert normalize_license_id("CC0 1.0") == "cc0"


def test_every_license_has_a_name_and_url():
    for license_id, meta in LICENSES.items():
        assert meta.name, license_id
        assert meta.url.startswith("http"), license_id
```

`tests/test_models.py`:

```python
import dataclasses

from resolvestock.models import SearchResult


def test_search_result_is_frozen():
    result = SearchResult(
        source="test",
        source_id="1",
        title="t",
        preview_url="https://example.invalid/p.png",
        download_url="https://example.invalid/d.png",
        media_type="image",
        width=None,
        height=None,
        has_alpha=None,
        license_id="cc0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        attribution="",
        source_page_url="https://example.invalid/page",
    )
    assert dataclasses.is_dataclass(result)
    assert result.uid == "test:1"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'resolvestock.licenses'`

- [ ] **Step 4: Write the implementation**

`resolvestock/models.py`:

```python
"""Core data types. Every layer speaks these."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MediaType = str  # "image" | "vector" | "video"


@dataclass(frozen=True)
class SearchResult:
    """One asset as returned by a source, normalized across all sources."""

    source: str
    source_id: str
    title: str
    preview_url: str
    download_url: str
    media_type: MediaType
    width: int | None
    height: int | None
    has_alpha: bool | None
    license_id: str
    license_url: str
    attribution: str
    source_page_url: str

    @property
    def uid(self) -> str:
        """Stable identity across sources, used for dedupe and history."""
        return f"{self.source}:{self.source_id}"


@dataclass(frozen=True)
class LibraryItem:
    """A downloaded asset with its provenance retained."""

    local_path: Path
    downloaded_at: datetime
    result: SearchResult
```

`resolvestock/licenses.py`:

```python
"""License identity and commercial-safety rules.

The user cuts assets apart and republishes commercially. Two license
families are liabilities in that context:

  NC  - bans commercial use outright.
  SA  - the adapted work may inherit the ShareAlike obligation.

Anything unrecognized is treated as unsafe. Unknown means unverified, and
silently assuming permission is the one failure mode that costs real money.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from resolvestock.models import SearchResult


@dataclass(frozen=True)
class License:
    name: str
    url: str
    commercial_safe: bool
    requires_attribution: bool


LICENSES: dict[str, License] = {
    "cc0": License(
        "CC0 1.0",
        "https://creativecommons.org/publicdomain/zero/1.0/",
        commercial_safe=True,
        requires_attribution=False,
    ),
    "public-domain": License(
        "Public Domain",
        "https://en.wikipedia.org/wiki/Public_domain",
        commercial_safe=True,
        requires_attribution=False,
    ),
    "pixabay": License(
        "Pixabay Content License",
        "https://pixabay.com/service/license-summary/",
        commercial_safe=True,
        requires_attribution=False,
    ),
    "cc-by": License(
        "CC BY 4.0",
        "https://creativecommons.org/licenses/by/4.0/",
        commercial_safe=True,
        requires_attribution=True,
    ),
    "cc-by-sa": License(
        "CC BY-SA 4.0",
        "https://creativecommons.org/licenses/by-sa/4.0/",
        commercial_safe=False,
        requires_attribution=True,
    ),
    "cc-by-nc": License(
        "CC BY-NC 4.0",
        "https://creativecommons.org/licenses/by-nc/4.0/",
        commercial_safe=False,
        requires_attribution=True,
    ),
    "cc-by-nc-sa": License(
        "CC BY-NC-SA 4.0",
        "https://creativecommons.org/licenses/by-nc-sa/4.0/",
        commercial_safe=False,
        requires_attribution=True,
    ),
    "cc-by-nd": License(
        "CC BY-ND 4.0",
        "https://creativecommons.org/licenses/by-nd/4.0/",
        commercial_safe=False,
        requires_attribution=True,
    ),
}

UNKNOWN = License(
    "Unknown", "https://example.invalid/unknown",
    commercial_safe=False, requires_attribution=True,
)


def normalize_license_id(raw: str) -> str:
    """Fold the many spellings sources use into our identifiers.

    Openverse says "by-nc-sa", Wikimedia says "CC BY-SA 4.0", Pixabay says
    nothing at all. Version numbers are dropped; they do not change whether
    a license is commercially safe.
    """
    if not raw:
        return "unknown"
    text = raw.strip().lower().replace("_", "-")
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-?\d+(\.\d+)?$", "", text)  # trailing version
    text = text.replace("cc-", "", 1) if text.startswith("cc-") else text
    if text in {"0", "cc0", "zero"}:
        return "cc0"
    if text in {"pd", "public-domain", "pdm"}:
        return "public-domain"
    if text == "pixabay":
        return "pixabay"
    candidate = f"cc-{text}" if not text.startswith("cc") else text
    return candidate if candidate in LICENSES else "unknown"


def get_license(license_id: str) -> License:
    return LICENSES.get(license_id, UNKNOWN)


def is_commercial_safe(license_id: str) -> bool:
    return get_license(license_id).commercial_safe


def filter_commercial_safe(results: Iterable[SearchResult]) -> list[SearchResult]:
    return [r for r in results if is_commercial_safe(r.license_id)]
```

Note the `cc0` path: `normalize_license_id("CC0 1.0")` lowercases to `cc0-1.0`, strips the trailing version to `cc0`, and matches directly.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: PASS, 12 tests (the two `parametrize` decorators expand to 7)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore resolvestock/ tests/
git commit -m "feat: project scaffold, core models, license classification"
```

---

### Task 2: SQLite response cache with TTL

**Files:**
- Create: `resolvestock/cache.py`
- Test: `tests/test_cache.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ResponseCache(db_path: Path, ttl_seconds: int = 86400)` with `get(key: str) -> str | None`, `set(key: str, value: str) -> None`, `purge_expired() -> int`, and `make_key(url: str, params: dict) -> str`.

Pixabay requires 24-hour caching of responses. This is the enforcement point.

- [ ] **Step 1: Write the failing test**

`tests/test_cache.py`:

```python
import time

from resolvestock.cache import ResponseCache, make_key


def test_set_then_get_round_trips(tmp_path):
    cache = ResponseCache(tmp_path / "c.db")
    cache.set("k", '{"hello": 1}')
    assert cache.get("k") == '{"hello": 1}'


def test_missing_key_returns_none(tmp_path):
    cache = ResponseCache(tmp_path / "c.db")
    assert cache.get("absent") is None


def test_expired_entry_returns_none(tmp_path):
    cache = ResponseCache(tmp_path / "c.db", ttl_seconds=0)
    cache.set("k", "v")
    time.sleep(0.01)
    assert cache.get("k") is None


def test_default_ttl_is_24_hours(tmp_path):
    # Pixabay's terms require 24h caching. Guard against a careless edit.
    assert ResponseCache(tmp_path / "c.db").ttl_seconds == 86400


def test_purge_expired_removes_only_stale_rows(tmp_path):
    cache = ResponseCache(tmp_path / "c.db", ttl_seconds=0)
    cache.set("old", "v")
    time.sleep(0.01)
    cache.ttl_seconds = 86400
    cache.set("fresh", "v")
    cache.ttl_seconds = 0
    removed = cache.purge_expired()
    assert removed == 2


def test_cache_persists_across_instances(tmp_path):
    db = tmp_path / "c.db"
    ResponseCache(db).set("k", "v")
    assert ResponseCache(db).get("k") == "v"


def test_make_key_is_order_independent():
    a = make_key("https://api.example/x", {"q": "cat", "page": 1})
    b = make_key("https://api.example/x", {"page": 1, "q": "cat"})
    assert a == b


def test_make_key_excludes_api_key_values():
    # An API key in a cache key would leak the secret into the db file.
    with_key = make_key("https://api.example/x", {"q": "cat", "key": "SECRET"})
    without = make_key("https://api.example/x", {"q": "cat"})
    assert with_key == without
    assert "SECRET" not in with_key
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_cache.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'resolvestock.cache'`

- [ ] **Step 3: Write the implementation**

`resolvestock/cache.py`:

```python
"""Response cache backed by SQLite.

Pixabay's API terms require responses to be cached for 24 hours. That makes
this module a compliance requirement, not a performance tweak - do not add a
bypass flag.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

DAY_SECONDS = 86400

# Never let a credential become part of a cache key; the db is on disk.
SECRET_PARAMS = frozenset({"key", "api_key", "apikey", "token", "access_token"})


def make_key(url: str, params: dict) -> str:
    """Stable key for a request, independent of parameter ordering."""
    safe = {k: v for k, v in sorted(params.items()) if k not in SECRET_PARAMS}
    payload = json.dumps([url, safe], separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ResponseCache:
    def __init__(self, db_path: Path, ttl_seconds: int = DAY_SECONDS):
        self.db_path = Path(db_path)
        self.ttl_seconds = ttl_seconds
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.db_path)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS responses ("
            "  key TEXT PRIMARY KEY,"
            "  value TEXT NOT NULL,"
            "  stored_at REAL NOT NULL"
            ")"
        )
        self._connection.commit()

    def get(self, key: str) -> str | None:
        row = self._connection.execute(
            "SELECT value, stored_at FROM responses WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        value, stored_at = row
        if time.time() - stored_at > self.ttl_seconds:
            return None
        return value

    def set(self, key: str, value: str) -> None:
        self._connection.execute(
            "INSERT OR REPLACE INTO responses (key, value, stored_at) "
            "VALUES (?, ?, ?)",
            (key, value, time.time()),
        )
        self._connection.commit()

    def purge_expired(self) -> int:
        cutoff = time.time() - self.ttl_seconds
        cursor = self._connection.execute(
            "DELETE FROM responses WHERE stored_at < ?", (cutoff,)
        )
        self._connection.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._connection.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_cache.py -q`
Expected: PASS, 8 tests

- [ ] **Step 5: Commit**

```bash
git add resolvestock/cache.py tests/test_cache.py
git commit -m "feat: SQLite response cache with 24h TTL"
```

---

### Task 3: Source protocol and HTTP client

**Files:**
- Create: `resolvestock/sources/base.py`
- Test: `tests/test_sources_base.py`

**Interfaces:**
- Consumes: `ResponseCache`, `make_key` from Task 2.
- Produces: `SearchQuery` dataclass, `Source` abstract base class with `name: str`, `requires_key: bool`, and `search(query: SearchQuery) -> list[SearchResult]`; plus `CachedHttp(cache, client)` with `get_json(url: str, params: dict) -> dict`.

- [ ] **Step 1: Write the failing test**

`tests/test_sources_base.py`:

```python
import json

import httpx

from resolvestock.cache import ResponseCache
from resolvestock.sources.base import CachedHttp, SearchQuery


def make_http(tmp_path, handler):
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    return CachedHttp(ResponseCache(tmp_path / "c.db"), client)


def test_get_json_returns_parsed_body(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"ok": True})

    http = make_http(tmp_path, handler)
    assert http.get_json("https://api.example/x", {"q": "cat"}) == {"ok": True}


def test_second_identical_call_is_served_from_cache(tmp_path):
    calls = []

    def handler(request):
        calls.append(request.url)
        return httpx.Response(200, json={"n": len(calls)})

    http = make_http(tmp_path, handler)
    first = http.get_json("https://api.example/x", {"q": "cat"})
    second = http.get_json("https://api.example/x", {"q": "cat"})
    assert first == second == {"n": 1}
    assert len(calls) == 1


def test_different_params_miss_the_cache(tmp_path):
    calls = []

    def handler(request):
        calls.append(request.url)
        return httpx.Response(200, json={"n": len(calls)})

    http = make_http(tmp_path, handler)
    http.get_json("https://api.example/x", {"q": "cat"})
    http.get_json("https://api.example/x", {"q": "dog"})
    assert len(calls) == 2


def test_http_error_raises(tmp_path):
    def handler(request):
        return httpx.Response(429, text="rate limited")

    http = make_http(tmp_path, handler)
    try:
        http.get_json("https://api.example/x", {"q": "cat"})
    except httpx.HTTPStatusError as error:
        assert error.response.status_code == 429
    else:
        raise AssertionError("expected HTTPStatusError")


def test_error_responses_are_not_cached(tmp_path):
    calls = []

    def handler(request):
        calls.append(request.url)
        if len(calls) == 1:
            return httpx.Response(500, text="boom")
        return httpx.Response(200, json={"ok": True})

    http = make_http(tmp_path, handler)
    try:
        http.get_json("https://api.example/x", {"q": "cat"})
    except httpx.HTTPStatusError:
        pass
    assert http.get_json("https://api.example/x", {"q": "cat"}) == {"ok": True}


def test_search_query_defaults_to_commercial_safe():
    assert SearchQuery(text="cat").commercial_safe_only is True


def test_search_query_defaults_to_transparent_off():
    assert SearchQuery(text="cat").transparent_only is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sources_base.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'resolvestock.sources.base'`

- [ ] **Step 3: Write the implementation**

`resolvestock/sources/base.py`:

```python
"""Shared contract for every stock source.

Adapters never touch Qt and never write files. They turn a SearchQuery into
a list of SearchResult, and nothing else.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from resolvestock.cache import ResponseCache, make_key
from resolvestock.models import SearchResult

USER_AGENT = "resolvestock/0.1 (https://github.com/; stock sourcing for editors)"


@dataclass(frozen=True)
class SearchQuery:
    text: str
    page: int = 1
    per_page: int = 40
    transparent_only: bool = False
    vectors_only: bool = False
    commercial_safe_only: bool = True


class CachedHttp:
    """GET JSON through the response cache.

    Only successful responses are stored. Caching a 429 or a 500 would make
    a transient failure look permanent for 24 hours.
    """

    def __init__(self, cache: ResponseCache, client: httpx.Client | None = None):
        self.cache = cache
        self.client = client or httpx.Client(
            timeout=15.0, headers={"User-Agent": USER_AGENT}
        )

    def get_json(self, url: str, params: dict) -> dict:
        key = make_key(url, params)
        cached = self.cache.get(key)
        if cached is not None:
            return json.loads(cached)
        response = self.client.get(url, params=params)
        response.raise_for_status()
        self.cache.set(key, response.text)
        return response.json()


class Source(ABC):
    name: str
    requires_key: bool = False

    @abstractmethod
    def search(self, query: SearchQuery) -> list[SearchResult]:
        """Return normalized results. Must not raise on empty results."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sources_base.py -q`
Expected: PASS, 7 tests

- [ ] **Step 5: Commit**

```bash
git add resolvestock/sources/base.py tests/test_sources_base.py
git commit -m "feat: source protocol and cached HTTP client"
```

---

### Task 4: Openverse adapter

**Files:**
- Create: `resolvestock/sources/openverse.py`, `tests/fixtures/openverse_transparent.json`
- Test: `tests/test_sources_openverse.py`

**Interfaces:**
- Consumes: `Source`, `SearchQuery`, `CachedHttp` from Task 3.
- Produces: `OpenverseSource(http: CachedHttp)` with `name = "openverse"`, `requires_key = False`, and `parse(payload: dict) -> list[SearchResult]`.

Openverse is built first because it needs **no API key**. First launch must return results before the user has pasted anything.

- [ ] **Step 1: Capture a real response as a fixture**

Do not write the parser from memory. Capture ground truth first:

```bash
.venv/Scripts/python.exe -c "import httpx, json, pathlib; r = httpx.get('https://api.openverse.org/v1/images/', params={'q': 'smoke', 'page_size': 5}, headers={'User-Agent': 'resolvestock/0.1'}, timeout=30); r.raise_for_status(); pathlib.Path('tests/fixtures').mkdir(parents=True, exist_ok=True); pathlib.Path('tests/fixtures/openverse_transparent.json').write_text(json.dumps(r.json(), indent=2), encoding='utf-8'); print(json.dumps(r.json()['results'][0], indent=2))"
```

Read the printed record. Confirm the field names before writing Step 3, and adjust the parser if they differ from what is written below. Expected top-level shape is `{"result_count": int, "results": [...]}`; each result is expected to carry `id`, `title`, `url`, `thumbnail`, `license`, `license_version`, `license_url`, `foreign_landing_url`, `creator`, `width`, `height`, `filetype`.

If Openverse returns a 401, it now requires registration — record that in `docs/spec.md` §11 and register for a client id before continuing.

- [ ] **Step 2: Write the failing test**

`tests/test_sources_openverse.py`:

```python
import json
from pathlib import Path

import httpx

from resolvestock.cache import ResponseCache
from resolvestock.sources.base import CachedHttp, SearchQuery
from resolvestock.sources.openverse import OpenverseSource

FIXTURE = Path(__file__).parent / "fixtures" / "openverse_transparent.json"


def make_source(tmp_path):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def handler(request):
        return httpx.Response(200, json=payload)

    http = CachedHttp(
        ResponseCache(tmp_path / "c.db"),
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    return OpenverseSource(http)


def test_search_returns_results(tmp_path):
    results = make_source(tmp_path).search(SearchQuery(text="smoke"))
    assert results, "fixture should yield at least one result"


def test_results_are_normalized(tmp_path):
    result = make_source(tmp_path).search(SearchQuery(text="smoke"))[0]
    assert result.source == "openverse"
    assert result.source_id
    assert result.download_url.startswith("http")
    assert result.preview_url.startswith("http")
    assert result.source_page_url.startswith("http")
    assert result.media_type in {"image", "vector"}


def test_every_result_carries_a_known_or_unknown_license(tmp_path):
    from resolvestock.licenses import LICENSES

    for result in make_source(tmp_path).search(SearchQuery(text="smoke")):
        assert result.license_id in LICENSES or result.license_id == "unknown"


def test_attribution_mentions_the_creator_when_present(tmp_path):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    creators = [r.get("creator") for r in payload["results"] if r.get("creator")]
    if not creators:
        return  # fixture has no attributed works; nothing to assert
    results = make_source(tmp_path).search(SearchQuery(text="smoke"))
    assert any(c in r.attribution for r in results for c in creators)


def test_svg_results_are_typed_as_vector(tmp_path):
    source = make_source(tmp_path)
    parsed = source.parse(
        {
            "results": [
                {
                    "id": "abc",
                    "title": "arrow",
                    "url": "https://example.invalid/a.svg",
                    "thumbnail": "https://example.invalid/a.png",
                    "license": "by",
                    "license_version": "4.0",
                    "license_url": "https://creativecommons.org/licenses/by/4.0/",
                    "foreign_landing_url": "https://example.invalid/page",
                    "creator": "Someone",
                    "width": 100,
                    "height": 100,
                    "filetype": "svg",
                }
            ]
        }
    )
    assert parsed[0].media_type == "vector"
    assert parsed[0].has_alpha is True
    assert parsed[0].license_id == "cc-by"


def test_missing_optional_fields_do_not_crash(tmp_path):
    parsed = make_source(tmp_path).parse({"results": [{"id": "x", "url": "https://e.invalid/a.png"}]})
    assert parsed[0].source_id == "x"
    assert parsed[0].license_id == "unknown"


def test_empty_payload_returns_empty_list(tmp_path):
    assert make_source(tmp_path).parse({"results": []}) == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sources_openverse.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'resolvestock.sources.openverse'`

- [ ] **Step 4: Write the implementation**

`resolvestock/sources/openverse.py`:

```python
"""Openverse adapter.

No API key required, which makes this the source that proves the app works
on first launch before any credential has been entered.
"""

from __future__ import annotations

from resolvestock.licenses import normalize_license_id
from resolvestock.models import SearchResult
from resolvestock.sources.base import CachedHttp, SearchQuery, Source

ENDPOINT = "https://api.openverse.org/v1/images/"
VECTOR_TYPES = {"svg"}
ALPHA_TYPES = {"png", "svg", "gif", "webp"}


class OpenverseSource(Source):
    name = "openverse"
    requires_key = False

    def __init__(self, http: CachedHttp):
        self.http = http

    def search(self, query: SearchQuery) -> list[SearchResult]:
        params: dict[str, object] = {
            "q": query.text,
            "page": query.page,
            "page_size": query.per_page,
        }
        if query.vectors_only:
            params["extension"] = "svg"
        elif query.transparent_only:
            # Openverse has no alpha flag; extension is the closest proxy.
            params["extension"] = "png,svg"
        if query.commercial_safe_only:
            params["license_type"] = "commercial,modification"
        return self.parse(self.http.get_json(ENDPOINT, params))

    def parse(self, payload: dict) -> list[SearchResult]:
        results = []
        for record in payload.get("results", []):
            filetype = (record.get("filetype") or "").lower()
            license_id = normalize_license_id(record.get("license") or "")
            creator = record.get("creator") or ""
            title = record.get("title") or "untitled"
            page_url = record.get("foreign_landing_url") or record.get("url") or ""
            results.append(
                SearchResult(
                    source=self.name,
                    source_id=str(record.get("id", "")),
                    title=title,
                    preview_url=record.get("thumbnail") or record.get("url") or "",
                    download_url=record.get("url") or "",
                    media_type="vector" if filetype in VECTOR_TYPES else "image",
                    width=record.get("width"),
                    height=record.get("height"),
                    has_alpha=filetype in ALPHA_TYPES if filetype else None,
                    license_id=license_id,
                    license_url=record.get("license_url") or "",
                    attribution=(
                        f"{title} by {creator} (Openverse)" if creator
                        else f"{title} (Openverse)"
                    ),
                    source_page_url=page_url,
                )
            )
        return results
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sources_openverse.py -q`
Expected: PASS, 7 tests

If a test fails because the live fixture uses different field names than the parser, the fixture wins. Fix the parser.

- [ ] **Step 6: Commit**

```bash
git add resolvestock/sources/openverse.py tests/test_sources_openverse.py tests/fixtures/openverse_transparent.json
git commit -m "feat: Openverse source adapter"
```

---

### Task 5: Wikimedia Commons adapter

**Files:**
- Create: `resolvestock/sources/wikimedia.py`, `tests/fixtures/wikimedia_search.json`
- Test: `tests/test_sources_wikimedia.py`

**Interfaces:**
- Consumes: `Source`, `SearchQuery`, `CachedHttp` from Task 3.
- Produces: `WikimediaSource(http: CachedHttp)` with `name = "wikimedia"`, `requires_key = False`, `parse(payload: dict) -> list[SearchResult]`.

Wikimedia is the best free source of true-alpha PNG and SVG. Its API returns a
dict of pages rather than a list, and license data lives in `extmetadata`.

- [ ] **Step 1: Capture a real response as a fixture**

```bash
.venv/Scripts/python.exe -c "import httpx, json, pathlib; r = httpx.get('https://commons.wikimedia.org/w/api.php', params={'action':'query','format':'json','generator':'search','gsrsearch':'filetype:bitmap arrow','gsrnamespace':6,'gsrlimit':5,'prop':'imageinfo','iiprop':'url|size|mime|extmetadata'}, headers={'User-Agent':'resolvestock/0.1 (contact: rychanrc@outlook.com)'}, timeout=30); r.raise_for_status(); pathlib.Path('tests/fixtures/wikimedia_search.json').write_text(json.dumps(r.json(), indent=2), encoding='utf-8'); print(list(r.json().get('query', {}).get('pages', {}).values())[0])"
```

Confirm the shape before writing the parser. Wikimedia requires a descriptive
`User-Agent` with contact information; requests without one get blocked.

- [ ] **Step 2: Write the failing test**

`tests/test_sources_wikimedia.py`:

```python
import json
from pathlib import Path

import httpx

from resolvestock.cache import ResponseCache
from resolvestock.sources.base import CachedHttp, SearchQuery
from resolvestock.sources.wikimedia import WikimediaSource

FIXTURE = Path(__file__).parent / "fixtures" / "wikimedia_search.json"


def make_source(tmp_path, payload=None):
    body = payload or json.loads(FIXTURE.read_text(encoding="utf-8"))

    def handler(request):
        return httpx.Response(200, json=body)

    http = CachedHttp(
        ResponseCache(tmp_path / "c.db"),
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    return WikimediaSource(http)


def test_search_returns_results(tmp_path):
    assert make_source(tmp_path).search(SearchQuery(text="arrow"))


def test_pages_dict_is_flattened_to_a_list(tmp_path):
    results = make_source(tmp_path).search(SearchQuery(text="arrow"))
    assert isinstance(results, list)
    assert len({r.source_id for r in results}) == len(results)


def test_license_is_read_from_extmetadata(tmp_path):
    payload = {
        "query": {
            "pages": {
                "42": {
                    "pageid": 42,
                    "title": "File:Arrow.svg",
                    "imageinfo": [
                        {
                            "url": "https://upload.example/Arrow.svg",
                            "thumburl": "https://upload.example/thumb.png",
                            "descriptionurl": "https://commons.example/File:Arrow.svg",
                            "width": 512,
                            "height": 512,
                            "mime": "image/svg+xml",
                            "extmetadata": {
                                "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                "LicenseUrl": {"value": "https://cc.example/by-sa"},
                                "Artist": {"value": "<a href='#'>Jane</a>"},
                            },
                        }
                    ],
                }
            }
        }
    }
    result = make_source(tmp_path, payload).search(SearchQuery(text="arrow"))[0]
    assert result.license_id == "cc-by-sa"
    assert result.media_type == "vector"
    assert result.has_alpha is True


def test_artist_html_is_stripped_from_attribution(tmp_path):
    payload = {
        "query": {
            "pages": {
                "7": {
                    "pageid": 7,
                    "title": "File:X.png",
                    "imageinfo": [
                        {
                            "url": "https://upload.example/X.png",
                            "descriptionurl": "https://commons.example/File:X.png",
                            "mime": "image/png",
                            "extmetadata": {
                                "Artist": {"value": "<a href='/u/Jane'>Jane Doe</a>"},
                                "LicenseShortName": {"value": "CC0"},
                            },
                        }
                    ],
                }
            }
        }
    }
    result = make_source(tmp_path, payload).search(SearchQuery(text="x"))[0]
    assert "Jane Doe" in result.attribution
    assert "<a" not in result.attribution


def test_missing_query_key_returns_empty(tmp_path):
    assert make_source(tmp_path, {}).search(SearchQuery(text="nothing")) == []


def test_pages_without_imageinfo_are_skipped(tmp_path):
    payload = {"query": {"pages": {"1": {"pageid": 1, "title": "File:No.png"}}}}
    assert make_source(tmp_path, payload).search(SearchQuery(text="x")) == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sources_wikimedia.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'resolvestock.sources.wikimedia'`

- [ ] **Step 4: Write the implementation**

`resolvestock/sources/wikimedia.py`:

```python
"""Wikimedia Commons adapter.

Best free supply of true-alpha PNG and SVG. Two quirks shape this module:
the API returns a dict of pages keyed by page id rather than a list, and
license data is buried in extmetadata as HTML fragments.
"""

from __future__ import annotations

import re

from resolvestock.licenses import normalize_license_id
from resolvestock.models import SearchResult
from resolvestock.sources.base import CachedHttp, SearchQuery, Source

ENDPOINT = "https://commons.wikimedia.org/w/api.php"
ALPHA_MIMES = {"image/png", "image/svg+xml", "image/webp", "image/gif"}
TAG_PATTERN = re.compile(r"<[^>]+>")


def strip_html(value: str) -> str:
    return TAG_PATTERN.sub("", value).strip()


class WikimediaSource(Source):
    name = "wikimedia"
    requires_key = False

    def __init__(self, http: CachedHttp):
        self.http = http

    def search(self, query: SearchQuery) -> list[SearchResult]:
        terms = query.text
        if query.vectors_only:
            terms = f"filetype:drawing {terms}"
        elif query.transparent_only:
            terms = f"filemime:png {terms}"
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": terms,
            "gsrnamespace": 6,
            "gsrlimit": query.per_page,
            "gsroffset": (query.page - 1) * query.per_page,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 320,
        }
        return self.parse(self.http.get_json(ENDPOINT, params))

    def parse(self, payload: dict) -> list[SearchResult]:
        pages = payload.get("query", {}).get("pages", {}) or {}
        results = []
        for page in pages.values():
            info_list = page.get("imageinfo") or []
            if not info_list:
                continue
            info = info_list[0]
            meta = info.get("extmetadata") or {}
            mime = (info.get("mime") or "").lower()
            license_raw = (meta.get("LicenseShortName") or {}).get("value", "")
            artist = strip_html((meta.get("Artist") or {}).get("value", ""))
            title = page.get("title", "").removeprefix("File:") or "untitled"
            results.append(
                SearchResult(
                    source=self.name,
                    source_id=str(page.get("pageid", "")),
                    title=title,
                    preview_url=info.get("thumburl") or info.get("url") or "",
                    download_url=info.get("url") or "",
                    media_type="vector" if mime == "image/svg+xml" else "image",
                    width=info.get("width"),
                    height=info.get("height"),
                    has_alpha=mime in ALPHA_MIMES if mime else None,
                    license_id=normalize_license_id(license_raw),
                    license_url=(meta.get("LicenseUrl") or {}).get("value", ""),
                    attribution=(
                        f"{title} by {artist} (Wikimedia Commons)" if artist
                        else f"{title} (Wikimedia Commons)"
                    ),
                    source_page_url=info.get("descriptionurl") or "",
                )
            )
        return results
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sources_wikimedia.py -q`
Expected: PASS, 6 tests

- [ ] **Step 6: Commit**

```bash
git add resolvestock/sources/wikimedia.py tests/test_sources_wikimedia.py tests/fixtures/wikimedia_search.json
git commit -m "feat: Wikimedia Commons source adapter"
```

---

### Task 6: Pixabay adapter with transparent and vector filters

**Files:**
- Create: `resolvestock/sources/pixabay.py`, `resolvestock/config.py`, `tests/fixtures/pixabay_transparent.json`
- Test: `tests/test_sources_pixabay.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: `Source`, `SearchQuery`, `CachedHttp` from Task 3.
- Produces: `PixabaySource(http: CachedHttp, api_key: str)` with `name = "pixabay"`, `requires_key = True`, `parse(payload: dict) -> list[SearchResult]`; and `Config` with `load() -> Config`, `save() -> None`, `pixabay_key: str | None`, `library_dir: Path`.

`colors=transparent` combined with `image_type=vector` is the reason this
source matters — it is a real server-side cutout filter that Pixabay's own
website barely exposes.

- [ ] **Step 1: Get an API key and capture a fixture**

Register at https://pixabay.com/api/docs/ (instant, no approval). Then:

```bash
PIXABAY_KEY=your_key_here
.venv/Scripts/python.exe -c "import httpx, json, os, pathlib; r = httpx.get('https://pixabay.com/api/', params={'key': os.environ['PIXABAY_KEY'], 'q': 'arrow', 'image_type': 'vector', 'colors': 'transparent', 'per_page': 5}, timeout=30); r.raise_for_status(); body = r.json(); [h.pop('userImageURL', None) for h in body['hits']]; pathlib.Path('tests/fixtures/pixabay_transparent.json').write_text(json.dumps(body, indent=2), encoding='utf-8'); print(json.dumps(body['hits'][0], indent=2))"
```

Confirm `totalHits > 0`. If `colors=transparent` returns nothing for vectors,
record that in `docs/spec.md` §11 — it would weaken the core v1 filter and
should be known before the UI is built.

**The fixture must not contain your API key.** The capture command above sends
the key as a parameter but Pixabay does not echo it in the body; verify by
searching the written file for the key before committing.

- [ ] **Step 2: Write the failing test**

`tests/test_config.py`:

```python
from pathlib import Path

from resolvestock.config import Config


def test_defaults_have_no_key_and_a_library_dir(tmp_path):
    config = Config.load(tmp_path / "config.json")
    assert config.pixabay_key is None
    assert isinstance(config.library_dir, Path)


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "config.json"
    config = Config.load(path)
    config.pixabay_key = "abc123"
    config.library_dir = tmp_path / "lib"
    config.save()
    assert Config.load(path).pixabay_key == "abc123"
    assert Config.load(path).library_dir == tmp_path / "lib"


def test_corrupt_config_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    assert Config.load(path).pixabay_key is None
```

`tests/test_sources_pixabay.py`:

```python
import json
from pathlib import Path

import httpx

from resolvestock.cache import ResponseCache
from resolvestock.sources.base import CachedHttp, SearchQuery
from resolvestock.sources.pixabay import PixabaySource

FIXTURE = Path(__file__).parent / "fixtures" / "pixabay_transparent.json"


def make_source(tmp_path, captured=None):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def handler(request):
        if captured is not None:
            captured.append(dict(request.url.params))
        return httpx.Response(200, json=payload)

    http = CachedHttp(
        ResponseCache(tmp_path / "c.db"),
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    return PixabaySource(http, api_key="TESTKEY")


def test_search_returns_results(tmp_path):
    assert make_source(tmp_path).search(SearchQuery(text="arrow"))


def test_transparent_only_sends_the_colors_filter(tmp_path):
    captured = []
    make_source(tmp_path, captured).search(
        SearchQuery(text="arrow", transparent_only=True)
    )
    assert captured[0]["colors"] == "transparent"


def test_vectors_only_sends_the_image_type_filter(tmp_path):
    captured = []
    make_source(tmp_path, captured).search(SearchQuery(text="arrow", vectors_only=True))
    assert captured[0]["image_type"] == "vector"


def test_plain_search_sends_neither_filter(tmp_path):
    captured = []
    make_source(tmp_path, captured).search(SearchQuery(text="arrow"))
    assert "colors" not in captured[0]
    assert captured[0].get("image_type") == "all"


def test_pixabay_results_use_the_pixabay_license(tmp_path):
    for result in make_source(tmp_path).search(SearchQuery(text="arrow")):
        assert result.license_id == "pixabay"


def test_download_url_prefers_the_largest_available(tmp_path):
    source = make_source(tmp_path)
    parsed = source.parse(
        {
            "hits": [
                {
                    "id": 5,
                    "tags": "arrow, sign",
                    "pageURL": "https://pixabay.com/x-5/",
                    "previewURL": "https://cdn.pixabay.com/p.png",
                    "webformatURL": "https://cdn.pixabay.com/w.png",
                    "largeImageURL": "https://cdn.pixabay.com/l.png",
                    "imageWidth": 1920,
                    "imageHeight": 1080,
                    "type": "vector/svg",
                    "user": "someone",
                }
            ]
        }
    )
    assert parsed[0].download_url == "https://cdn.pixabay.com/l.png"
    assert parsed[0].media_type == "vector"
    assert parsed[0].title == "arrow, sign"


def test_api_key_never_appears_in_a_result(tmp_path):
    for result in make_source(tmp_path).search(SearchQuery(text="arrow")):
        assert "TESTKEY" not in result.download_url
        assert "TESTKEY" not in result.preview_url


def test_empty_hits_returns_empty_list(tmp_path):
    assert make_source(tmp_path).parse({"hits": []}) == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sources_pixabay.py tests/test_config.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'resolvestock.config'`

- [ ] **Step 4: Write the implementation**

`resolvestock/config.py`:

```python
"""User configuration - API keys and library location.

Kept deliberately small. Openverse and Wikimedia need no credentials, so the
app must work fully before this file has ever been written.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".resolvestock" / "config.json"
DEFAULT_LIBRARY_DIR = Path.home() / "ResolveStock"


@dataclass
class Config:
    path: Path
    pixabay_key: str | None = None
    library_dir: Path = DEFAULT_LIBRARY_DIR

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> Config:
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls(path=path)
        library = data.get("library_dir")
        return cls(
            path=path,
            pixabay_key=data.get("pixabay_key") or None,
            library_dir=Path(library) if library else DEFAULT_LIBRARY_DIR,
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "pixabay_key": self.pixabay_key,
                    "library_dir": str(self.library_dir),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
```

`resolvestock/sources/pixabay.py`:

```python
"""Pixabay adapter.

Carries the filter that justifies v1: colors=transparent, optionally with
image_type=vector. Both are real server-side filters.

Two terms-of-service obligations are enforced elsewhere but noted here so
they are not lost: responses must be cached 24h (see cache.py), and
systematic mass downloads are forbidden - so this module never fetches an
asset, only metadata.
"""

from __future__ import annotations

from resolvestock.models import SearchResult
from resolvestock.sources.base import CachedHttp, SearchQuery, Source

ENDPOINT = "https://pixabay.com/api/"


class PixabaySource(Source):
    name = "pixabay"
    requires_key = True

    def __init__(self, http: CachedHttp, api_key: str):
        self.http = http
        self.api_key = api_key

    def search(self, query: SearchQuery) -> list[SearchResult]:
        params: dict[str, object] = {
            "key": self.api_key,
            "q": query.text,
            "page": query.page,
            "per_page": query.per_page,
            "image_type": "vector" if query.vectors_only else "all",
            "safesearch": "true",
        }
        if query.transparent_only:
            params["colors"] = "transparent"
        return self.parse(self.http.get_json(ENDPOINT, params))

    def parse(self, payload: dict) -> list[SearchResult]:
        results = []
        for hit in payload.get("hits", []):
            hit_type = (hit.get("type") or "").lower()
            user = hit.get("user") or ""
            title = hit.get("tags") or "untitled"
            results.append(
                SearchResult(
                    source=self.name,
                    source_id=str(hit.get("id", "")),
                    title=title,
                    preview_url=hit.get("previewURL") or "",
                    download_url=(
                        hit.get("largeImageURL")
                        or hit.get("webformatURL")
                        or hit.get("previewURL")
                        or ""
                    ),
                    media_type="vector" if "vector" in hit_type else "image",
                    width=hit.get("imageWidth"),
                    height=hit.get("imageHeight"),
                    has_alpha=None,  # Pixabay does not report alpha per item.
                    license_id="pixabay",
                    license_url="https://pixabay.com/service/license-summary/",
                    attribution=(
                        f"{title} by {user} (Pixabay)" if user
                        else f"{title} (Pixabay)"
                    ),
                    source_page_url=hit.get("pageURL") or "",
                )
            )
        return results
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sources_pixabay.py tests/test_config.py -q`
Expected: PASS, 11 tests

- [ ] **Step 6: Verify the fixture holds no secret, then commit**

```bash
grep -c "$PIXABAY_KEY" tests/fixtures/pixabay_transparent.json || echo "clean"
git add resolvestock/sources/pixabay.py resolvestock/config.py tests/test_sources_pixabay.py tests/test_config.py tests/fixtures/pixabay_transparent.json
git commit -m "feat: Pixabay adapter with transparent and vector filters"
```

---

### Task 7: Registry — fan-out search, dedupe, filtering

**Files:**
- Create: `resolvestock/sources/registry.py`
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: every `Source` from Tasks 4–6, `filter_commercial_safe` from Task 1.
- Produces: `SourceRegistry(sources: list[Source])` with `search(query: SearchQuery) -> SearchOutcome`, and `SearchOutcome` carrying `results: list[SearchResult]` plus `errors: dict[str, str]`; also `build_registry(http, config) -> SourceRegistry`.

One source failing must never blank the whole search. Errors are reported
per source and the rest of the results still come through.

- [ ] **Step 1: Write the failing test**

`tests/test_registry.py`:

```python
import pytest

from resolvestock.models import SearchResult
from resolvestock.sources.base import SearchQuery, Source
from resolvestock.sources.registry import SourceRegistry


def make_result(source, source_id, license_id="cc0", title="t"):
    return SearchResult(
        source=source,
        source_id=source_id,
        title=title,
        preview_url="https://example.invalid/p.png",
        download_url="https://example.invalid/d.png",
        media_type="image",
        width=10,
        height=10,
        has_alpha=True,
        license_id=license_id,
        license_url="https://example.invalid/l",
        attribution="a",
        source_page_url="https://example.invalid/page",
    )


class FakeSource(Source):
    def __init__(self, name, results=None, error=None):
        self.name = name
        self._results = results or []
        self._error = error

    def search(self, query):
        if self._error:
            raise self._error
        return self._results


def test_results_from_all_sources_are_merged():
    registry = SourceRegistry(
        [
            FakeSource("a", [make_result("a", "1")]),
            FakeSource("b", [make_result("b", "2")]),
        ]
    )
    outcome = registry.search(SearchQuery(text="x"))
    assert {r.uid for r in outcome.results} == {"a:1", "b:2"}


def test_one_failing_source_does_not_blank_the_search():
    registry = SourceRegistry(
        [
            FakeSource("good", [make_result("good", "1")]),
            FakeSource("bad", error=RuntimeError("rate limited")),
        ]
    )
    outcome = registry.search(SearchQuery(text="x"))
    assert [r.uid for r in outcome.results] == ["good:1"]
    assert "bad" in outcome.errors
    assert "rate limited" in outcome.errors["bad"]


def test_duplicate_uids_are_dropped():
    duplicate = make_result("a", "1")
    registry = SourceRegistry(
        [FakeSource("a", [duplicate, duplicate, make_result("a", "2")])]
    )
    outcome = registry.search(SearchQuery(text="x"))
    assert [r.uid for r in outcome.results] == ["a:1", "a:2"]


def test_commercial_safe_filter_is_applied_by_default():
    registry = SourceRegistry(
        [
            FakeSource(
                "a",
                [make_result("a", "1", "cc-by-nc"), make_result("a", "2", "cc0")],
            )
        ]
    )
    outcome = registry.search(SearchQuery(text="x"))
    assert [r.uid for r in outcome.results] == ["a:2"]


def test_commercial_safe_filter_can_be_disabled():
    registry = SourceRegistry([FakeSource("a", [make_result("a", "1", "cc-by-nc")])])
    outcome = registry.search(SearchQuery(text="x", commercial_safe_only=False))
    assert [r.uid for r in outcome.results] == ["a:1"]


def test_results_interleave_across_sources():
    # Prevents one source monopolizing the top of the grid.
    registry = SourceRegistry(
        [
            FakeSource("a", [make_result("a", "1"), make_result("a", "2")]),
            FakeSource("b", [make_result("b", "1"), make_result("b", "2")]),
        ]
    )
    outcome = registry.search(SearchQuery(text="x"))
    assert [r.uid for r in outcome.results] == ["a:1", "b:1", "a:2", "b:2"]


def test_empty_registry_returns_no_results():
    outcome = SourceRegistry([]).search(SearchQuery(text="x"))
    assert outcome.results == []
    assert outcome.errors == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_registry.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'resolvestock.sources.registry'`

- [ ] **Step 3: Write the implementation**

`resolvestock/sources/registry.py`:

```python
"""Fan out one query across every configured source.

Design rules:
  - A source that fails is reported, not fatal.
  - Results interleave round-robin so no single source owns the top of the
    grid. This is the seed of the anti-sameness ranking planned for v1.5.
  - The commercial-safe filter is applied here, once, so no UI path can
    forget it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import zip_longest

from resolvestock.licenses import filter_commercial_safe
from resolvestock.models import SearchResult
from resolvestock.sources.base import SearchQuery, Source


@dataclass
class SearchOutcome:
    results: list[SearchResult] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


class SourceRegistry:
    def __init__(self, sources: list[Source]):
        self.sources = sources

    def search(self, query: SearchQuery) -> SearchOutcome:
        outcome = SearchOutcome()
        per_source: list[list[SearchResult]] = []
        for source in self.sources:
            try:
                per_source.append(source.search(query))
            except Exception as error:  # noqa: BLE001 - one bad source is not fatal
                outcome.errors[source.name] = str(error)

        merged: list[SearchResult] = []
        for group in zip_longest(*per_source):
            merged.extend(item for item in group if item is not None)

        if query.commercial_safe_only:
            merged = filter_commercial_safe(merged)

        seen: set[str] = set()
        for result in merged:
            if result.uid in seen:
                continue
            seen.add(result.uid)
            outcome.results.append(result)
        return outcome


def build_registry(http, config) -> SourceRegistry:
    """Assemble the sources that are usable given current configuration.

    Openverse and Wikimedia need no credentials, so a first launch with an
    empty config still returns results.
    """
    from resolvestock.sources.openverse import OpenverseSource
    from resolvestock.sources.pixabay import PixabaySource
    from resolvestock.sources.wikimedia import WikimediaSource

    sources: list[Source] = [OpenverseSource(http), WikimediaSource(http)]
    if config.pixabay_key:
        sources.append(PixabaySource(http, config.pixabay_key))
    return SourceRegistry(sources)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_registry.py -q`
Expected: PASS, 7 tests

- [ ] **Step 5: Commit**

```bash
git add resolvestock/sources/registry.py tests/test_registry.py
git commit -m "feat: source registry with fan-out, interleave, and dedupe"
```

---

### Task 8: CLI — and the usable-hit-rate measurement

**Files:**
- Create: `resolvestock/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `SourceRegistry`, `SearchQuery`, `Config`, `ResponseCache`, `CachedHttp`.
- Produces: `format_results(outcome: SearchOutcome) -> str`, `main(argv: list[str]) -> int`.

**This task is also the deferred supply test.** Once it runs, execute ten real
queries from a past project and count usable results. Record the number in
`docs/spec.md` §11. If the rate is poor, stop and revisit scope before
building any UI.

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:

```python
from resolvestock.cli import format_results
from resolvestock.models import SearchResult
from resolvestock.sources.registry import SearchOutcome


def make_result(source="openverse", license_id="cc0"):
    return SearchResult(
        source=source,
        source_id="1",
        title="smoke plume",
        preview_url="https://example.invalid/p.png",
        download_url="https://example.invalid/d.png",
        media_type="image",
        width=1920,
        height=1080,
        has_alpha=True,
        license_id=license_id,
        license_url="https://example.invalid/l",
        attribution="smoke plume by Jane (Openverse)",
        source_page_url="https://example.invalid/page",
    )


def test_format_includes_title_source_and_license():
    text = format_results(SearchOutcome(results=[make_result()]))
    assert "smoke plume" in text
    assert "openverse" in text
    assert "cc0" in text


def test_format_includes_dimensions_when_known():
    assert "1920x1080" in format_results(SearchOutcome(results=[make_result()]))


def test_format_reports_source_errors():
    outcome = SearchOutcome(results=[], errors={"pixabay": "429 rate limited"})
    text = format_results(outcome)
    assert "pixabay" in text
    assert "429" in text


def test_format_reports_the_result_count():
    text = format_results(SearchOutcome(results=[make_result(), make_result("wikimedia")]))
    assert "2 result" in text


def test_empty_outcome_says_so():
    assert "no results" in format_results(SearchOutcome()).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_cli.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'resolvestock.cli'`

- [ ] **Step 3: Write the implementation**

`resolvestock/cli.py`:

```python
"""Terminal search.

Exists to prove the source layer works before any UI is written, and to
measure the usable-hit rate that the whole project rests on.

    python -m resolvestock.cli "smoke" --transparent
"""

from __future__ import annotations

import argparse
import sys

from resolvestock.cache import ResponseCache
from resolvestock.config import Config
from resolvestock.sources.base import CachedHttp, SearchQuery
from resolvestock.sources.registry import SearchOutcome, build_registry


def format_results(outcome: SearchOutcome) -> str:
    lines: list[str] = []
    if not outcome.results:
        lines.append("no results")
    else:
        lines.append(f"{len(outcome.results)} result(s)")
        for index, result in enumerate(outcome.results, start=1):
            size = (
                f"{result.width}x{result.height}"
                if result.width and result.height
                else "size unknown"
            )
            lines.append(
                f"{index:>3}. [{result.source}] {result.title}\n"
                f"     {size}  license={result.license_id}  "
                f"alpha={result.has_alpha}\n"
                f"     {result.download_url}"
            )
    for name, message in outcome.errors.items():
        lines.append(f"! {name} failed: {message}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="resolvestock")
    parser.add_argument("query")
    parser.add_argument("--transparent", action="store_true")
    parser.add_argument("--vectors", action="store_true")
    parser.add_argument("--include-restricted", action="store_true",
                        help="include CC-BY-NC and CC-BY-SA results")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--per-page", type=int, default=20)
    args = parser.parse_args(argv)

    config = Config.load()
    http = CachedHttp(ResponseCache(config.library_dir / ".cache" / "responses.db"))
    registry = build_registry(http, config)
    outcome = registry.search(
        SearchQuery(
            text=args.query,
            page=args.page,
            per_page=args.per_page,
            transparent_only=args.transparent,
            vectors_only=args.vectors,
            commercial_safe_only=not args.include_restricted,
        )
    )
    print(format_results(outcome))
    return 0 if outcome.results else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_cli.py -q`
Expected: PASS, 5 tests

- [ ] **Step 5: Run the supply test against live APIs**

Ten real queries from a past project. Example shape:

```bash
.venv/Scripts/python.exe -m resolvestock.cli "smoke plume" --transparent
.venv/Scripts/python.exe -m resolvestock.cli "arrow icon" --vectors
```

Count results that are actually usable. Write the tally into `docs/spec.md`
§11 replacing "still unmeasured". **If usable hits are under roughly 3 in 10
across the ten queries, stop and revisit scope with the author before Task 9.**

- [ ] **Step 6: Commit**

```bash
git add resolvestock/cli.py tests/test_cli.py docs/spec.md
git commit -m "feat: terminal search CLI, record usable-hit-rate measurement"
```

---

### Task 9: Library — download, filename normalization, provenance

**Files:**
- Create: `resolvestock/library.py`
- Test: `tests/test_library.py`

**Interfaces:**
- Consumes: `SearchResult`, `LibraryItem`.
- Produces: `Library(root: Path, client: httpx.Client | None = None)` with `download(result: SearchResult) -> LibraryItem`, `items() -> list[LibraryItem]`, `normalize_filename(result: SearchResult, suffix: str) -> str`, `sidecar_path(path: Path) -> Path`.

Filenames matter more than they look. Resolve's Fairlight Sound Library and
its media pool both index on filename, so `impact_metal_heavy_01.wav` is
searchable where `123456__user__hit.wav` is not.

Provenance is written to a JSON sidecar so it survives the app being
uninstalled.

- [ ] **Step 1: Write the failing test**

`tests/test_library.py`:

```python
import json

import httpx
import pytest

from resolvestock.library import Library
from resolvestock.models import SearchResult


def make_result(title="Smoke Plume, Dark!", url="https://example.invalid/a.png",
                source="openverse", source_id="42"):
    return SearchResult(
        source=source,
        source_id=source_id,
        title=title,
        preview_url="https://example.invalid/p.png",
        download_url=url,
        media_type="image",
        width=1920,
        height=1080,
        has_alpha=True,
        license_id="cc-by",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        attribution="Smoke Plume by Jane (Openverse)",
        source_page_url="https://example.invalid/page",
    )


def make_library(tmp_path, body=b"PNGDATA", status=200):
    def handler(request):
        return httpx.Response(status, content=body)

    return Library(tmp_path / "lib", httpx.Client(transport=httpx.MockTransport(handler)))


def test_download_writes_the_file(tmp_path):
    item = make_library(tmp_path).download(make_result())
    assert item.local_path.exists()
    assert item.local_path.read_bytes() == b"PNGDATA"


def test_filename_is_normalized(tmp_path):
    item = make_library(tmp_path).download(make_result())
    assert item.local_path.name == "smoke_plume_dark_openverse_42.png"


def test_filename_keeps_the_source_extension(tmp_path):
    item = make_library(tmp_path).download(
        make_result(url="https://example.invalid/a.svg")
    )
    assert item.local_path.suffix == ".svg"


def test_untitled_result_still_gets_a_usable_name(tmp_path):
    item = make_library(tmp_path).download(make_result(title="   "))
    assert item.local_path.name == "untitled_openverse_42.png"


def test_provenance_sidecar_is_written(tmp_path):
    library = make_library(tmp_path)
    item = library.download(make_result())
    sidecar = library.sidecar_path(item.local_path)
    assert sidecar.exists()
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["license_id"] == "cc-by"
    assert data["attribution"] == "Smoke Plume by Jane (Openverse)"
    assert data["source_page_url"] == "https://example.invalid/page"
    assert data["downloaded_at"]


def test_redownloading_the_same_asset_does_not_duplicate(tmp_path):
    library = make_library(tmp_path)
    first = library.download(make_result())
    second = library.download(make_result())
    assert first.local_path == second.local_path
    assert len(list(library.root.glob("*.png"))) == 1


def test_items_reads_back_provenance(tmp_path):
    library = make_library(tmp_path)
    library.download(make_result())
    items = library.items()
    assert len(items) == 1
    assert items[0].result.license_id == "cc-by"
    assert items[0].result.title == "Smoke Plume, Dark!"


def test_failed_download_raises_and_leaves_no_partial_file(tmp_path):
    library = make_library(tmp_path, status=404)
    with pytest.raises(httpx.HTTPStatusError):
        library.download(make_result())
    assert list(library.root.glob("*.png")) == []


def test_orphan_file_without_sidecar_is_skipped_by_items(tmp_path):
    library = make_library(tmp_path)
    library.root.mkdir(parents=True, exist_ok=True)
    (library.root / "stray.png").write_bytes(b"x")
    assert library.items() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_library.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'resolvestock.library'`

- [ ] **Step 3: Write the implementation**

`resolvestock/library.py`:

```python
"""Local asset library: download, naming, and provenance.

Two decisions worth keeping:

  Filenames are normalized because Resolve indexes on them. A downloaded
  asset named 123456__user__hit.png is invisible to the media pool's search;
  smoke_plume_dark_openverse_42.png is not.

  Provenance goes in a JSON sidecar next to the file, not only in a database,
  so the license record survives this app being uninstalled.
"""

from __future__ import annotations

import dataclasses
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

from resolvestock.models import LibraryItem, SearchResult
from resolvestock.sources.base import USER_AGENT

SIDECAR_SUFFIX = ".provenance.json"
UNSAFE_CHARS = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_length: int = 48) -> str:
    slug = UNSAFE_CHARS.sub("_", text.strip().lower()).strip("_")
    return slug[:max_length].rstrip("_")


class Library:
    def __init__(self, root: Path, client: httpx.Client | None = None):
        self.root = Path(root)
        self.client = client or httpx.Client(
            timeout=60.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        )

    def normalize_filename(self, result: SearchResult, suffix: str) -> str:
        stem = slugify(result.title) or "untitled"
        return f"{stem}_{result.source}_{result.source_id}{suffix}"

    def sidecar_path(self, path: Path) -> Path:
        return path.with_suffix(path.suffix + SIDECAR_SUFFIX)

    def _suffix_for(self, result: SearchResult) -> str:
        suffix = Path(urlparse(result.download_url).path).suffix.lower()
        return suffix if suffix else ".bin"

    def download(self, result: SearchResult) -> LibraryItem:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / self.normalize_filename(result, self._suffix_for(result))

        if target.exists() and self.sidecar_path(target).exists():
            return self._read_item(target)

        response = self.client.get(result.download_url)
        response.raise_for_status()

        # Write to a temp name first so a failure never leaves a half file
        # that later looks like a valid asset.
        temporary = target.with_suffix(target.suffix + ".part")
        temporary.write_bytes(response.content)
        temporary.replace(target)

        downloaded_at = datetime.now(timezone.utc)
        record = dataclasses.asdict(result)
        record["downloaded_at"] = downloaded_at.isoformat()
        self.sidecar_path(target).write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )
        return LibraryItem(local_path=target, downloaded_at=downloaded_at, result=result)

    def _read_item(self, path: Path) -> LibraryItem:
        data = json.loads(self.sidecar_path(path).read_text(encoding="utf-8"))
        downloaded_at = datetime.fromisoformat(data.pop("downloaded_at"))
        return LibraryItem(
            local_path=path, downloaded_at=downloaded_at, result=SearchResult(**data)
        )

    def items(self) -> list[LibraryItem]:
        if not self.root.exists():
            return []
        found = []
        for sidecar in sorted(self.root.glob(f"*{SIDECAR_SUFFIX}")):
            asset = Path(str(sidecar)[: -len(SIDECAR_SUFFIX)])
            if asset.exists():
                found.append(self._read_item(asset))
        return found
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_library.py -q`
Expected: PASS, 9 tests

- [ ] **Step 5: Commit**

```bash
git add resolvestock/library.py tests/test_library.py
git commit -m "feat: library download with filename normalization and provenance sidecars"
```

---

### Task 10: Credits export

**Files:**
- Create: `resolvestock/credits.py`
- Test: `tests/test_credits.py`

**Interfaces:**
- Consumes: `LibraryItem` from Task 9, `get_license` from Task 1.
- Produces: `build_credits(items: Iterable[LibraryItem]) -> str`, `write_credits(items, path: Path) -> Path`.

Spec §8.2 requires attribution to be exportable as a credits list. This is
the deliverable a commercial editor actually needs and no free aggregator
provides.

- [ ] **Step 1: Write the failing test**

`tests/test_credits.py`:

```python
from datetime import datetime, timezone

from resolvestock.credits import build_credits, write_credits
from resolvestock.models import LibraryItem, SearchResult


def make_item(license_id="cc-by", attribution="Smoke by Jane (Openverse)", name="a.png"):
    result = SearchResult(
        source="openverse",
        source_id="1",
        title="Smoke",
        preview_url="https://example.invalid/p.png",
        download_url="https://example.invalid/d.png",
        media_type="image",
        width=10,
        height=10,
        has_alpha=True,
        license_id=license_id,
        license_url="https://creativecommons.org/licenses/by/4.0/",
        attribution=attribution,
        source_page_url="https://example.invalid/page",
    )
    from pathlib import Path

    return LibraryItem(Path(name), datetime.now(timezone.utc), result)


def test_credits_include_attribution_and_license_name():
    text = build_credits([make_item()])
    assert "Smoke by Jane (Openverse)" in text
    assert "CC BY 4.0" in text


def test_credits_include_the_source_page_link():
    assert "https://example.invalid/page" in build_credits([make_item()])


def test_items_not_requiring_attribution_are_omitted():
    # CC0 and the Pixabay license require no credit; listing them adds noise.
    text = build_credits([make_item(license_id="cc0"), make_item(license_id="cc-by")])
    assert text.count("Smoke by Jane") == 1


def test_duplicate_attributions_appear_once():
    text = build_credits([make_item(), make_item(name="b.png")])
    assert text.count("Smoke by Jane (Openverse)") == 1


def test_empty_input_produces_a_clear_message():
    assert "no attribution required" in build_credits([]).lower()


def test_write_credits_creates_the_file(tmp_path):
    path = write_credits([make_item()], tmp_path / "CREDITS.txt")
    assert path.exists()
    assert "CC BY 4.0" in path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_credits.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'resolvestock.credits'`

- [ ] **Step 3: Write the implementation**

`resolvestock/credits.py`:

```python
"""Credits export.

Only licenses that actually require attribution are listed. Padding the list
with CC0 and Pixabay items would train the user to ignore it, which defeats
the point.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from resolvestock.licenses import get_license
from resolvestock.models import LibraryItem

HEADER = "Credits\n=======\n"
NOTHING_REQUIRED = "No attribution required for the assets in this library."


def build_credits(items: Iterable[LibraryItem]) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for item in items:
        meta = get_license(item.result.license_id)
        if not meta.requires_attribution:
            continue
        if item.result.attribution in seen:
            continue
        seen.add(item.result.attribution)
        lines.append(
            f"- {item.result.attribution}\n"
            f"  {meta.name} - {item.result.license_url}\n"
            f"  {item.result.source_page_url}"
        )
    if not lines:
        return f"{HEADER}\n{NOTHING_REQUIRED}\n"
    return f"{HEADER}\n" + "\n".join(lines) + "\n"


def write_credits(items: Iterable[LibraryItem], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_credits(items), encoding="utf-8")
    return path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_credits.py -q`
Expected: PASS, 6 tests

- [ ] **Step 5: Commit**

```bash
git add resolvestock/credits.py tests/test_credits.py
git commit -m "feat: credits export for assets requiring attribution"
```

---

### Task 11: Library tray — the drag source into Resolve

**Files:**
- Create: `resolvestock/ui/__init__.py`, `resolvestock/ui/tray.py`
- Delete: `prototype_drag.py`
- Test: `tests/test_ui_tray.py`

**Interfaces:**
- Consumes: `LibraryItem` from Task 9.
- Produces: `LibraryTray(QListWidget)` with `set_items(items: list[LibraryItem]) -> None`, `selected_paths() -> list[Path]`, `mimeData(items) -> QMimeData`.

This ports the verified drag behavior out of `prototype_drag.py`. The
prototype already proved Resolve accepts a Qt-originated `CF_HDROP` payload;
this task makes it a real component and deletes the prototype.

Qt tests run headless with `QT_QPA_PLATFORM=offscreen`.

- [ ] **Step 1: Write the failing test**

`tests/test_ui_tray.py`:

```python
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from resolvestock.models import LibraryItem, SearchResult  # noqa: E402
from resolvestock.ui.tray import LibraryTray  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def make_item(tmp_path, name="a.png", license_id="cc-by"):
    path = tmp_path / name
    path.write_bytes(b"x")
    result = SearchResult(
        source="openverse",
        source_id=name,
        title="Smoke",
        preview_url="https://example.invalid/p.png",
        download_url="https://example.invalid/d.png",
        media_type="image",
        width=10,
        height=10,
        has_alpha=True,
        license_id=license_id,
        license_url="https://example.invalid/l",
        attribution="Smoke by Jane (Openverse)",
        source_page_url="https://example.invalid/page",
    )
    return LibraryItem(path, datetime.now(timezone.utc), result)


def test_set_items_populates_the_tray(app, tmp_path):
    tray = LibraryTray()
    tray.set_items([make_item(tmp_path, "a.png"), make_item(tmp_path, "b.png")])
    assert tray.count() == 2


def test_mime_data_carries_file_urls(app, tmp_path):
    tray = LibraryTray()
    item = make_item(tmp_path, "a.png")
    tray.set_items([item])
    tray.selectAll()
    mime = tray.mimeData(tray.selectedItems())
    assert mime.hasUrls()
    assert Path(mime.urls()[0].toLocalFile()) == item.local_path


def test_multi_select_drag_carries_every_path(app, tmp_path):
    tray = LibraryTray()
    tray.set_items([make_item(tmp_path, "a.png"), make_item(tmp_path, "b.png")])
    tray.selectAll()
    urls = tray.mimeData(tray.selectedItems()).urls()
    assert len(urls) == 2


def test_tooltip_shows_license_and_attribution(app, tmp_path):
    tray = LibraryTray()
    tray.set_items([make_item(tmp_path, "a.png")])
    tooltip = tray.item(0).toolTip()
    assert "Smoke by Jane (Openverse)" in tooltip
    assert "CC BY 4.0" in tooltip


def test_set_items_replaces_previous_contents(app, tmp_path):
    tray = LibraryTray()
    tray.set_items([make_item(tmp_path, "a.png")])
    tray.set_items([make_item(tmp_path, "b.png")])
    assert tray.count() == 1


def test_selected_paths_returns_local_paths(app, tmp_path):
    tray = LibraryTray()
    item = make_item(tmp_path, "a.png")
    tray.set_items([item])
    tray.selectAll()
    assert tray.selected_paths() == [item.local_path]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ui_tray.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'resolvestock.ui'`

- [ ] **Step 3: Write the implementation**

`resolvestock/ui/__init__.py` is empty.

`resolvestock/ui/tray.py`:

```python
"""Library tray - the drag source into DaVinci Resolve.

Resolve has no plugin surface on the free version, so integration is a
native OS drag carrying file:// URLs. QMimeData.setUrls produces the same
CF_HDROP payload Explorer sends, which Resolve accepts. Verified against
Resolve free before this component was written.

Drags are CopyAction only. A MoveAction would permit the drop target to
delete the source file out of the user's library.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData, QSize, Qt, QUrl
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QStyle

from resolvestock.licenses import get_license
from resolvestock.models import LibraryItem

RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


class LibraryTray(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QSize(120, 90))
        self.setGridSize(QSize(140, 130))
        self.setResizeMode(QListWidget.Adjust)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(False)
        self.setDropIndicatorShown(False)

    def set_items(self, items: list[LibraryItem]) -> None:
        self.clear()
        placeholder = self.style().standardIcon(QStyle.SP_FileIcon)
        for item in items:
            entry = QListWidgetItem(item.local_path.name)
            entry.setData(Qt.UserRole, str(item.local_path))
            entry.setToolTip(self._tooltip(item))
            if item.local_path.suffix.lower() in RASTER_SUFFIXES:
                pixmap = QPixmap(str(item.local_path))
                entry.setIcon(QIcon(pixmap) if not pixmap.isNull() else placeholder)
            else:
                entry.setIcon(placeholder)
            self.addItem(entry)

    def _tooltip(self, item: LibraryItem) -> str:
        meta = get_license(item.result.license_id)
        return (
            f"{item.result.attribution}\n"
            f"{meta.name}\n"
            f"{item.result.source_page_url}"
        )

    def selected_paths(self) -> list[Path]:
        return [Path(entry.data(Qt.UserRole)) for entry in self.selectedItems()]

    def mimeData(self, items) -> QMimeData:
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(entry.data(Qt.UserRole)) for entry in items])
        return data

    def startDrag(self, supportedActions) -> None:
        super().startDrag(Qt.CopyAction)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ui_tray.py -q`
Expected: PASS, 6 tests

- [ ] **Step 5: Delete the prototype and commit**

The prototype's only job was answering whether Resolve accepts a Qt drag. It
does. The behavior now lives in `ui/tray.py`.

```bash
rm prototype_drag.py
git add resolvestock/ui/ tests/test_ui_tray.py
git rm --cached prototype_drag.py 2>/dev/null || true
git add -A
git commit -m "feat: library tray with verified drag-to-Resolve, drop prototype"
```

---

### Task 12: Results grid with async thumbnails

**Files:**
- Create: `resolvestock/ui/grid.py`
- Test: `tests/test_ui_grid.py`

**Interfaces:**
- Consumes: `SearchResult` from Task 1.
- Produces: `ResultsGrid(QListWidget)` with `set_results(results: list[SearchResult]) -> None`, `results() -> list[SearchResult]`, signal `download_requested = Signal(object)`; and `ThumbnailLoader(QObject)` with `load(url: str, callback) -> None`.

The grid holds **remote** results with no local file, so it is not a drag
source. Clicking an item requests a download; the file then appears in the
tray, which is where dragging happens. This is the two-step flow the spec
requires — a drag needs a path that already exists on disk.

- [ ] **Step 1: Write the failing test**

`tests/test_ui_grid.py`:

```python
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from resolvestock.models import SearchResult  # noqa: E402
from resolvestock.ui.grid import ResultsGrid  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def make_result(source_id="1", title="Smoke", license_id="cc-by"):
    return SearchResult(
        source="openverse",
        source_id=source_id,
        title=title,
        preview_url="https://example.invalid/p.png",
        download_url="https://example.invalid/d.png",
        media_type="image",
        width=1920,
        height=1080,
        has_alpha=True,
        license_id=license_id,
        license_url="https://example.invalid/l",
        attribution="Smoke by Jane (Openverse)",
        source_page_url="https://example.invalid/page",
    )


def test_set_results_populates_the_grid(app):
    grid = ResultsGrid()
    grid.set_results([make_result("1"), make_result("2")])
    assert grid.count() == 2


def test_results_round_trip(app):
    grid = ResultsGrid()
    results = [make_result("1")]
    grid.set_results(results)
    assert grid.results()[0].uid == "openverse:1"


def test_item_label_shows_title_and_source(app):
    grid = ResultsGrid()
    grid.set_results([make_result()])
    assert "Smoke" in grid.item(0).text()
    assert "openverse" in grid.item(0).text()


def test_tooltip_shows_license_and_dimensions(app):
    grid = ResultsGrid()
    grid.set_results([make_result()])
    tooltip = grid.item(0).toolTip()
    assert "CC BY 4.0" in tooltip
    assert "1920x1080" in tooltip


def test_double_click_emits_download_requested(app):
    grid = ResultsGrid()
    result = make_result()
    grid.set_results([result])
    received = []
    grid.download_requested.connect(received.append)
    grid.itemDoubleClicked.emit(grid.item(0))
    assert received == [result]


def test_grid_is_not_a_drag_source(app):
    # Remote results have no local file. Dragging happens from the tray.
    grid = ResultsGrid()
    assert grid.dragEnabled() is False


def test_set_results_replaces_previous_contents(app):
    grid = ResultsGrid()
    grid.set_results([make_result("1")])
    grid.set_results([make_result("2")])
    assert grid.count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ui_grid.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'resolvestock.ui.grid'`

- [ ] **Step 3: Write the implementation**

`resolvestock/ui/grid.py`:

```python
"""Search results grid.

Deliberately NOT a drag source. These results are remote - there is no local
file to hand a drop target, and pre-downloading every result to enable
dragging would violate Pixabay's ban on systematic mass downloads. Double
click downloads; the result then appears in the tray, which is draggable.

Thumbnails load on a QThreadPool so the UI never blocks on the network.
"""

from __future__ import annotations

import httpx
from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QStyle

from resolvestock.licenses import get_license
from resolvestock.models import SearchResult
from resolvestock.sources.base import USER_AGENT


class _ThumbnailSignals(QObject):
    loaded = Signal(str, bytes)
    failed = Signal(str, str)


class _ThumbnailJob(QRunnable):
    def __init__(self, url: str, signals: _ThumbnailSignals):
        super().__init__()
        self.url = url
        self.signals = signals

    def run(self) -> None:
        try:
            response = httpx.get(
                self.url, timeout=15.0, follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            self.signals.loaded.emit(self.url, response.content)
        except Exception as error:  # noqa: BLE001 - a missing thumb is cosmetic
            self.signals.failed.emit(self.url, str(error))


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

        self._results: dict[str, SearchResult] = {}
        self._items_by_url: dict[str, QListWidgetItem] = {}
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
            entry.setToolTip(self._tooltip(result))
            entry.setIcon(placeholder)
            self.addItem(entry)
            self._results[result.uid] = result
            if result.preview_url:
                self._items_by_url[result.preview_url] = entry
                self.loader.load(result.preview_url)

    def results(self) -> list[SearchResult]:
        return [self._results[self.item(i).data(Qt.UserRole)] for i in range(self.count())]

    def _tooltip(self, result: SearchResult) -> str:
        meta = get_license(result.license_id)
        size = (
            f"{result.width}x{result.height}"
            if result.width and result.height
            else "size unknown"
        )
        return (
            f"{result.title}\n{size}\n{meta.name}\n"
            f"alpha={result.has_alpha}\n{result.source_page_url}"
        )

    def _apply_thumbnail(self, url: str, data: bytes) -> None:
        entry = self._items_by_url.get(url)
        if entry is None:
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            entry.setIcon(QIcon(pixmap))

    def _emit_download(self, entry: QListWidgetItem) -> None:
        result = self._results.get(entry.data(Qt.UserRole))
        if result is not None:
            self.download_requested.emit(result)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ui_grid.py -q`
Expected: PASS, 7 tests

- [ ] **Step 5: Commit**

```bash
git add resolvestock/ui/grid.py tests/test_ui_grid.py
git commit -m "feat: results grid with async thumbnail loading"
```

---

### Task 13: Main window — search, filters, wiring

**Files:**
- Create: `resolvestock/ui/main_window.py`, `resolvestock/ui/app.py`
- Test: `tests/test_ui_main_window.py`

**Interfaces:**
- Consumes: `ResultsGrid` (Task 12), `LibraryTray` (Task 11), `SourceRegistry` (Task 7), `Library` (Task 9), `write_credits` (Task 10), `Config` (Task 6).
- Produces: `MainWindow(registry, library, config)` with `build_query() -> SearchQuery`, `run_search() -> None`, `download(result) -> None`, `refresh_tray() -> None`, `export_credits(path) -> Path`; `main(argv=None) -> int`.

Search runs on a worker thread. Tests drive the window's methods directly
with a fake registry, so no network and no event-loop timing.

- [ ] **Step 1: Write the failing test**

`tests/test_ui_main_window.py`:

```python
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from resolvestock.config import Config  # noqa: E402
from resolvestock.models import LibraryItem, SearchResult  # noqa: E402
from resolvestock.sources.registry import SearchOutcome  # noqa: E402
from resolvestock.ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def make_result(source_id="1", license_id="cc-by"):
    return SearchResult(
        source="openverse",
        source_id=source_id,
        title="Smoke",
        preview_url="",
        download_url="https://example.invalid/d.png",
        media_type="image",
        width=10,
        height=10,
        has_alpha=True,
        license_id=license_id,
        license_url="https://example.invalid/l",
        attribution="Smoke by Jane (Openverse)",
        source_page_url="https://example.invalid/page",
    )


class FakeRegistry:
    def __init__(self, outcome=None):
        self.outcome = outcome or SearchOutcome(results=[make_result()])
        self.queries = []

    def search(self, query):
        self.queries.append(query)
        return self.outcome


class FakeLibrary:
    def __init__(self, root):
        self.root = Path(root)
        self.downloaded = []

    def download(self, result):
        path = self.root / f"{result.source_id}.png"
        self.root.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
        item = LibraryItem(path, datetime.now(timezone.utc), result)
        self.downloaded.append(item)
        return item

    def items(self):
        return list(self.downloaded)


def make_window(app, tmp_path, registry=None):
    config = Config.load(tmp_path / "config.json")
    config.library_dir = tmp_path / "lib"
    return MainWindow(registry or FakeRegistry(), FakeLibrary(config.library_dir), config)


def test_commercial_safe_filter_defaults_to_checked(app, tmp_path):
    window = make_window(app, tmp_path)
    assert window.commercial_safe_checkbox.isChecked() is True


def test_build_query_reflects_the_filter_checkboxes(app, tmp_path):
    window = make_window(app, tmp_path)
    window.search_input.setText("smoke")
    window.transparent_checkbox.setChecked(True)
    window.vectors_checkbox.setChecked(True)
    query = window.build_query()
    assert query.text == "smoke"
    assert query.transparent_only is True
    assert query.vectors_only is True
    assert query.commercial_safe_only is True


def test_run_search_populates_the_grid(app, tmp_path):
    registry = FakeRegistry()
    window = make_window(app, tmp_path, registry)
    window.search_input.setText("smoke")
    window.run_search()
    assert window.grid.count() == 1
    assert registry.queries[0].text == "smoke"


def test_source_errors_are_shown_in_the_status_bar(app, tmp_path):
    registry = FakeRegistry(SearchOutcome(results=[], errors={"pixabay": "429"}))
    window = make_window(app, tmp_path, registry)
    window.search_input.setText("smoke")
    window.run_search()
    assert "pixabay" in window.status_label.text()


def test_download_adds_the_item_to_the_tray(app, tmp_path):
    window = make_window(app, tmp_path)
    window.download(make_result(), threaded=False)
    assert window.tray.count() == 1


def test_empty_search_text_does_not_call_the_registry(app, tmp_path):
    registry = FakeRegistry()
    window = make_window(app, tmp_path, registry)
    window.search_input.setText("   ")
    window.run_search()
    assert registry.queries == []


def test_export_credits_writes_a_file(app, tmp_path):
    window = make_window(app, tmp_path)
    window.download(make_result(), threaded=False)
    path = window.export_credits(tmp_path / "CREDITS.txt")
    assert path.exists()
    assert "Smoke by Jane (Openverse)" in path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ui_main_window.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'resolvestock.ui.main_window'`

- [ ] **Step 3: Write the implementation**

`resolvestock/ui/main_window.py`:

```python
"""Main window: search bar, filters, results grid, library tray.

Flow, and the reason for it: results are remote, so they cannot be dragged.
Double clicking a result downloads it into the library; the file then shows
in the tray, and the tray is what drags into Resolve.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from resolvestock.credits import write_credits
from resolvestock.sources.base import SearchQuery
from resolvestock.ui.grid import ResultsGrid
from resolvestock.ui.tray import LibraryTray


class _DownloadSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class _DownloadJob(QRunnable):
    def __init__(self, library, result, signals: _DownloadSignals):
        super().__init__()
        self.library = library
        self.result = result
        self.signals = signals

    def run(self) -> None:
        try:
            self.signals.finished.emit(self.library.download(self.result))
        except Exception as error:  # noqa: BLE001 - surfaced in the status bar
            self.signals.failed.emit(str(error))


class MainWindow(QMainWindow):
    def __init__(self, registry, library, config, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.library = library
        self.config = config
        self.pool = QThreadPool.globalInstance()

        self.setWindowTitle("resolvestock")
        self.resize(1100, 760)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("search cutouts and vectors")
        self.search_input.returnPressed.connect(self.run_search)
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.run_search)

        self.transparent_checkbox = QCheckBox("Transparent only")
        self.vectors_checkbox = QCheckBox("Vectors only")
        self.commercial_safe_checkbox = QCheckBox("Commercial-safe only")
        self.commercial_safe_checkbox.setChecked(True)
        self.commercial_safe_checkbox.setToolTip(
            "Excludes CC BY-NC and CC BY-SA. Leave on for commercial work."
        )

        self.credits_button = QPushButton("Export credits")
        self.credits_button.clicked.connect(self._prompt_export_credits)

        self.grid = ResultsGrid()
        self.grid.download_requested.connect(self.download)
        self.tray = LibraryTray()
        self.status_label = QLabel("ready")
        self.status_label.setWordWrap(True)

        controls = QHBoxLayout()
        controls.addWidget(self.search_input, stretch=1)
        controls.addWidget(self.search_button)

        filters = QHBoxLayout()
        filters.addWidget(self.transparent_checkbox)
        filters.addWidget(self.vectors_checkbox)
        filters.addWidget(self.commercial_safe_checkbox)
        filters.addStretch(1)
        filters.addWidget(self.credits_button)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.grid)
        splitter.addWidget(self.tray)
        splitter.setSizes([520, 240])

        layout = QVBoxLayout()
        layout.addLayout(controls)
        layout.addLayout(filters)
        layout.addWidget(QLabel("Results - double click to download"))
        layout.addWidget(splitter, stretch=1)
        layout.addWidget(QLabel("Library - drag into Resolve's media pool"))
        layout.addWidget(self.status_label)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.refresh_tray()

    def build_query(self) -> SearchQuery:
        return SearchQuery(
            text=self.search_input.text().strip(),
            transparent_only=self.transparent_checkbox.isChecked(),
            vectors_only=self.vectors_checkbox.isChecked(),
            commercial_safe_only=self.commercial_safe_checkbox.isChecked(),
        )

    def run_search(self) -> None:
        query = self.build_query()
        if not query.text:
            self.status_label.setText("enter a search term")
            return
        self.status_label.setText(f"searching for {query.text}...")
        outcome = self.registry.search(query)
        self.grid.set_results(outcome.results)
        message = f"{len(outcome.results)} result(s)"
        if outcome.errors:
            failures = "; ".join(f"{k}: {v}" for k, v in outcome.errors.items())
            message = f"{message} - some sources failed - {failures}"
        self.status_label.setText(message)

    def download(self, result, threaded: bool = True) -> None:
        """Download an asset into the library.

        `threaded=False` runs inline. Tests use it so the assertion does not
        race a thread pool; the UI always uses the default.
        """
        self.status_label.setText(f"downloading {result.title}...")
        signals = _DownloadSignals()
        signals.finished.connect(self._on_download_finished)
        signals.failed.connect(lambda msg: self.status_label.setText(f"failed: {msg}"))
        job = _DownloadJob(self.library, result, signals)
        if threaded:
            self.pool.start(job)
        else:
            job.run()

    def _on_download_finished(self, item) -> None:
        self.refresh_tray()
        self.status_label.setText(f"saved {item.local_path.name}")

    def refresh_tray(self) -> None:
        self.tray.set_items(self.library.items())

    def export_credits(self, path: Path) -> Path:
        return write_credits(self.library.items(), Path(path))

    def _prompt_export_credits(self) -> None:
        chosen, _ = QFileDialog.getSaveFileName(
            self, "Export credits", "CREDITS.txt", "Text files (*.txt)"
        )
        if chosen:
            self.export_credits(Path(chosen))
            self.status_label.setText(f"credits written to {chosen}")
```

`resolvestock/ui/app.py`:

```python
"""Entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from resolvestock.cache import ResponseCache
from resolvestock.config import Config
from resolvestock.library import Library
from resolvestock.sources.base import CachedHttp
from resolvestock.sources.registry import build_registry
from resolvestock.ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    config = Config.load()
    http = CachedHttp(ResponseCache(config.library_dir / ".cache" / "responses.db"))
    window = MainWindow(build_registry(http, config), Library(config.library_dir), config)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ui_main_window.py -q`
Expected: PASS, 7 tests

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS, all tests

- [ ] **Step 6: Commit**

```bash
git add resolvestock/ui/main_window.py resolvestock/ui/app.py tests/test_ui_main_window.py
git commit -m "feat: main window wiring search, filters, downloads, and credits export"
```

---

### Task 14: End-to-end verification against real Resolve

**Files:**
- Modify: `docs/spec.md` (§11 open questions)

No code. This is the gate that proves the product works, and it needs hands
on the actual application.

- [ ] **Step 1: Launch the app against live APIs**

```bash
.venv/Scripts/python.exe -m resolvestock.ui.app
```

- [ ] **Step 2: Run the full loop**

1. Search a real term from a past project, with **Transparent only** checked
2. Confirm thumbnails load and license text appears in tooltips
3. Double click to download; confirm the item appears in the tray
4. Open DaVinci Resolve (free), load a project, Media page
5. Drag one tray item onto the **media pool** — confirm it lands
6. Drag one tray item onto the **timeline** — record whether it lands
7. Ctrl-click three tray items, drag together — record whether all three land
8. Confirm the downloaded folder holds both the asset and its
   `.provenance.json` sidecar
9. Click **Export credits**; confirm only attribution-requiring items appear

- [ ] **Step 3: Record the results**

Update `docs/spec.md` §11:
- Replace "usable-hit rate is still unmeasured" with the measured tally
- Replace "multi-file drag and timeline-drop" with the confirmed behavior
- Note whether `colors=transparent` returned useful vector results

- [ ] **Step 4: Commit**

```bash
git add docs/spec.md
git commit -m "docs: record end-to-end verification results against Resolve free"
```

---

### Task 15: README, packaging, and the demo GIF

**Files:**
- Create: `README.md`
- Modify: `pyproject.toml`

Spec §12 makes GitHub stars a success criterion, which makes the README and
demo a deliverable rather than an afterthought. A repo with no demo GIF gets
no stars regardless of code quality.

- [ ] **Step 1: Record a demo GIF**

Capture the loop: type a search, thumbnails appear, double click to download,
drag from the tray into Resolve's media pool, clip lands. Keep it under 15
seconds. Save as `docs/demo.gif`.

- [ ] **Step 2: Write the README**

`README.md`:

````markdown
# resolvestock

Search free stock cutouts and vectors, and drag them straight into DaVinci
Resolve's media pool. Works on the **free** version of Resolve.

![demo](docs/demo.gif)

## Why

Sourcing cutouts and vectors for motion graphics means leaving the editor,
opening a browser, searching several sites one at a time, and losing the
license record the moment the file hits a folder. This does all three in one
window, and keeps the provenance.

## Install

```bash
git clone <repo-url>
cd resolvestock
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e .
.venv/Scripts/python.exe -m resolvestock.ui.app
```

Requires Python 3.11+.

## Sources

| Source | API key | Notes |
|---|---|---|
| Openverse | not needed | Works on first launch |
| Wikimedia Commons | not needed | Best supply of true-alpha PNG and SVG |
| Pixabay | free, instant signup | Adds server-side `transparent` and `vector` filters |

Paste a Pixabay key in the app to enable it. The app works without one.

## Licensing

Every result shows its license, and every download writes a
`.provenance.json` sidecar recording the source, license, and attribution.

**Commercial-safe filtering is on by default.** It excludes CC BY-NC (bans
commercial use) and CC BY-SA (your adapted work may inherit the ShareAlike
obligation). Turn it off only if you know why you are doing so.

Use **Export credits** to produce an attribution list for a project. Only
licenses that actually require credit are listed.

## DaVinci Resolve integration

Free Resolve has no plugin surface — Workflow Integration panels and external
scripting are Studio-only. So this is a standalone app that integrates via
native drag-and-drop, which works on every Resolve version and cannot break
when Resolve updates.

Downloads also land in a normal folder, so they work with Resolve's Media
Storage tab and PowerBins.

## Development

```bash
.venv/Scripts/python.exe -m pip install -e ".[dev]"
.venv/Scripts/python.exe -m pytest -q
```

Tests never hit the network; adapters are tested against captured fixtures.
````

- [ ] **Step 3: Verify a clean install works**

```bash
.venv/Scripts/python.exe -m pip install -e .
.venv/Scripts/python.exe -m resolvestock.ui.app
```

Expected: window opens, a search returns results with no config file present.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/demo.gif pyproject.toml
git commit -m "docs: README with demo GIF, install, and licensing notes"
```

---

## Deferred — not in this plan

From spec §10, explicitly out of scope here:

- Vecteezy adapter — key requires an application
- Anti-sameness ranking (deep pages, exclude-already-used)
- Keyable video, pending the supply test in spec §11
- Sound effects, pending Freesound OAuth2
- Studio Workflow Integration panel
- ffmpeg metadata writing — only matters once audio ships

## Repository rename

Spec §13: the directory is named `davinci-resolve-plugin` and this is not a
plugin. Rename before the first public push. The Python package is already
`resolvestock`, so only the directory and remote need changing.
