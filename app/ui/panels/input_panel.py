import os
from typing import List

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from app.constants import VIDEO_EXTENSIONS


class InputPanel(QWidget):
    videos_loaded = pyqtSignal(list)
    video_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths: List[str] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        label = QLabel("Video Input")
        label.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(label)

        btn_row = QHBoxLayout()
        self._btn_add_files = QPushButton("Add Video(s)")
        self._btn_add_folder = QPushButton("Add Folder")
        self._btn_clear = QPushButton("Clear All")
        for btn in (self._btn_add_files, self._btn_add_folder, self._btn_clear):
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        self._list = QListWidget()
        self._list.setMinimumHeight(120)
        layout.addWidget(self._list)

        self._count_label = QLabel("No videos loaded")
        layout.addWidget(self._count_label)

        self._btn_add_files.clicked.connect(self._add_files_dialog)
        self._btn_add_folder.clicked.connect(self._add_folder_dialog)
        self._btn_clear.clicked.connect(self._clear_all)
        self._list.itemClicked.connect(self._on_item_clicked)

    def _add_files_dialog(self) -> None:
        ext_filter = "Video Files (" + " ".join(f"*{e}" for e in sorted(VIDEO_EXTENSIONS)) + ")"
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Video(s)", "", ext_filter)
        if paths:
            self._add_paths(paths)

    def _add_folder_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder:
            return
        found = []
        for entry in os.scandir(folder):
            if entry.is_file() and os.path.splitext(entry.name)[1].lower() in VIDEO_EXTENSIONS:
                found.append(entry.path)
        found.sort()
        if found:
            self._add_paths(found)

    def _add_paths(self, paths: List[str]) -> None:
        existing = set(self._paths)
        new_paths = [p for p in paths if p not in existing]
        for path in new_paths:
            self._paths.append(path)
            item = QListWidgetItem(os.path.basename(path))
            item.setData(0x0100, path)
            self._list.addItem(item)
        if new_paths:
            self._update_count()
            self.videos_loaded.emit(list(self._paths))

    def _clear_all(self) -> None:
        self._paths.clear()
        self._list.clear()
        self._update_count()

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        path = item.data(0x0100)
        if path:
            self.video_selected.emit(path)

    def _update_count(self) -> None:
        n = len(self._paths)
        self._count_label.setText(f"{n} video{'s' if n != 1 else ''} loaded")

    def get_all_paths(self) -> List[str]:
        return list(self._paths)

    def highlight_video(self, path: str) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            is_current = item.data(0x0100) == path
            item.setSelected(is_current)
