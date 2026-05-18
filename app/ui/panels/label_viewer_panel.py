import os
import random
import re
from typing import List, Optional, Tuple

from PyQt5.QtCore import QEvent, QSettings, Qt
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QScrollArea, QSplitter, QVBoxLayout, QWidget,
)

from app.constants import IMAGE_EXTENSIONS

_COLORS = [
    "#e74c3c", "#2ecc71", "#3498db", "#f39c12", "#9b59b6",
    "#1abc9c", "#e67e22", "#34495e", "#e91e63", "#00bcd4",
    "#8bc34a", "#ff5722", "#607d8b", "#ff9800", "#673ab7",
    "#4caf50", "#f44336", "#2196f3", "#ffeb3b", "#795548",
]

BBox = Tuple[int, float, float, float, float]

_ZOOM_MIN = 0.05
_ZOOM_MAX = 8.0
_ZOOM_STEP = 1.2


class LabelViewerPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = QSettings("VideoToPng", "App")
        self._images: List[str] = []
        self._class_names: List[str] = []
        self._current_index: int = -1
        self._annotated_pix: Optional[QPixmap] = None
        self._zoom: float = 1.0
        self._fit_mode: bool = True
        self._build_ui()

        saved = self._settings.value("viewer/folder", "")
        if saved and os.path.isdir(saved):
            self._folder_input.setText(saved)
            self._scan_folder()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("Label Viewer")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Labeled folder:"))
        self._folder_input = QLineEdit()
        self._folder_input.setPlaceholderText("Folder with images + YOLO .txt files…")
        folder_row.addWidget(self._folder_input)
        btn_browse = QPushButton("Browse")
        btn_browse.setFixedWidth(70)
        btn_browse.clicked.connect(self._browse_folder)
        folder_row.addWidget(btn_browse)
        btn_random = QPushButton("Random")
        btn_random.setFixedWidth(70)
        btn_random.clicked.connect(self._go_random)
        folder_row.addWidget(btn_random)
        layout.addLayout(folder_row)

        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self._image_list = QListWidget()
        self._image_list.setFixedWidth(220)
        self._image_list.currentRowChanged.connect(self._on_row_changed)
        left_layout.addWidget(self._image_list)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        # Scrollable image area
        self._scroll_area = QScrollArea()
        self._scroll_area.setAlignment(Qt.AlignCenter)
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setStyleSheet(
            "QScrollArea { background: #111; border: 1px solid #333; }"
            "QScrollArea > QWidget > QWidget { background: #111; }"
        )
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setStyleSheet("background: #111;")
        self._scroll_area.setWidget(self._image_label)
        self._scroll_area.viewport().installEventFilter(self)
        right_layout.addWidget(self._scroll_area, stretch=1)

        # Zoom controls + info row
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(4)

        btn_zoom_out = QPushButton("−")
        btn_zoom_out.setFixedSize(28, 26)
        btn_zoom_out.setToolTip("Zoom out  (Ctrl+Scroll)")
        btn_zoom_out.clicked.connect(self._zoom_out)
        bottom_row.addWidget(btn_zoom_out)

        self._zoom_label = QLabel("Fit")
        self._zoom_label.setFixedWidth(48)
        self._zoom_label.setAlignment(Qt.AlignCenter)
        self._zoom_label.setStyleSheet(
            "color: #aaa; font-size: 11px; background: #2a2a2a; "
            "border: 1px solid #444; border-radius: 2px; padding: 2px;"
        )
        bottom_row.addWidget(self._zoom_label)

        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setFixedSize(28, 26)
        btn_zoom_in.setToolTip("Zoom in  (Ctrl+Scroll)")
        btn_zoom_in.clicked.connect(self._zoom_in)
        bottom_row.addWidget(btn_zoom_in)

        btn_fit = QPushButton("Fit")
        btn_fit.setFixedWidth(38)
        btn_fit.setToolTip("Fit image to window")
        btn_fit.clicked.connect(self._zoom_reset_fit)
        bottom_row.addWidget(btn_fit)

        btn_100 = QPushButton("1:1")
        btn_100.setFixedWidth(34)
        btn_100.setToolTip("Show at 100% (original size)")
        btn_100.clicked.connect(self._zoom_100)
        bottom_row.addWidget(btn_100)

        bottom_row.addSpacing(10)

        self._info_label = QLabel("No image selected")
        self._info_label.setStyleSheet("color: #aaa; font-size: 11px;")
        self._info_label.setWordWrap(True)
        bottom_row.addWidget(self._info_label, stretch=1)

        right_layout.addLayout(bottom_row)

        nav_row = QHBoxLayout()
        self._btn_prev = QPushButton("◀ Prev")
        self._btn_next = QPushButton("Next ▶")
        self._btn_prev.clicked.connect(self._go_prev)
        self._btn_next.clicked.connect(self._go_next)
        nav_row.addWidget(self._btn_prev)
        nav_row.addStretch()
        nav_row.addWidget(self._btn_next)
        right_layout.addLayout(nav_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        self.setFocusPolicy(Qt.StrongFocus)

    # ── zoom ─────────────────────────────────────────────────────────────────

    def _current_fit_scale(self) -> float:
        if self._annotated_pix is None or self._annotated_pix.isNull():
            return 1.0
        vp = self._scroll_area.viewport()
        iw, ih = self._annotated_pix.width(), self._annotated_pix.height()
        return min(max(1, vp.width()) / iw, max(1, vp.height()) / ih)

    def _zoom_in(self) -> None:
        if self._fit_mode:
            self._zoom = self._current_fit_scale()
            self._fit_mode = False
        self._zoom = min(_ZOOM_MAX, self._zoom * _ZOOM_STEP)
        self._render_zoom()

    def _zoom_out(self) -> None:
        if self._fit_mode:
            self._zoom = self._current_fit_scale()
            self._fit_mode = False
        self._zoom = max(_ZOOM_MIN, self._zoom / _ZOOM_STEP)
        self._render_zoom()

    def _zoom_reset_fit(self) -> None:
        self._fit_mode = True
        self._render_zoom()

    def _zoom_100(self) -> None:
        self._fit_mode = False
        self._zoom = 1.0
        self._render_zoom()

    def _render_zoom(self) -> None:
        if self._annotated_pix is None or self._annotated_pix.isNull():
            return
        if self._fit_mode:
            scale = self._current_fit_scale()
            self._zoom_label.setText("Fit")
        else:
            scale = self._zoom
            self._zoom_label.setText(f"{int(scale * 100)}%")

        new_w = max(1, int(self._annotated_pix.width() * scale))
        new_h = max(1, int(self._annotated_pix.height() * scale))
        scaled = self._annotated_pix.scaled(
            new_w, new_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._image_label.setPixmap(scaled)
        self._image_label.resize(scaled.width(), scaled.height())

    # ── event handling ───────────────────────────────────────────────────────

    def eventFilter(self, obj, event) -> bool:
        if obj is self._scroll_area.viewport() and event.type() == QEvent.Wheel:
            if event.modifiers() & Qt.ControlModifier:
                if event.angleDelta().y() > 0:
                    self._zoom_in()
                else:
                    self._zoom_out()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key_Left, Qt.Key_A):
            self._go_prev()
        elif key in (Qt.Key_Right, Qt.Key_D):
            self._go_next()
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            self._zoom_in()
        elif key == Qt.Key_Minus:
            self._zoom_out()
        elif key == Qt.Key_0:
            self._zoom_reset_fit()
        elif key == Qt.Key_1:
            self._zoom_100()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._fit_mode:
            self._render_zoom()

    # ── folder scanning ──────────────────────────────────────────────────────

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Labeled Images Folder")
        if folder:
            self._folder_input.setText(folder)
            self._scan_folder()

    def _scan_folder(self) -> None:
        folder = self._folder_input.text().strip()
        if not folder or not os.path.isdir(folder):
            return
        self._settings.setValue("viewer/folder", folder)
        self._class_names = self._detect_class_names(folder)
        self._images = sorted(
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
        )
        self._image_list.clear()
        for img_path in self._images:
            fname = os.path.basename(img_path)
            has_lbl = os.path.isfile(os.path.splitext(img_path)[0] + ".txt")
            item = QListWidgetItem(f"{'✓' if has_lbl else '✗'}  {fname}")
            item.setForeground(QColor("#ccc") if has_lbl else QColor("#555"))
            self._image_list.addItem(item)
        if self._images:
            self._image_list.setCurrentRow(0)

    def _detect_class_names(self, folder: str) -> List[str]:
        for fname in ("classes.txt", "obj.names"):
            path = os.path.join(folder, fname)
            if os.path.isfile(path):
                with open(path) as f:
                    return [l.strip() for l in f if l.strip()]
        for fname in ("data.yaml", "dataset.yaml"):
            for d in (folder, os.path.dirname(folder)):
                path = os.path.join(d, fname)
                if os.path.isfile(path):
                    try:
                        with open(path) as f:
                            content = f.read()
                        m = re.search(r"names\s*:\s*\[([^\]]+)\]", content)
                        if m:
                            return [n.strip().strip("'\"") for n in m.group(1).split(",")]
                    except Exception:
                        pass
        return []

    # ── image display ────────────────────────────────────────────────────────

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._images):
            self._current_index = row
            self._load_and_annotate(self._images[row])

    def _load_and_annotate(self, img_path: str) -> None:
        pix = QPixmap(img_path)
        if pix.isNull():
            self._image_label.setText("Could not load image.")
            self._annotated_pix = None
            return

        txt_path = os.path.splitext(img_path)[0] + ".txt"
        bboxes = self._load_bboxes(txt_path)

        if bboxes:
            pix = pix.copy()
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing)
            w, h = pix.width(), pix.height()
            pen_width = max(2, w // 500)
            for class_id, cx, cy, bw, bh in bboxes:
                color = QColor(_COLORS[class_id % len(_COLORS)])
                painter.setPen(QPen(color, pen_width))
                x1 = int((cx - bw / 2) * w)
                y1 = int((cy - bh / 2) * h)
                bw_px = int(bw * w)
                bh_px = int(bh * h)
                painter.drawRect(x1, y1, bw_px, bh_px)
                label = (
                    self._class_names[class_id]
                    if class_id < len(self._class_names)
                    else f"class_{class_id}"
                )
                text_w = len(label) * 7 + 6
                text_h = 16
                painter.fillRect(x1, max(0, y1 - text_h), text_w, text_h, color)
                painter.setPen(QPen(QColor("white"), 1))
                painter.drawText(x1 + 3, max(text_h, y1) - 3, label)
            painter.end()

        self._annotated_pix = pix
        self._render_zoom()

        class_counts: dict = {}
        for class_id, *_ in bboxes:
            name = (
                self._class_names[class_id]
                if class_id < len(self._class_names)
                else f"class_{class_id}"
            )
            class_counts[name] = class_counts.get(name, 0) + 1
        info = os.path.basename(img_path)
        if class_counts:
            info += "   |   " + "  ".join(f"{k}({v})" for k, v in class_counts.items())
        else:
            info += "   (no labels)"
        self._info_label.setText(info)

    def _load_bboxes(self, txt_path: str) -> List[BBox]:
        bboxes: List[BBox] = []
        if not os.path.isfile(txt_path):
            return bboxes
        try:
            with open(txt_path) as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 5:
                        try:
                            bboxes.append((
                                int(parts[0]),
                                float(parts[1]), float(parts[2]),
                                float(parts[3]), float(parts[4]),
                            ))
                        except ValueError:
                            pass
        except Exception:
            pass
        return bboxes

    # ── navigation ───────────────────────────────────────────────────────────

    def _go_prev(self) -> None:
        if self._images and self._current_index > 0:
            self._image_list.setCurrentRow(self._current_index - 1)

    def _go_next(self) -> None:
        if self._images and self._current_index < len(self._images) - 1:
            self._image_list.setCurrentRow(self._current_index + 1)

    def _go_random(self) -> None:
        if self._images:
            self._image_list.setCurrentRow(random.randint(0, len(self._images) - 1))
