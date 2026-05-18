import json
import os
import random
import shutil
from typing import Dict, List, Set

from PyQt5.QtCore import QMetaObject, QRunnable, QSettings, QThreadPool, Qt, Q_ARG, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QFileDialog, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea,
    QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from app.constants import IMAGE_EXTENSIONS

HISTORY_FILENAME = "sample_history.json"
THUMB_SIZE = 118


class _ThumbLoader(QRunnable):
    def __init__(self, path: str, widget: "SamplerThumb"):
        super().__init__()
        self._path = path
        self._widget = widget
        self.setAutoDelete(True)

    def run(self) -> None:
        pix = QPixmap(self._path)
        if not pix.isNull():
            QMetaObject.invokeMethod(
                self._widget, "_set_pixmap",
                Qt.QueuedConnection,
                Q_ARG(QPixmap, pix),
            )


class SamplerThumb(QLabel):
    toggled = pyqtSignal(str, bool)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background: #2a2a2a; border: 2px solid #444;")
        self._path = path
        self._staged = False

    @pyqtSlot(QPixmap)
    def _set_pixmap(self, pix: QPixmap) -> None:
        scaled = pix.scaled(
            THUMB_SIZE - 4, THUMB_SIZE - 4,
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        self.setPixmap(scaled)

    def mousePressEvent(self, event) -> None:
        self.set_staged(not self._staged)
        self.toggled.emit(self._path, self._staged)

    def set_staged(self, staged: bool) -> None:
        self._staged = staged
        border = "#2ecc71" if staged else "#444"
        self.setStyleSheet(f"background: #2a2a2a; border: 2px solid {border};")

    @property
    def is_staged(self) -> bool:
        return self._staged


class LabelSamplerPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = QSettings("VideoToPng", "App")
        self._pool = QThreadPool.globalInstance()
        self._current_folder: str = ""
        self._thumb_widgets: Dict[str, SamplerThumb] = {}
        self._staged: Set[str] = set()
        self._history: Set[str] = set()
        self._build_ui()

        saved = self._settings.value("sampler/source_folder", "")
        if saved and os.path.isdir(saved):
            self._source_input.setText(saved)
            self._scan_source()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("Label Sampler")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

        src_row = QHBoxLayout()
        src_row.addWidget(QLabel("Source folder:"))
        self._source_input = QLineEdit()
        self._source_input.setPlaceholderText("frames/ root folder…")
        src_row.addWidget(self._source_input)
        btn_browse = QPushButton("Browse")
        btn_browse.setFixedWidth(70)
        btn_browse.clicked.connect(self._browse_source)
        src_row.addWidget(btn_browse)
        btn_refresh = QPushButton("Refresh")
        btn_refresh.setFixedWidth(70)
        btn_refresh.clicked.connect(self._scan_source)
        src_row.addWidget(btn_refresh)
        layout.addLayout(src_row)

        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        left_layout.addWidget(QLabel("Subfolders:"))
        self._folder_list = QListWidget()
        self._folder_list.setFixedWidth(260)
        self._folder_list.currentItemChanged.connect(self._on_folder_selected)
        left_layout.addWidget(self._folder_list)
        self._excluded_label = QLabel("Already sampled: 0")
        self._excluded_label.setStyleSheet("color: #888; font-size: 10px;")
        left_layout.addWidget(self._excluded_label)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._grid_container = QWidget()
        from PyQt5.QtWidgets import QGridLayout
        self._grid = QGridLayout(self._grid_container)
        self._grid.setSpacing(6)
        self._grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._scroll.setWidget(self._grid_container)
        right_layout.addWidget(self._scroll)

        sample_row = QHBoxLayout()
        sample_row.addWidget(QLabel("Sample N randomly:"))
        self._sample_spin = QSpinBox()
        self._sample_spin.setRange(1, 100000)
        self._sample_spin.setValue(50)
        sample_row.addWidget(self._sample_spin)
        btn_sample = QPushButton("Sample")
        btn_sample.setFixedWidth(80)
        btn_sample.clicked.connect(self._do_random_sample)
        sample_row.addWidget(btn_sample)
        btn_clear = QPushButton("Clear")
        btn_clear.setFixedWidth(60)
        btn_clear.clicked.connect(self._clear_staged)
        sample_row.addWidget(btn_clear)
        sample_row.addStretch()
        right_layout.addLayout(sample_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #444;")
        layout.addWidget(line)

        batch_row = QHBoxLayout()
        batch_row.addWidget(QLabel("Batch output folder:"))
        self._batch_input = QLineEdit()
        self._batch_input.setPlaceholderText("Output folder for labeling batch…")
        batch_row.addWidget(self._batch_input)
        btn_browse_batch = QPushButton("Browse")
        btn_browse_batch.setFixedWidth(70)
        btn_browse_batch.clicked.connect(self._browse_batch)
        batch_row.addWidget(btn_browse_batch)
        layout.addLayout(batch_row)

        bottom_row = QHBoxLayout()
        self._status_label = QLabel("0 images staged")
        self._status_label.setStyleSheet("color: #aaa;")
        bottom_row.addWidget(self._status_label)
        bottom_row.addStretch()
        self._btn_create = QPushButton("Create Labeling Batch")
        self._btn_create.setStyleSheet(
            "QPushButton { background-color: #1a6db5; color: white; "
            "font-weight: bold; padding: 6px 16px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #2585d4; }"
            "QPushButton:disabled { background-color: #333; color: #666; }"
        )
        self._btn_create.clicked.connect(self._create_batch)
        bottom_row.addWidget(self._btn_create)
        layout.addLayout(bottom_row)

    # ── public ──────────────────────────────────────────────────────────────

    def set_source_folder(self, folder: str) -> None:
        if folder and os.path.isdir(folder):
            self._source_input.setText(folder)
            self._scan_source()

    # ── scanning ────────────────────────────────────────────────────────────

    def _browse_source(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Frames Root Folder")
        if folder:
            self._source_input.setText(folder)
            self._scan_source()

    def _browse_batch(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Batch Output Folder")
        if folder:
            self._batch_input.setText(folder)

    def _scan_source(self) -> None:
        folder = self._source_input.text().strip()
        if not folder or not os.path.isdir(folder):
            return
        self._settings.setValue("sampler/source_folder", folder)
        self._load_history(folder)
        self._staged.clear()
        self._clear_grid()
        self._thumb_widgets.clear()
        self._current_folder = ""
        self._folder_list.clear()
        try:
            entries = sorted(
                (e for e in os.scandir(folder) if e.is_dir()),
                key=lambda e: e.name,
            )
            for entry in entries:
                count = sum(
                    1 for f in os.scandir(entry.path)
                    if os.path.splitext(f.name)[1].lower() in IMAGE_EXTENSIONS
                )
                if count == 0:
                    continue
                item = QListWidgetItem(f"  {entry.name}   ({count:,})")
                item.setData(Qt.UserRole, entry.path)
                self._folder_list.addItem(item)
        except PermissionError:
            pass
        self._update_status()

    def _load_history(self, source_root: str) -> None:
        self._history.clear()
        path = os.path.join(source_root, HISTORY_FILENAME)
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                self._history = set(data.get("sampled", []))
            except Exception:
                pass
        self._excluded_label.setText(f"Already sampled: {len(self._history):,}")

    def _save_history(self, source_root: str, new_rel_paths: List[str]) -> None:
        self._history.update(new_rel_paths)
        path = os.path.join(source_root, HISTORY_FILENAME)
        try:
            with open(path, "w") as f:
                json.dump({"sampled": sorted(self._history)}, f, indent=2)
        except Exception:
            pass
        self._excluded_label.setText(f"Already sampled: {len(self._history):,}")

    # ── thumbnail grid ───────────────────────────────────────────────────────

    def _on_folder_selected(self, current, _previous) -> None:
        if not current:
            return
        self._load_folder_thumbnails(current.data(Qt.UserRole))

    def _load_folder_thumbnails(self, folder_path: str) -> None:
        self._current_folder = folder_path
        self._clear_grid()
        self._thumb_widgets.clear()
        try:
            images = sorted(
                f.path for f in os.scandir(folder_path)
                if os.path.splitext(f.name)[1].lower() in IMAGE_EXTENSIONS
            )
        except PermissionError:
            return

        cols = max(3, (self._scroll.width() - 20) // (THUMB_SIZE + 10))
        for i, img_path in enumerate(images):
            row, col = divmod(i, cols)
            widget = SamplerThumb(img_path)
            widget.toggled.connect(self._on_thumb_toggled)
            if img_path in self._staged:
                widget.set_staged(True)
            self._grid.addWidget(widget, row, col)
            self._thumb_widgets[img_path] = widget
            self._pool.start(_ThumbLoader(img_path, widget))

    def _clear_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ── staging ──────────────────────────────────────────────────────────────

    def _on_thumb_toggled(self, path: str, staged: bool) -> None:
        if staged:
            self._staged.add(path)
        else:
            self._staged.discard(path)
        self._update_status()

    def _do_random_sample(self) -> None:
        if not self._current_folder:
            return
        n = self._sample_spin.value()
        source_root = self._source_input.text().strip()

        try:
            all_images = [
                f.path for f in os.scandir(self._current_folder)
                if os.path.splitext(f.name)[1].lower() in IMAGE_EXTENSIONS
            ]
        except PermissionError:
            return

        def rel(p: str) -> str:
            try:
                return os.path.relpath(p, source_root)
            except ValueError:
                return p

        available = [p for p in all_images if rel(p) not in self._history and p not in self._staged]
        sampled = random.sample(available, min(n, len(available)))
        for path in sampled:
            self._staged.add(path)
            w = self._thumb_widgets.get(path)
            if w:
                w.set_staged(True)
        self._update_status()

    def _clear_staged(self) -> None:
        self._staged.clear()
        for w in self._thumb_widgets.values():
            w.set_staged(False)
        self._update_status()

    def _update_status(self) -> None:
        self._status_label.setText(f"{len(self._staged):,} images staged")

    # ── batch creation ───────────────────────────────────────────────────────

    def _create_batch(self) -> None:
        if not self._staged:
            QMessageBox.information(self, "No Images", "No images are staged for this batch.")
            return
        batch_folder = self._batch_input.text().strip()
        if not batch_folder:
            QMessageBox.warning(self, "No Output Folder", "Please select a batch output folder.")
            return
        source_root = self._source_input.text().strip()
        os.makedirs(batch_folder, exist_ok=True)
        new_rel: List[str] = []
        errors = 0
        for img_path in list(self._staged):
            try:
                shutil.copy2(img_path, batch_folder)
                try:
                    new_rel.append(os.path.relpath(img_path, source_root))
                except ValueError:
                    new_rel.append(img_path)
            except Exception:
                errors += 1
        self._save_history(source_root, new_rel)
        self._staged.clear()
        for w in self._thumb_widgets.values():
            w.set_staged(False)
        self._update_status()
        msg = f"Batch created: {len(new_rel):,} images copied to:\n{batch_folder}"
        if errors:
            msg += f"\n\n{errors} file(s) failed to copy."
        QMessageBox.information(self, "Batch Created", msg)
