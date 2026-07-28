"""Persistent user settings."""

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
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> "Config":
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls(path)
        return cls(
            path,
            data.get("pixabay_key") or None,
            Path(data["library_dir"])
            if data.get("library_dir")
            else DEFAULT_LIBRARY_DIR,
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {"pixabay_key": self.pixabay_key, "library_dir": str(self.library_dir)},
                indent=2,
            ),
            encoding="utf-8",
        )
