# Stock Asset Sourcing App — Specification

**Status:** v1 scope locked
**Date:** 2026-07-28
**Author:** Ryan

---

## 1. Problem

Motion graphics and video-essay work needs a constant supply of source
material — cutout images, vectors, and clips that get cut apart, keyed, and
composited rather than dropped on a timeline as-is. Sourcing that material
today means leaving the editor, opening a browser, searching several stock
sites one at a time, evaluating results by eye, downloading, and dragging the
file back in. This happens 15–20 times per project.

Two costs:

- **Context switching.** Every hunt breaks editing flow.
- **Memory pressure.** A browser competing with DaVinci Resolve on a low-end
  machine degrades playback.

A third cost is invisible until it matters: once a file lands in a folder, its
source, license, and attribution requirement are gone. For work that is cut up
and republished commercially, that is a liability.

## 2. Target user

**Primary:** video essayists and motion graphics editors who use stock as raw
compositing material — cutouts, vectors, elements — not as finished B-roll.

**Secondary:** documentary editors sourcing generic B-roll.

Both are assumed to be on **free DaVinci Resolve**. Paid stock subscriptions
are assumed absent.

## 3. What this is not

Explicitly out of scope, with reasons, so these don't get re-litigated:

| Cut | Reason |
|---|---|
| DaVinci Resolve plugin or panel | Workflow Integration Plugins and external scripting are **Studio-only**. Free Resolve has no plugin surface. |
| Keyable / pre-keyed VFX elements (v1) | The sites holding this content — Videezy, Mixkit, ProductionCrate, ActionVFX, FX Elements — have no public APIs. ProductionCrate already ships its own Resolve plugin for this category. Revisit only after a supply test against Pixabay and Vecteezy. |
| Sound effects (v1) | Freesound originals require an OAuth2 flow. Deferred by choice. |
| FCPXML batch import | PowerBins already provide cross-project reuse with no code. |
| Paid or subscription stock sources | No budget, no revenue, and reselling access would violate source terms. |
| Any paid tier | The project is free. Success is measured in GitHub stars and the author's own workflow. |

## 4. Verified platform constraints

Confirmed 2026-07-28. These are facts, not assumptions.

| Capability | Free Resolve | Evidence |
|---|---|---|
| External Python scripting | **No** — Studio only; free runs scripts from the internal Console only | Blackmagic docs |
| Workflow Integration Plugins | **No** — Studio only | Resolve manual, "Workflow Integrations (Studio Version Only)" |
| PowerBins | **Yes** | Tested by author |
| Fairlight Sound Library | Adds a folder; indexed results not yet visible | Unresolved, see §11 |
| `File > Import` | Project formats only (`.drp`, `.drt`, zip). Timeline XML lives at Media Pool right-click → `Timelines > Import > AAF, EDL, XML...` | Tested by author |
| **Drag-and-drop from a Qt window into the media pool** | **Yes** | Tested by author with a native Qt file-URL drag |

The last row is the architecture. `QMimeData.setUrls` + `QDrag` produces the
same `CF_HDROP` shell payload Explorer sends, and Resolve accepts it. No
Resolve API is involved, so nothing breaks when Resolve updates.

## 5. Architecture

A **standalone PySide6 desktop application**. Not a plugin.

```
┌─────────────────────────────────────┐
│  Search bar + source/license filters │
├─────────────────────────────────────┤
│  Results grid (remote thumbnails)    │
│  click → download                    │
├─────────────────────────────────────┤
│  Library tray (local files)          │
│  drag → Resolve media pool           │
└─────────────────────────────────────┘
```

**The two-step flow is a hard constraint, not a preference.** A drag must hand
the drop target a path that already exists on disk. Downloading mid-drag is
impossible, and speculatively pre-downloading every result violates Pixabay's
ban on systematic mass downloads. So: click to download, then drag from the
library tray.

The library tray is one component doing three jobs — download queue, local
library, and drag source — and it is where license and attribution live.

**Layer separation:**

- `sources/` — one adapter per API, each normalizing to a common result type.
  Knows nothing about Qt.
- `cache/` — SQLite-backed response cache with 24h TTL.
- `library/` — download, filename normalization, metadata write, provenance
  records.
- `ui/` — PySide6. Knows nothing about HTTP.

The source layer is testable from a terminal with no UI, and is built first.

## 6. Tech stack

| Concern | Choice | Note |
|---|---|---|
| UI | **PySide6** | LGPL. Not PyQt6, which is GPL. |
| HTTP | `httpx` | Concurrent search across sources |
| Threading | `QThreadPool` | Network off the UI thread |
| Cache | `sqlite3` | Required by Pixabay terms |
| Metadata / thumbnails | `ffmpeg` subprocess | Python BWF/iXML writers are unreliable |
| Packaging | Nuitka or PyInstaller | Windows exe |
| Python | 3.11+ | 3.11.9 in use |

Rejected: **Tauri.** Smaller binary and lower RAM, but requires learning Rust
and a web stack for an unpaid side project. Wrong trade.

## 7. Sources — v1

| Source | Media | Key | Rate limit | Hard requirement |
|---|---|---|---|---|
| **Openverse** | images, audio (800M CC items) | **none** | higher with OAuth | Per-item license varies; must display it |
| **Wikimedia Commons** | alpha PNG, SVG | none | generous | Per-item license varies; attribution per item |
| **Pixabay** | photo, vector, video | instant signup | 100 req / 60s | **Responses must be cached 24h.** No permanent hotlinking. No systematic mass downloads. |
| **Vecteezy** | photo, video, SVG, PNG | application required | TBD | Added last — key approval is a blocker |

Build order is Openverse → Wikimedia → Pixabay → Vecteezy. The first two need
no key at all, so **first launch produces results before the user has pasted
anything.** That is deliberate: two account registrations before first value
would kill adoption.

**Pixabay filters that make this worth building:** `colors=transparent` and
`image_type=vector` are real server-side filters that Pixabay's own website
barely surfaces. Transparent-cutout search is the core v1 capability and it
exists at the API level.

**Deferred sources:** Pexels (weak for cutouts; requires a visible "provided by
Pexels" credit plus photographer link if used), Coverr (cinematic loops, wrong
category), Freesound (OAuth), Internet Archive (documentary lane).

## 8. Compliance — mandatory in v1

These are not polish. Each is a terms-of-service obligation or a legal
exposure, and each must ship in v1.

1. **24-hour response cache.** Pixabay requires it explicitly.
2. **Attribution display.** Shown in the library tray per item, exportable as a
   credits list per project.
3. **Per-item license.** Openverse and Wikimedia items carry different licenses
   per item. A single blanket license notice is wrong and unsafe.
4. **Commercial-safe filter, on by default.** Excludes `CC-BY-NC` (bans
   commercial use) and `CC-BY-SA` (adapted work may inherit the ShareAlike
   obligation). The user cuts assets up and republishes commercially, so both
   are real liabilities.
5. **No bulk-download feature.** A "download all results" button would violate
   Pixabay's terms. Downloads are one deliberate user action each.

Compliance work doubles as the product's differentiator: no free stock
aggregator tracks provenance, and provenance is what a commercial editor
actually needs.

## 9. Data model

```python
@dataclass(frozen=True)
class SearchResult:
    source: str            # "pixabay" | "openverse" | "wikimedia" | "vecteezy"
    source_id: str         # stable id within that source
    title: str
    preview_url: str       # small image for the grid
    download_url: str      # full-resolution asset
    media_type: str        # "image" | "vector" | "video"
    width: int | None
    height: int | None
    has_alpha: bool | None # True when the source guarantees transparency
    license_id: str        # "cc0" | "cc-by" | "cc-by-sa" | "cc-by-nc" | "pixabay"
    license_url: str
    attribution: str       # ready-to-paste credit line
    source_page_url: str   # link back, required by several sources
```

```python
@dataclass(frozen=True)
class LibraryItem:
    local_path: Path
    downloaded_at: datetime
    result: SearchResult    # full provenance retained
```

Provenance is written to a sidecar record alongside the file so it survives the
app being uninstalled.

## 10. Feature list — v1

**Must have:**

- Unified search across Openverse, Wikimedia, Pixabay
- Filter: transparent / alpha only
- Filter: media type (raster image, vector)
- Filter: commercial-safe (on by default)
- Results grid with remote thumbnails
- Click to download into a library folder
- Library tray, drag-to-Resolve from it
- Semantic filename normalization on download
- Per-item license and attribution display
- 24h response cache
- Credits export for a project

**Explicitly deferred to v1.5+:**

- Anti-sameness ranking — deep result pages, cross-source mixing, exclude
  assets already used in past projects. Real problem for video essayists, but
  not load-bearing for v1.
- Vecteezy adapter, pending key approval
- Keyable video, pending a supply test
- Sound effects, pending OAuth work
- Studio Workflow Integration panel, same engine underneath

## 11. Open questions

1. **Fairlight Sound Library indexing.** Author added a folder but saw no
   results. Panel is empty until a search term is typed; also check the
   database dropdown and that files are `wav`/`aiff`/`mp3` (Freesound previews
   are `ogg`, which would explain it). Blocks the SFX lane only.
2. **Usable-hit rate is still unmeasured.** The premise that free sources cover
   real needs has never been tested. **The first terminal run of the source
   adapter layer is the test:** 10 real queries from a past project, count
   usable results. No extra work, and it happens before any UI exists.
3. **Vecteezy API terms and rate limits** — unread until a key is approved.
4. **Multi-file drag and timeline-drop** — media pool drop is confirmed;
   dragging several files at once and dropping directly on the timeline are
   not.

## 12. Success criteria

- The author stops alt-tabbing to a browser during motion graphics work
- GitHub stars — which means a README with a demo GIF and one r/davinciresolve
  post are part of the deliverable, not an afterthought
- v1 is finishable in a small number of weekends. Scope creep is the primary
  risk to this project; §3 and §10 exist to contain it.

## 13. Repository note

The directory is named `davinci-resolve-plugin`. This is not a plugin and
cannot be one on free Resolve. Rename before the first public commit.
