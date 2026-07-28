"""Attribution credits for downloaded assets."""

from pathlib import Path
from typing import Iterable
from resolvestock.licenses import get_license
from resolvestock.models import LibraryItem

HEADER = "Credits\n=======\n"


def build_credits(items: Iterable[LibraryItem]) -> str:
    lines, seen = [], set()
    for item in items:
        license_meta = get_license(item.result.license_id)
        if not license_meta.requires_attribution or item.result.attribution in seen:
            continue
        seen.add(item.result.attribution)
        lines.append(
            f"- {item.result.attribution}\n"
            f"  {license_meta.name} - {item.result.license_url}\n"
            f"  {item.result.source_page_url}"
        )
    return f"{HEADER}\n" + (
        "\n".join(lines) + "\n"
        if lines
        else "No attribution required for the assets in this library.\n"
    )


def write_credits(items: Iterable[LibraryItem], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_credits(items), encoding="utf-8")
    return path
