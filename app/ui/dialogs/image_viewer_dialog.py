from typing import List

from PyQt5.QtCore import Qt, QRunnable, QThreadPool, QMetaObject, Q_ARG, pyqtSlot
from PyQt5.QtGui import QKeySequence, QPixmap, QColor
from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QShortcut, QSizePolicy, QVBoxLayout, QWidget,
)

from app.models.frame_data import FrameData
from app.utils.time_utils import seconds_to_hms


class _ImageLoader(QRunnable):
    def __init__(self, path: str, dialog: "ImageViewerDialog"):
        super().__init__()
        self._path = path
        self._dialog = dialog
        self.setAutoDelete(True)

    def run(self) -> None:
        pixmap = QPixmap(self._path)
        QMetaObject.invokeMethod(
            self._dialog, "_on_image_loaded",
            Qt.QueuedConnection,
            Q_ARG(QPixmap, pixmap),
        )


class ImageViewerDialog(QDialog):
    _MIN_ZOOM = 0.05
    _MAX_ZOOM = 8.0

    def __init__(self, frames: List[FrameData], start_index: int, parent=None):
        super().__init__(parent)
        self._frames = frames
        self._idx = max(0, min(start_index, len(frames) - 1))
        self._zoom = 1.0
        self._fit_mode = True
        self._pixmap: QPixmap = None
        self._pool = QThreadPool.globalInstance()

        self.setWindowTitle("Frame Viewer")
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMaximizeButtonHint)
        self.resize(1100, 750)
        self._build_ui()
        self._setup_shortcuts()
        self._load_current()

    # ------------------------------------------------------------------ UI --

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── top info bar ──────────────────────────────────────────────────
        self._info_bar = QWidget()
        self._info_bar.setStyleSheet("background-color: #161616;")
        info_layout = QHBoxLayout(self._info_bar)
        info_layout.setContentsMargins(12, 6, 12, 6)

        self._info_label = QLabel("")
        self._info_label.setStyleSheet("color: #ddd; font-size: 12px; font-family: monospace;")
        info_layout.addWidget(self._info_label)
        info_layout.addStretch()

        self._toggle_btn = QPushButton("")
        self._toggle_btn.setFixedWidth(110)
        self._toggle_btn.clicked.connect(self._toggle_selection)
        info_layout.addWidget(self._toggle_btn)

        root.addWidget(self._info_bar)

        # ── image area ────────────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setAlignment(Qt.AlignCenter)
        self._scroll.setStyleSheet("background-color: #111; border: none;")
        self._scroll.setWidgetResizable(False)

        self._img_label = QLabel()
        self._img_label.setAlignment(Qt.AlignCenter)
        self._img_label.setStyleSheet("background-color: #111;")
        self._img_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._loading_label = QLabel("Loading…")
        self._loading_label.setAlignment(Qt.AlignCenter)
        self._loading_label.setStyleSheet("color: #666; font-size: 18px;")

        self._scroll.setWidget(self._img_label)
        root.addWidget(self._scroll, stretch=1)

        # ── bottom navigation bar ─────────────────────────────────────────
        nav = QWidget()
        nav.setStyleSheet("background-color: #161616;")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(12, 6, 12, 6)
        nav_layout.setSpacing(8)

        self._btn_prev = QPushButton("◀  Prev")
        self._btn_next = QPushButton("Next  ▶")
        for btn in (self._btn_prev, self._btn_next):
            btn.setFixedWidth(90)
        self._btn_prev.clicked.connect(self._go_prev)
        self._btn_next.clicked.connect(self._go_next)

        self._nav_label = QLabel("")
        self._nav_label.setAlignment(Qt.AlignCenter)
        self._nav_label.setStyleSheet("color: #888; font-size: 11px;")

        self._btn_fit = QPushButton("Fit")
        self._btn_actual = QPushButton("1:1")
        self._zoom_label = QLabel("100%")
        self._zoom_label.setStyleSheet("color: #888; font-size: 11px; min-width: 42px;")
        self._zoom_label.setAlignment(Qt.AlignCenter)
        for btn in (self._btn_fit, self._btn_actual):
            btn.setFixedWidth(50)
        self._btn_fit.clicked.connect(self._set_fit_mode)
        self._btn_actual.clicked.connect(self._set_actual_size)

        nav_layout.addWidget(self._btn_prev)
        nav_layout.addStretch()
        nav_layout.addWidget(self._nav_label)
        nav_layout.addStretch()
        nav_layout.addWidget(self._zoom_label)
        nav_layout.addWidget(self._btn_fit)
        nav_layout.addWidget(self._btn_actual)
        nav_layout.addWidget(self._btn_next)

        root.addWidget(nav)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.Key_Left),   self, self._go_prev)
        QShortcut(QKeySequence(Qt.Key_Right),  self, self._go_next)
        QShortcut(QKeySequence(Qt.Key_Escape), self, self.close)
        QShortcut(QKeySequence(Qt.Key_Space),  self, self._toggle_selection)
        QShortcut(QKeySequence(Qt.Key_F),      self, self._set_fit_mode)
        QShortcut(QKeySequence("Ctrl+="),      self, lambda: self._zoom_by(1.25))
        QShortcut(QKeySequence("Ctrl+-"),      self, lambda: self._zoom_by(0.8))

    # --------------------------------------------------------- navigation --

    def _go_prev(self) -> None:
        if self._idx > 0:
            self._idx -= 1
            self._load_current()

    def _go_next(self) -> None:
        if self._idx < len(self._frames) - 1:
            self._idx += 1
            self._load_current()

    def _load_current(self) -> None:
        self._pixmap = None
        self._img_label.setPixmap(QPixmap())
        self._img_label.setText("Loading…")
        self._img_label.setStyleSheet("color: #666; font-size: 18px; background-color: #111;")
        self._img_label.resize(self._scroll.viewport().size())
        self._update_info()
        loader = _ImageLoader(self._frames[self._idx].file_path, self)
        self._pool.start(loader)

    @pyqtSlot(QPixmap)
    def _on_image_loaded(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self._img_label.setStyleSheet("background-color: #111;")
        self._img_label.setText("")
        if self._fit_mode:
            self._apply_fit()
        else:
            self._apply_zoom()

    # ------------------------------------------------------------ display --

    def _update_info(self) -> None:
        frame = self._frames[self._idx]
        ts = seconds_to_hms(frame.timestamp_seconds)
        sharp = f"{frame.sharpness_score:.1f}" if frame.sharpness_score > 0 else "—"
        self._info_label.setText(
            f"Frame {frame.frame_index:06d}  │  {ts}  │  Sharpness: {sharp}"
        )
        self._update_selection_btn(frame.is_selected)
        total = len(self._frames)
        self._nav_label.setText(f"{self._idx + 1} / {total}")
        self._btn_prev.setEnabled(self._idx > 0)
        self._btn_next.setEnabled(self._idx < total - 1)

    def _update_selection_btn(self, selected: bool) -> None:
        if selected:
            self._toggle_btn.setText("✓ Selected")
            self._toggle_btn.setStyleSheet(
                "background-color: #1a4a2a; color: #7effa0; border-radius: 4px; padding: 3px 8px;"
            )
        else:
            self._toggle_btn.setText("✗ Unselected")
            self._toggle_btn.setStyleSheet(
                "background-color: #3a2a2a; color: #ff8888; border-radius: 4px; padding: 3px 8px;"
            )

    def _toggle_selection(self) -> None:
        frame = self._frames[self._idx]
        frame.is_selected = not frame.is_selected
        self._update_selection_btn(frame.is_selected)

    # -------------------------------------------------------------- zoom --

    def _apply_fit(self) -> None:
        self._fit_mode = True
        if self._pixmap is None or self._pixmap.isNull():
            return
        vp = self._scroll.viewport().size()
        scaled = self._pixmap.scaled(vp, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._img_label.setPixmap(scaled)
        self._img_label.resize(scaled.size())
        if self._pixmap.width() > 0:
            self._zoom = scaled.width() / self._pixmap.width()
        self._zoom_label.setText(f"{self._zoom * 100:.0f}%")

    def _apply_zoom(self) -> None:
        self._fit_mode = False
        if self._pixmap is None or self._pixmap.isNull():
            return
        w = int(self._pixmap.width() * self._zoom)
        h = int(self._pixmap.height() * self._zoom)
        scaled = self._pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._img_label.setPixmap(scaled)
        self._img_label.resize(scaled.size())
        self._zoom_label.setText(f"{self._zoom * 100:.0f}%")

    def _set_fit_mode(self) -> None:
        self._fit_mode = True
        self._apply_fit()

    def _set_actual_size(self) -> None:
        self._zoom = 1.0
        self._fit_mode = False
        self._apply_zoom()

    def _zoom_by(self, factor: float) -> None:
        self._fit_mode = False
        self._zoom = max(self._MIN_ZOOM, min(self._MAX_ZOOM, self._zoom * factor))
        self._apply_zoom()

    # ------------------------------------------------------- Qt overrides --

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self._zoom_by(factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._fit_mode and self._pixmap:
            self._apply_fit()
