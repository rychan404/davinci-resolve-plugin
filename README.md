# resolvestock

Search free stock cutouts and vectors, download individual assets with their
license provenance, then drag local files straight into DaVinci Resolve's
media pool. Works with the free version of Resolve.

<!-- Add docs/demo.gif after recording the Resolve drag-and-drop loop. -->

## Why

Sourcing compositing material normally means leaving the editor and losing a
file's source and license as soon as it reaches a download folder. ResolveStock
searches the supported free sources in one window and preserves provenance with
each downloaded asset.

## Install

Requires Python 3.11 or newer.

macOS / Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

## Run

Desktop app:

```bash
.venv/bin/resolvestock          # macOS / Linux
.venv\Scripts\resolvestock      # Windows
```

Terminal search (prints results without opening the app; useful for checking
sources and your API key):

```bash
.venv/bin/python -m resolvestock.cli "smoke"                  # macOS / Linux
.venv\Scripts\python -m resolvestock.cli "smoke" --transparent  # Windows
```

Options: `--transparent`, `--vectors`, `--photos`, `--include-restricted`
(include NC/SA/unknown licenses), `--page N`, `--per-page N`.

## Pixabay key

Openverse and Wikimedia Commons work without credentials. To enable Pixabay,
get a free key from https://pixabay.com/api/docs/ and create
`~/.resolvestock/config.json` (on Windows, `C:\Users\<you>\.resolvestock\config.json`):

```json
{
  "pixabay_key": "your-key",
  "library_dir": "/Users/you/ResolveStock"
}
```

Restart the app after editing the config.

Pixabay API responses are cached for 24 hours and the app provides no
bulk-download workflow.

## Sources

| Source | API key | Notes |
|---|---|---|
| Openverse | Not needed | Available on first launch |
| Wikimedia Commons | Not needed | Strong source of alpha PNG and SVG |
| Pixabay | Free key | Adds transparent and vector server-side filters |

## Workflow

1. Search, optionally restricting to transparent assets or vectors.
2. Double-click one result to download it deliberately.
3. Drag the downloaded item from the library tray into Resolve.
4. Export credits when your project uses attribution-required assets.

Commercial-safe filtering is on by default and excludes NC, SA, and unknown
licenses. Each downloaded asset has a neighboring `.provenance.json` record.

## DaVinci Resolve integration

Free Resolve has no plugin surface for this workflow. ResolveStock is a
standalone desktop app: drag downloaded local files from its library tray into
Resolve's media pool. The normal library folder is also available to Resolve's
Media Storage and PowerBins.

## Development

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q   # macOS / Linux
.venv\Scripts\python -m pytest -q                         # Windows
```

Tests do not make network calls; source adapters use JSON fixtures.
