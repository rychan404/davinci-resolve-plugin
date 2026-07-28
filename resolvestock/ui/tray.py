"""Local library tray: the only drag source, always CopyAction."""

from pathlib import Path
from PySide6.QtCore import QMimeData, QSize, Qt, QUrl
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QStyle
from resolvestock.licenses import get_license
from resolvestock.models import LibraryItem


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
            entry.setToolTip(
                f"{item.result.attribution}\n"
                f"{get_license(item.result.license_id).name}\n"
                f"{item.result.source_page_url}"
            )
            pixmap = QPixmap(str(item.local_path))
            entry.setIcon(QIcon(pixmap) if not pixmap.isNull() else placeholder)
            self.addItem(entry)

    def selected_paths(self) -> list[Path]:
        return [Path(entry.data(Qt.UserRole)) for entry in self.selectedItems()]

    def mimeData(self, items) -> QMimeData:
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(entry.data(Qt.UserRole)) for entry in items])
        return data

    def startDrag(self, supportedActions) -> None:
        super().startDrag(Qt.CopyAction)
