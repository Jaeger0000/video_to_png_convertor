import os
from typing import Callable, List, Optional

from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout,
)

_ZOOM_MIN = 0.05
_ZOOM_MAX = 8.0
_ZOOM_STEP = 1.2


class ImageZoomDialog(QDialog):
    """Full-resolution zoom viewer with left/right navigation.

    annotate_fn: optional callable(path) -> QPixmap; use to draw bboxes etc.
    If None, images are loaded as-is.
    """

    def __init__(
        self,
        image_paths: List[str],
        start_index: int = 0,
        annotate_fn: Optional[Callable[[str], QPixmap]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._paths = image_paths
        self._index = max(0, min(start_index, len(image_paths) - 1))
        self._annotate_fn = annotate_fn or (lambda p: QPixmap(p))
        self._current_pix: Optional[QPixmap] = None
        self._zoom: float = 1.0
        self._fit_mode: bool = True
        self._build_ui()
        self.resize(1060, 740)
        self._load(self._index)

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        self._title_label = QLabel()
        self._title_label.setStyleSheet("font-weight: bold; color: #ddd; font-size: 12px;")
        header.addWidget(self._title_label)
        header.addStretch()
        self._counter_label = QLabel()
        self._counter_label.setStyleSheet("color: #888; font-size: 11px;")
        header.addWidget(self._counter_label)
        layout.addLayout(header)

        # Image area
        self._scroll = QScrollArea()
        self._scroll.setAlignment(Qt.AlignCenter)
        self._scroll.setWidgetResizable(False)
        self._scroll.setStyleSheet(
            "QScrollArea { background: #111; border: 1px solid #333; }"
            "QScrollArea > QWidget > QWidget { background: #111; }"
        )
        self._img_lbl = QLabel()
        self._img_lbl.setAlignment(Qt.AlignCenter)
        self._img_lbl.setStyleSheet("background: #111;")
        self._scroll.setWidget(self._img_lbl)
        self._scroll.viewport().installEventFilter(self)
        layout.addWidget(self._scroll, stretch=1)

        # Bottom controls
        ctrl = QHBoxLayout()
        ctrl.setSpacing(4)

        self._btn_prev = QPushButton("◀ Prev")
        self._btn_prev.setFixedWidth(80)
        self._btn_prev.clicked.connect(self._go_prev)
        ctrl.addWidget(self._btn_prev)

        ctrl.addStretch()

        for label, slot, w in [("−", self._zoom_out, 28), ("+", self._zoom_in, 28)]:
            b = QPushButton(label)
            b.setFixedSize(w, 26)
            b.clicked.connect(slot)
            ctrl.addWidget(b)

        self._zoom_lbl = QLabel("Fit")
        self._zoom_lbl.setFixedWidth(50)
        self._zoom_lbl.setAlignment(Qt.AlignCenter)
        self._zoom_lbl.setStyleSheet(
            "color: #aaa; font-size: 11px; background: #2a2a2a; "
            "border: 1px solid #444; border-radius: 2px; padding: 2px;"
        )
        ctrl.addWidget(self._zoom_lbl)

        for label, slot, w in [("Fit", self._zoom_fit, 38), ("1:1", self._zoom_100, 34)]:
            b = QPushButton(label)
            b.setFixedWidth(w)
            b.clicked.connect(slot)
            ctrl.addWidget(b)

        ctrl.addStretch()

        self._btn_next = QPushButton("Next ▶")
        self._btn_next.setFixedWidth(80)
        self._btn_next.clicked.connect(self._go_next)
        ctrl.addWidget(self._btn_next)

        layout.addLayout(ctrl)
        self.setFocusPolicy(Qt.StrongFocus)

    # ── image loading ────────────────────────────────────────────────────────

    def _load(self, index: int) -> None:
        if not self._paths:
            return
        self._index = index
        path = self._paths[index]
        pix = self._annotate_fn(path)
        self._current_pix = pix if not pix.isNull() else None
        self.setWindowTitle(os.path.basename(path))
        self._title_label.setText(os.path.basename(path))
        self._counter_label.setText(f"{index + 1} / {len(self._paths)}")
        self._btn_prev.setEnabled(index > 0)
        self._btn_next.setEnabled(index < len(self._paths) - 1)
        self._render()

    # ── zoom ─────────────────────────────────────────────────────────────────

    def _fit_scale(self) -> float:
        if not self._current_pix:
            return 1.0
        vp = self._scroll.viewport()
        iw, ih = self._current_pix.width(), self._current_pix.height()
        return min(max(1, vp.width()) / iw, max(1, vp.height()) / ih)

    def _zoom_in(self) -> None:
        if self._fit_mode:
            self._zoom = self._fit_scale()
            self._fit_mode = False
        self._zoom = min(_ZOOM_MAX, self._zoom * _ZOOM_STEP)
        self._render()

    def _zoom_out(self) -> None:
        if self._fit_mode:
            self._zoom = self._fit_scale()
            self._fit_mode = False
        self._zoom = max(_ZOOM_MIN, self._zoom / _ZOOM_STEP)
        self._render()

    def _zoom_fit(self) -> None:
        self._fit_mode = True
        self._render()

    def _zoom_100(self) -> None:
        self._fit_mode = False
        self._zoom = 1.0
        self._render()

    def _render(self) -> None:
        if not self._current_pix:
            return
        if self._fit_mode:
            scale = self._fit_scale()
            self._zoom_lbl.setText("Fit")
        else:
            scale = self._zoom
            self._zoom_lbl.setText(f"{int(scale * 100)}%")
        w = max(1, int(self._current_pix.width() * scale))
        h = max(1, int(self._current_pix.height() * scale))
        scaled = self._current_pix.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._img_lbl.setPixmap(scaled)
        self._img_lbl.resize(scaled.width(), scaled.height())

    # ── navigation ───────────────────────────────────────────────────────────

    def _go_prev(self) -> None:
        if self._index > 0:
            self._load(self._index - 1)

    def _go_next(self) -> None:
        if self._index < len(self._paths) - 1:
            self._load(self._index + 1)

    # ── events ───────────────────────────────────────────────────────────────

    def eventFilter(self, obj, event) -> bool:
        if obj is self._scroll.viewport() and event.type() == QEvent.Wheel:
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
            self._zoom_fit()
        elif key == Qt.Key_1:
            self._zoom_100()
        elif key == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._fit_mode:
            self._render()
