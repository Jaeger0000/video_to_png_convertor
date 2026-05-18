import os

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider, QSpinBox,
    QTimeEdit, QVBoxLayout, QWidget,
)
from PyQt5.QtCore import QTime, Qt

from app.constants import (
    DEFAULT_EXTRACTION_FPS, DEFAULT_FILENAME_PREFIX,
    DEFAULT_JPEG_QUALITY, DEFAULT_RESOLUTION_MULTIPLIER,
)
from app.models.extraction_config import ExtractionConfig
from app.models.video_info import VideoInfo


class SettingsPanel(QWidget):
    start_conversion_requested = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_video_info: VideoInfo = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel("Conversion Settings")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(6)

        # Frame rate
        fps_row = QHBoxLayout()
        self._fps_spin = QDoubleSpinBox()
        self._fps_spin.setRange(0.01, 999.0)
        self._fps_spin.setSingleStep(0.5)
        self._fps_spin.setValue(DEFAULT_EXTRACTION_FPS)
        self._fps_spin.setDecimals(2)
        self._fps_spin.setSuffix(" fps")
        self._btn_use_original = QPushButton("Use Original")
        self._btn_use_original.setFixedWidth(100)
        self._btn_use_original.clicked.connect(self._use_original_fps)
        fps_row.addWidget(self._fps_spin)
        fps_row.addWidget(self._btn_use_original)
        form.addRow("Frame Rate:", fps_row)

        # Image format
        self._format_combo = QComboBox()
        self._format_combo.addItems(["PNG", "JPEG"])
        self._format_combo.currentTextChanged.connect(self._on_format_changed)
        form.addRow("Format:", self._format_combo)

        # JPEG quality
        quality_row = QHBoxLayout()
        self._quality_slider = QSlider(Qt.Horizontal)
        self._quality_slider.setRange(1, 95)
        self._quality_slider.setValue(DEFAULT_JPEG_QUALITY)
        self._quality_label = QLabel(str(DEFAULT_JPEG_QUALITY))
        self._quality_slider.valueChanged.connect(
            lambda v: self._quality_label.setText(str(v))
        )
        quality_row.addWidget(self._quality_slider)
        quality_row.addWidget(self._quality_label)
        self._quality_row_widget = QWidget()
        self._quality_row_widget.setLayout(quality_row)
        self._quality_row_widget.setVisible(False)
        form.addRow("JPEG Quality:", self._quality_row_widget)

        # Filename prefix
        self._prefix_input = QLineEdit(DEFAULT_FILENAME_PREFIX)
        form.addRow("Filename Prefix:", self._prefix_input)

        # Time range
        time_row = QHBoxLayout()
        self._start_time = QTimeEdit()
        self._start_time.setDisplayFormat("HH:mm:ss")
        self._end_time = QTimeEdit()
        self._end_time.setDisplayFormat("HH:mm:ss")
        time_row.addWidget(QLabel("Start:"))
        time_row.addWidget(self._start_time)
        time_row.addWidget(QLabel("End:"))
        time_row.addWidget(self._end_time)
        form.addRow("Time Range:", time_row)

        # Resolution multiplier
        self._resolution_spin = QDoubleSpinBox()
        self._resolution_spin.setRange(0.1, 4.0)
        self._resolution_spin.setSingleStep(0.1)
        self._resolution_spin.setValue(DEFAULT_RESOLUTION_MULTIPLIER)
        self._resolution_spin.setDecimals(1)
        self._resolution_spin.setSuffix("×")
        form.addRow("Resolution:", self._resolution_spin)

        # Output folder
        folder_row = QHBoxLayout()
        self._output_folder_input = QLineEdit()
        self._output_folder_input.setPlaceholderText("Select output folder...")
        self._btn_browse_output = QPushButton("Browse")
        self._btn_browse_output.setFixedWidth(70)
        self._btn_browse_output.clicked.connect(self._browse_output_folder)
        folder_row.addWidget(self._output_folder_input)
        folder_row.addWidget(self._btn_browse_output)
        form.addRow("Output Folder:", folder_row)

        layout.addLayout(form)
        layout.addSpacing(8)

        self._btn_start = QPushButton("Start Conversion")
        self._btn_start.setStyleSheet(
            "QPushButton { background-color: #2d7d46; color: white; "
            "font-weight: bold; padding: 8px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #3a9e5c; }"
            "QPushButton:disabled { background-color: #555; }"
        )
        self._btn_start.clicked.connect(self._on_start_clicked)
        layout.addWidget(self._btn_start)
        layout.addStretch()

    def _on_format_changed(self, text: str) -> None:
        self._quality_row_widget.setVisible(text == "JPEG")

    def _use_original_fps(self) -> None:
        if self._current_video_info and self._current_video_info.fps > 0:
            self._fps_spin.setValue(self._current_video_info.fps)

    def _browse_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self._output_folder_input.setText(folder)

    def _on_start_clicked(self) -> None:
        config = self.build_config()
        if config:
            self.start_conversion_requested.emit(config)

    def set_video_info(self, info: VideoInfo) -> None:
        self._current_video_info = info
        duration_secs = int(info.duration_seconds)
        max_time = QTime(duration_secs // 3600, (duration_secs % 3600) // 60, duration_secs % 60)
        self._end_time.setMaximumTime(max_time)
        self._start_time.setMaximumTime(max_time)
        self._end_time.setTime(max_time)
        self._start_time.setTime(QTime(0, 0, 0))

    def build_config(self, video_path: str = None) -> ExtractionConfig:
        if video_path is None and self._current_video_info:
            video_path = self._current_video_info.file_path
        if not video_path:
            return None
        output_folder = self._output_folder_input.text().strip()
        if not output_folder:
            output_folder = os.path.join(
                os.path.dirname(video_path),
                "frames_" + os.path.splitext(os.path.basename(video_path))[0],
            )
        start_t = self._start_time.time()
        end_t = self._end_time.time()
        start_s = start_t.hour() * 3600 + start_t.minute() * 60 + start_t.second()
        end_s = end_t.hour() * 3600 + end_t.minute() * 60 + end_t.second()
        return ExtractionConfig(
            source_video_path=video_path,
            output_folder=output_folder,
            output_format=self._format_combo.currentText(),
            jpeg_quality=self._quality_slider.value(),
            filename_prefix=self._prefix_input.text().strip() or DEFAULT_FILENAME_PREFIX,
            extraction_fps=self._fps_spin.value(),
            start_time_seconds=float(start_s),
            end_time_seconds=float(end_s) if end_s > start_s else 0.0,
            resolution_multiplier=self._resolution_spin.value(),
        )

    def set_enabled(self, enabled: bool) -> None:
        self._btn_start.setEnabled(enabled)
        self._fps_spin.setEnabled(enabled)
        self._format_combo.setEnabled(enabled)
        self._prefix_input.setEnabled(enabled)
