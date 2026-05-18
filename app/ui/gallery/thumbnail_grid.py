import math
from typing import List, Optional

from PyQt5.QtCore import QRunnable, QThreadPool, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from app.constants import FilterMode, THUMBNAIL_PAGE_SIZE, THUMBNAIL_SIZE_PX
from app.models.frame_data import FrameData
from app.ui.gallery.frame_thumbnail import FrameThumbnailWidget


class _ThumbnailLoader(QRunnable):
    def __init__(self, path: str, widget: FrameThumbnailWidget):
        super().__init__()
        self._path = path
        self._widget = widget
        self.setAutoDelete(True)

    def run(self) -> None:
        pixmap = QPixmap(self._path)
        if not pixmap.isNull():
            from PyQt5.QtCore import QMetaObject, Q_ARG
            QMetaObject.invokeMethod(
                self._widget, "_receive_pixmap",
                Qt.QueuedConnection,
                Q_ARG(QPixmap, pixmap),
            )


class ThumbnailGrid(QWidget):
    frame_toggled = pyqtSignal(int, bool)

    PAGE_SIZE = THUMBNAIL_PAGE_SIZE

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_frames: List[FrameData] = []
        self._visible_frames: List[FrameData] = []
        self._current_page = 0
        self._filter_mode = FilterMode.ALL
        self._thumbnail_widgets: dict = {}
        self._pool = QThreadPool.globalInstance()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._grid_container = QWidget()
        self._grid = QGridLayout(self._grid_container)
        self._grid.setSpacing(6)
        self._scroll.setWidget(self._grid_container)
        layout.addWidget(self._scroll)

        page_row = QHBoxLayout()
        self._btn_prev = QPushButton("← Prev")
        self._btn_next = QPushButton("Next →")
        self._page_label = QLabel("Page 0 / 0")
        self._page_label.setAlignment(Qt.AlignCenter)
        self._btn_prev.clicked.connect(self._prev_page)
        self._btn_next.clicked.connect(self._next_page)
        page_row.addWidget(self._btn_prev)
        page_row.addStretch()
        page_row.addWidget(self._page_label)
        page_row.addStretch()
        page_row.addWidget(self._btn_next)
        layout.addLayout(page_row)

    def load_frames(self, frames: List[FrameData]) -> None:
        self._all_frames = frames
        self._current_page = 0
        self._apply_filter()

    def set_filter(self, mode: FilterMode) -> None:
        self._filter_mode = mode
        self._current_page = 0
        self._apply_filter()

    def refresh_all(self) -> None:
        self._apply_filter()

    def refresh_frame(self, frame_index: int) -> None:
        widget = self._thumbnail_widgets.get(frame_index)
        if widget:
            widget.set_sharpness(self._all_frames[frame_index].sharpness_score)

    def _apply_filter(self) -> None:
        if self._filter_mode == FilterMode.SELECTED:
            self._visible_frames = [f for f in self._all_frames if f.is_selected]
        elif self._filter_mode == FilterMode.UNSELECTED:
            self._visible_frames = [f for f in self._all_frames if not f.is_selected]
        elif self._filter_mode == FilterMode.SHARPNESS_DESC:
            self._visible_frames = sorted(self._all_frames, key=lambda f: f.sharpness_score, reverse=True)
        elif self._filter_mode == FilterMode.SHARPNESS_ASC:
            self._visible_frames = sorted(self._all_frames, key=lambda f: f.sharpness_score)
        else:
            self._visible_frames = list(self._all_frames)
        self._render_page(self._current_page)

    def _total_pages(self) -> int:
        return max(1, math.ceil(len(self._visible_frames) / self.PAGE_SIZE))

    def _render_page(self, page: int) -> None:
        self._current_page = max(0, min(page, self._total_pages() - 1))
        self._thumbnail_widgets.clear()

        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        start = self._current_page * self.PAGE_SIZE
        end = start + self.PAGE_SIZE
        page_frames = self._visible_frames[start:end]

        cols = max(1, (self.width() - 20) // (THUMBNAIL_SIZE_PX + 18))
        cols = max(3, cols)

        for i, frame in enumerate(page_frames):
            row, col = divmod(i, cols)
            widget = _PatchedThumbnail(frame)
            widget.toggled.connect(self._on_thumbnail_toggled)
            self._grid.addWidget(widget, row, col)
            self._thumbnail_widgets[frame.frame_index] = widget
            loader = _ThumbnailLoader(frame.file_path, widget)
            self._pool.start(loader)

        total = self._total_pages()
        self._page_label.setText(f"Page {self._current_page + 1} / {total}")
        self._btn_prev.setEnabled(self._current_page > 0)
        self._btn_next.setEnabled(self._current_page < total - 1)

    def _prev_page(self) -> None:
        self._render_page(self._current_page - 1)

    def _next_page(self) -> None:
        self._render_page(self._current_page + 1)

    def _on_thumbnail_toggled(self, frame_index: int, is_selected: bool) -> None:
        self.frame_toggled.emit(frame_index, is_selected)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._all_frames:
            self._render_page(self._current_page)


class _PatchedThumbnail(FrameThumbnailWidget):
    """Adds slot for cross-thread pixmap delivery."""

    @pyqtSlot(QPixmap)
    def _receive_pixmap(self, pixmap: QPixmap) -> None:
        self.set_pixmap(pixmap)
