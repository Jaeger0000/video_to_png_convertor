from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from app.utils.time_utils import seconds_to_hms


class ProgressPanel(QWidget):
    cancel_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self._phase_label = QLabel("")
        self._phase_label.setStyleSheet("font-style: italic; color: #aaa;")
        layout.addWidget(self._phase_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        info_row = QHBoxLayout()
        self._count_label = QLabel("")
        self._eta_label = QLabel("")
        info_row.addWidget(self._count_label)
        info_row.addStretch()
        info_row.addWidget(self._eta_label)
        layout.addLayout(info_row)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self.cancel_requested)
        layout.addWidget(self._cancel_btn)

    def set_phase(self, phase: str) -> None:
        self._phase_label.setText(phase)
        self._cancel_btn.setVisible(bool(phase))

    def update_progress(self, current: int, total: int) -> None:
        pct = int(current / total * 100) if total > 0 else 0
        self._progress_bar.setValue(pct)
        self._count_label.setText(f"{current:,} / {total:,} frames")

    def update_eta(self, seconds: float) -> None:
        self._eta_label.setText(f"ETA: {seconds_to_hms(seconds)}")

    def reset(self) -> None:
        self._phase_label.setText("")
        self._progress_bar.setValue(0)
        self._count_label.setText("")
        self._eta_label.setText("")
        self._cancel_btn.setVisible(False)
