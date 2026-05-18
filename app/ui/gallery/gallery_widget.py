from typing import List

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox, QDoubleSpinBox, QGroupBox, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QSpinBox, QSplitter, QStackedWidget,
    QVBoxLayout, QWidget,
)
from PyQt5.QtCore import Qt

from app.constants import FilterMode, SelectionMode
from app.models.frame_data import FrameData
from app.services.sharpness_service import SharpnessService
from app.ui.dialogs.image_viewer_dialog import ImageViewerDialog
from app.ui.gallery.sharpness_chart import SharpnessChart
from app.ui.gallery.thumbnail_grid import ThumbnailGrid


class GalleryWidget(QWidget):
    save_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frames: List[FrameData] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        splitter = QSplitter(Qt.Vertical)

        # Top: sharpness chart
        self._chart = SharpnessChart()
        splitter.addWidget(self._chart)

        # Bottom: controls + grid
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(4, 4, 4, 4)
        bottom_layout.setSpacing(6)

        bottom_layout.addWidget(self._build_selection_controls())

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self._filter_combo = QComboBox()
        self._filter_combo.addItems([
            "All", "Selected Only", "Unselected Only",
            "By Sharpness ↓", "By Sharpness ↑",
        ])
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._filter_combo)

        self._selected_count_label = QLabel("")
        filter_row.addStretch()
        filter_row.addWidget(self._selected_count_label)
        bottom_layout.addLayout(filter_row)

        self._grid = ThumbnailGrid()
        self._grid.frame_toggled.connect(self._on_frame_toggled)
        self._grid.frame_preview_requested.connect(self._on_preview_requested)
        bottom_layout.addWidget(self._grid)

        btn_row = QHBoxLayout()
        self._btn_save = QPushButton("Save Selected Frames")
        self._btn_save.setStyleSheet(
            "QPushButton { background-color: #1a6db5; color: white; "
            "font-weight: bold; padding: 6px 16px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #2585d4; }"
        )
        self._btn_save.clicked.connect(self.save_requested)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_save)
        bottom_layout.addLayout(btn_row)

        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

    def _build_selection_controls(self) -> QGroupBox:
        box = QGroupBox("Frame Selection")
        layout = QHBoxLayout(box)

        # Radio buttons
        self._radio_batch = QRadioButton("Batch")
        self._radio_best_n = QRadioButton("Best N")
        self._radio_top_pct = QRadioButton("Top %")
        self._radio_manual = QRadioButton("Manual")
        self._radio_batch.setChecked(True)
        for r in (self._radio_batch, self._radio_best_n, self._radio_top_pct, self._radio_manual):
            layout.addWidget(r)
            r.toggled.connect(self._on_mode_changed)

        # Stacked parameter widget
        self._param_stack = QStackedWidget()

        # Batch: batch size
        w_batch = QWidget()
        hl = QHBoxLayout(w_batch)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(QLabel("Batch size:"))
        self._batch_size_spin = QSpinBox()
        self._batch_size_spin.setRange(1, 10000)
        self._batch_size_spin.setValue(30)
        hl.addWidget(self._batch_size_spin)
        self._param_stack.addWidget(w_batch)  # index 0

        # Best N: n
        w_n = QWidget()
        hl2 = QHBoxLayout(w_n)
        hl2.setContentsMargins(0, 0, 0, 0)
        hl2.addWidget(QLabel("N:"))
        self._best_n_spin = QSpinBox()
        self._best_n_spin.setRange(1, 100000)
        self._best_n_spin.setValue(100)
        hl2.addWidget(self._best_n_spin)
        self._param_stack.addWidget(w_n)  # index 1

        # Top %
        w_pct = QWidget()
        hl3 = QHBoxLayout(w_pct)
        hl3.setContentsMargins(0, 0, 0, 0)
        hl3.addWidget(QLabel("Top %:"))
        self._top_pct_spin = QDoubleSpinBox()
        self._top_pct_spin.setRange(0.1, 100.0)
        self._top_pct_spin.setValue(20.0)
        self._top_pct_spin.setSuffix("%")
        hl3.addWidget(self._top_pct_spin)
        self._param_stack.addWidget(w_pct)  # index 2

        # Manual: no extra param
        w_manual = QWidget()
        w_manual.setLayout(QHBoxLayout())
        self._param_stack.addWidget(w_manual)  # index 3

        layout.addWidget(self._param_stack)

        self._btn_apply = QPushButton("Apply Selection")
        self._btn_apply.clicked.connect(self._apply_selection)
        layout.addWidget(self._btn_apply)

        return box

    def _on_mode_changed(self) -> None:
        if self._radio_batch.isChecked():
            self._param_stack.setCurrentIndex(0)
        elif self._radio_best_n.isChecked():
            self._param_stack.setCurrentIndex(1)
        elif self._radio_top_pct.isChecked():
            self._param_stack.setCurrentIndex(2)
        else:
            self._param_stack.setCurrentIndex(3)

    def load_frames(self, frames: List[FrameData]) -> None:
        self._frames = frames
        self._grid.load_frames(frames)
        self._chart.plot(frames)
        self._update_selection_count()

    def update_one_score(self, frame_index: int, score: float) -> None:
        if frame_index < len(self._frames):
            self._frames[frame_index].sharpness_score = score
            self._grid.refresh_frame(frame_index)

    def update_all_scores(self, scores: List[float]) -> None:
        for i, score in enumerate(scores):
            if i < len(self._frames):
                self._frames[i].sharpness_score = score
        self._chart.plot(self._frames)
        self._grid.refresh_all()

    def _apply_selection(self) -> None:
        if not self._frames:
            return
        if self._radio_batch.isChecked():
            selected_indices = set(SharpnessService.select_batch_sharpest(
                self._frames, self._batch_size_spin.value()
            ))
        elif self._radio_best_n.isChecked():
            selected_indices = set(SharpnessService.select_top_n(
                self._frames, self._best_n_spin.value()
            ))
        elif self._radio_top_pct.isChecked():
            selected_indices = set(SharpnessService.select_top_percentage(
                self._frames, self._top_pct_spin.value()
            ))
        else:
            return  # manual: user clicks individually

        for frame in self._frames:
            frame.is_selected = frame.frame_index in selected_indices

        self._chart.highlight_selection(selected_indices)
        self._grid.refresh_all()
        self._update_selection_count()

    def _on_filter_changed(self, index: int) -> None:
        mode_map = {
            0: FilterMode.ALL,
            1: FilterMode.SELECTED,
            2: FilterMode.UNSELECTED,
            3: FilterMode.SHARPNESS_DESC,
            4: FilterMode.SHARPNESS_ASC,
        }
        self._grid.set_filter(mode_map.get(index, FilterMode.ALL))

    def _on_frame_toggled(self, frame_index: int, is_selected: bool) -> None:
        if frame_index < len(self._frames):
            self._frames[frame_index].is_selected = is_selected
        selected = {f.frame_index for f in self._frames if f.is_selected}
        self._chart.highlight_selection(selected)
        self._update_selection_count()

    def _on_preview_requested(self, frame_index: int) -> None:
        dlg = ImageViewerDialog(self._frames, frame_index, parent=self)
        dlg.exec_()

    def _update_selection_count(self) -> None:
        total = len(self._frames)
        selected = sum(1 for f in self._frames if f.is_selected)
        self._selected_count_label.setText(f"{selected:,} / {total:,} selected")

    def get_frames(self) -> List[FrameData]:
        return self._frames
