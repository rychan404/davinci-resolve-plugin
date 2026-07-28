"""Desktop application entry point."""

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
    window = MainWindow(
        build_registry(
            CachedHttp(ResponseCache(config.library_dir / ".cache" / "responses.db")),
            config,
        ),
        Library(config.library_dir),
        config,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
