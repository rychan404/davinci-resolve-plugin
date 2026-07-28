"""License identity and conservative commercial-safety rules."""

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


LICENSES = {
    "cc0": License(
        "CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/", True, False
    ),
    "public-domain": License(
        "Public Domain", "https://en.wikipedia.org/wiki/Public_domain", True, False
    ),
    "pixabay": License(
        "Pixabay Content License",
        "https://pixabay.com/service/license-summary/",
        True,
        False,
    ),
    "cc-by": License(
        "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/", True, True
    ),
    "cc-by-sa": License(
        "CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/", False, True
    ),
    "cc-by-nc": License(
        "CC BY-NC 4.0", "https://creativecommons.org/licenses/by-nc/4.0/", False, True
    ),
    "cc-by-nc-sa": License(
        "CC BY-NC-SA 4.0",
        "https://creativecommons.org/licenses/by-nc-sa/4.0/",
        False,
        True,
    ),
    "cc-by-nd": License(
        "CC BY-ND 4.0", "https://creativecommons.org/licenses/by-nd/4.0/", False, True
    ),
}
UNKNOWN = License("Unknown", "https://example.invalid/unknown", False, True)


def normalize_license_id(raw: str) -> str:
    if not raw:
        return "unknown"
    text = raw.strip().lower().replace("_", "-").replace("/", "-")
    text = text.replace(" ", "-")
    text = re.sub(r"-+", "-", text).strip("-")
    # CC0 is itself a license name, not a version number. Handle it before
    # stripping trailing versions such as the one in "CC0 1.0".
    if text in {"0", "cc0", "zero"}:
        return "cc0"
    text = re.sub(r"-?\d+(\.\d+)?$", "", text)
    if text.startswith("cc-"):
        text = text[3:]
    if text in {"0", "cc0", "zero"}:
        return "cc0"
    if text in {"pd", "public-domain", "pdm"}:
        return "public-domain"
    if text == "pixabay":
        return text
    candidate = f"cc-{text}"
    return candidate if candidate in LICENSES else "unknown"


def get_license(license_id: str) -> License:
    return LICENSES.get(license_id, UNKNOWN)


def is_commercial_safe(license_id: str) -> bool:
    return get_license(license_id).commercial_safe


def filter_commercial_safe(results: Iterable[SearchResult]) -> list[SearchResult]:
    return [result for result in results if is_commercial_safe(result.license_id)]
