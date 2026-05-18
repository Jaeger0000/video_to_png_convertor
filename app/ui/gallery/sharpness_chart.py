from typing import List, Set

import numpy as np
from PyQt5.QtWidgets import QVBoxLayout, QWidget
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from app.constants import CHART_MAX_POINTS
from app.models.frame_data import FrameData


class SharpnessChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._frames: List[FrameData] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._fig = Figure(figsize=(6, 2.5), dpi=90, facecolor="#1e1e1e")
        self._ax = self._fig.add_subplot(111, facecolor="#252525")
        self._ax.tick_params(colors="#ccc", labelsize=8)
        for spine in self._ax.spines.values():
            spine.set_edgecolor("#555")
        self._ax.set_xlabel("Frame Index", color="#ccc", fontsize=8)
        self._ax.set_ylabel("Sharpness", color="#ccc", fontsize=8)
        self._fig.tight_layout(pad=1.5)

        self._canvas = FigureCanvasQTAgg(self._fig)
        toolbar = NavigationToolbar2QT(self._canvas, self)
        layout.addWidget(toolbar)
        layout.addWidget(self._canvas)

        self._line = None
        self._sel_scatter = None

    def plot(self, frames: List[FrameData]) -> None:
        self._frames = frames
        self._redraw()

    def update_scores(self, scores: List[float]) -> None:
        for i, score in enumerate(scores):
            if i < len(self._frames):
                self._frames[i].sharpness_score = score
        self._redraw_idle()

    def highlight_selection(self, selected_indices: Set[int]) -> None:
        self._redraw_idle()

    def _redraw(self) -> None:
        self._ax.cla()
        self._ax.set_facecolor("#252525")
        self._ax.tick_params(colors="#ccc", labelsize=8)
        self._ax.set_xlabel("Frame Index", color="#ccc", fontsize=8)
        self._ax.set_ylabel("Sharpness", color="#ccc", fontsize=8)
        for spine in self._ax.spines.values():
            spine.set_edgecolor("#555")

        if not self._frames:
            self._canvas.draw_idle()
            return

        indices = np.array([f.frame_index for f in self._frames])
        scores = np.array([f.sharpness_score for f in self._frames])

        # Downsample line for large datasets
        if len(indices) > CHART_MAX_POINTS:
            step = len(indices) // CHART_MAX_POINTS
            ds_idx = indices[::step]
            ds_scores = scores[::step]
        else:
            ds_idx = indices
            ds_scores = scores

        self._ax.plot(ds_idx, ds_scores, color="#4a9eff", linewidth=0.8, alpha=0.7)

        # Selected / unselected scatter (full resolution)
        sel_mask = np.array([f.is_selected for f in self._frames])
        if sel_mask.any():
            self._ax.scatter(indices[sel_mask], scores[sel_mask], s=8, c="#2ecc71", zorder=3, label="selected")
        if (~sel_mask).any():
            self._ax.scatter(indices[~sel_mask], scores[~sel_mask], s=4, c="#888", zorder=2, alpha=0.5)

        self._fig.tight_layout(pad=1.5)
        self._canvas.draw_idle()

    def _redraw_idle(self) -> None:
        self._redraw()
