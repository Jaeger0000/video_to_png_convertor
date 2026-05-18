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

        phase_row = QHBoxLayout()
        self._phase_label = QLabel("")
        self._phase_label.setStyleSheet("font-style: italic; color: #aaa;")
        phase_row.addWidget(self._phase_label)
        phase_row.addStretch()
        self._device_badge = QLabel("")
        self._device_badge.setStyleSheet(
            "background-color: #1a3a5c; color: #7ec8ff; "
            "font-size: 10px; padding: 2px 7px; border-radius: 8px;"
        )
        self._device_badge.setVisible(False)
        phase_row.addWidget(self._device_badge)
        layout.addLayout(phase_row)

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

    def set_device(self, label: str) -> None:
        self._device_badge.setText(label)
        self._device_badge.setVisible(bool(label))
        color = "#1a4a2a" if "GPU" in label else "#1a3a5c"
        text_color = "#7effa0" if "GPU" in label else "#7ec8ff"
        self._device_badge.setStyleSheet(
            f"background-color: {color}; color: {text_color}; "
            "font-size: 10px; padding: 2px 7px; border-radius: 8px;"
        )

    def reset(self) -> None:
        self._phase_label.setText("")
        self._progress_bar.setValue(0)
        self._count_label.setText("")
        self._eta_label.setText("")
        self._cancel_btn.setVisible(False)
        self._device_badge.setVisible(False)
