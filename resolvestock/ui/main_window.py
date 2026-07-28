"""Main search, download, provenance, and drag workflow."""

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
    def __init__(self, library, result, signals):
        super().__init__()
        self.library, self.result, self.signals = library, result, signals

    def run(self):
        try:
            self.signals.finished.emit(self.library.download(self.result))
        except Exception as error:
            self.signals.failed.emit(str(error))


class MainWindow(QMainWindow):
    def __init__(self, registry, library, config, parent=None):
        super().__init__(parent)
        self.registry, self.library, self.config, self.pool = (
            registry,
            library,
            config,
            QThreadPool.globalInstance(),
        )
        # QThreadPool owns the C++ QRunnable, but not necessarily the Python
        # wrappers captured by its callbacks. Retaining jobs until a queued
        # completion signal reaches the UI thread prevents PySide from
        # collecting a signal object while its worker is still emitting.
        self._active_downloads: set[_DownloadJob] = set()
        self.setWindowTitle("resolvestock")
        self.resize(1100, 760)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("search cutouts and vectors")
        self.search_input.returnPressed.connect(self.run_search)
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.run_search)
        (
            self.transparent_checkbox,
            self.vectors_checkbox,
            self.commercial_safe_checkbox,
        ) = (
            QCheckBox("Transparent only"),
            QCheckBox("Vectors only"),
            QCheckBox("Commercial-safe only"),
        )
        self.commercial_safe_checkbox.setChecked(True)
        self.credits_button = QPushButton("Export credits")
        self.credits_button.clicked.connect(self._prompt_export_credits)
        self.grid, self.tray, self.status_label = (
            ResultsGrid(),
            LibraryTray(),
            QLabel("ready"),
        )
        self.status_label.setWordWrap(True)
        self.grid.download_requested.connect(self.download)
        controls = QHBoxLayout()
        controls.addWidget(self.search_input, 1)
        controls.addWidget(self.search_button)
        filters = QHBoxLayout()
        [
            filters.addWidget(widget)
            for widget in (
                self.transparent_checkbox,
                self.vectors_checkbox,
                self.commercial_safe_checkbox,
            )
        ]
        filters.addStretch(1)
        filters.addWidget(self.credits_button)
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.grid)
        splitter.addWidget(self.tray)
        splitter.setSizes([520, 240])
        layout = QVBoxLayout()
        layout.addLayout(controls)
        layout.addLayout(filters)
        layout.addWidget(QLabel("Results — double click to download"))
        layout.addWidget(splitter, 1)
        layout.addWidget(QLabel("Library — drag into Resolve's media pool"))
        layout.addWidget(self.status_label)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)
        self.refresh_tray()

    def closeEvent(self, event):
        self.grid.loader.stop()
        super().closeEvent(event)

    def build_query(self) -> SearchQuery:
        return SearchQuery(
            self.search_input.text().strip(),
            transparent_only=self.transparent_checkbox.isChecked(),
            vectors_only=self.vectors_checkbox.isChecked(),
            commercial_safe_only=self.commercial_safe_checkbox.isChecked(),
        )

    def run_search(self) -> None:
        query = self.build_query()
        if not query.text:
            self.status_label.setText("enter a search term")
            return
        outcome = self.registry.search(query)
        self.grid.set_results(outcome.results)
        message = f"{len(outcome.results)} result(s)"
        if outcome.errors:
            message += " — some sources failed — " + "; ".join(
                f"{name}: {error}" for name, error in outcome.errors.items()
            )
        self.status_label.setText(message)

    def download(self, result, threaded=True) -> None:
        self.status_label.setText(f"downloading {result.title}...")
        signals = _DownloadSignals(self)
        job = _DownloadJob(self.library, result, signals)

        def finished(item) -> None:
            self._active_downloads.discard(job)
            self._on_download_finished(item)

        def failed(message: str) -> None:
            self._active_downloads.discard(job)
            self.status_label.setText(f"failed: {message}")

        signals.finished.connect(finished)
        signals.failed.connect(failed)
        self._active_downloads.add(job)
        if threaded:
            self.pool.start(job)
        else:
            job.run()

    def _on_download_finished(self, item):
        self.refresh_tray()
        self.status_label.setText(f"saved {item.local_path.name}")

    def refresh_tray(self):
        self.tray.set_items(self.library.items())

    def export_credits(self, path: Path) -> Path:
        return write_credits(self.library.items(), Path(path))

    def _prompt_export_credits(self):
        chosen, _ = QFileDialog.getSaveFileName(
            self, "Export credits", "CREDITS.txt", "Text files (*.txt)"
        )
        if chosen:
            self.export_credits(Path(chosen))
            self.status_label.setText(f"credits written to {chosen}")
