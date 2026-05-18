import os
from typing import List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSplitter, QStackedWidget, QStatusBar,
    QTextEdit, QVBoxLayout, QWidget,
)

from app.constants import APP_NAME, APP_VERSION
from app.models.frame_data import FrameData
from app.models.video_info import VideoInfo
from app.services.save_service import SaveService
from app.services.video_service import VideoService
from app.ui.dialogs.save_dialog import SaveDialog
from app.ui.gallery.gallery_widget import GalleryWidget
from app.ui.panels.info_panel import InfoPanel
from app.ui.panels.input_panel import InputPanel
from app.ui.panels.progress_panel import ProgressPanel
from app.ui.panels.settings_panel import SettingsPanel
from app.workers.extraction_worker import ExtractionWorker
from app.workers.sharpness_worker import SharpnessWorker


STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 12px;
}
QGroupBox {
    border: 1px solid #444;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 4px;
}
QGroupBox::title {
    color: #aaa;
    subcontrol-origin: margin;
    left: 8px;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTimeEdit {
    background-color: #2d2d2d;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 3px 6px;
    color: #e0e0e0;
}
QPushButton {
    background-color: #3a3a3a;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 4px 10px;
    color: #e0e0e0;
}
QPushButton:hover { background-color: #4a4a4a; }
QPushButton:disabled { color: #666; background-color: #2a2a2a; }
QProgressBar {
    border: 1px solid #555;
    border-radius: 3px;
    text-align: center;
    background-color: #2d2d2d;
}
QProgressBar::chunk { background-color: #2d7d46; }
QListWidget {
    background-color: #252525;
    border: 1px solid #444;
    border-radius: 3px;
}
QListWidget::item:selected { background-color: #1a5276; }
QScrollBar:vertical {
    background: #2a2a2a; width: 10px; border-radius: 5px;
}
QScrollBar::handle:vertical { background: #555; border-radius: 5px; }
QTextEdit {
    background-color: #1a1a1a;
    border: 1px solid #444;
    color: #f08080;
    font-family: monospace;
    font-size: 11px;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1200, 800)

        self._current_video_info: Optional[VideoInfo] = None
        self._video_queue: List[str] = []
        self._current_queue_index: int = 0
        self._extraction_worker: Optional[ExtractionWorker] = None
        self._sharpness_worker: Optional[SharpnessWorker] = None
        self._extracted_paths: List[str] = []
        self._frames: List[FrameData] = []
        self._errors: List[str] = []

        self.setStyleSheet(STYLESHEET)
        self._build_ui()
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

    def _build_ui(self) -> None:
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Page 0: setup
        self._stack.addWidget(self._build_setup_page())

        # Page 1: gallery
        gallery_container = QWidget()
        gc_layout = QVBoxLayout(gallery_container)
        gc_layout.setContentsMargins(4, 4, 4, 4)
        gc_layout.setSpacing(4)

        self._btn_back = QPushButton("← Back to Settings")
        self._btn_back.setFixedWidth(160)
        self._btn_back.clicked.connect(self._go_back_to_setup)
        gc_layout.addWidget(self._btn_back)

        self._gallery = GalleryWidget()
        self._gallery.save_requested.connect(self._on_save_requested)
        gc_layout.addWidget(self._gallery)

        self._stack.addWidget(gallery_container)

    def _build_setup_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(6, 6, 6, 6)
        page_layout.setSpacing(6)

        main_splitter = QSplitter(Qt.Horizontal)

        # Left side
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self._input_panel = InputPanel()
        self._input_panel.videos_loaded.connect(self._on_videos_loaded)
        self._input_panel.video_selected.connect(self._on_video_selected)
        left_layout.addWidget(self._input_panel)

        self._info_panel = InfoPanel()
        left_layout.addWidget(self._info_panel)

        left_layout.addStretch()
        main_splitter.addWidget(left)

        # Right side
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        self._settings_panel = SettingsPanel()
        self._settings_panel.start_conversion_requested.connect(self._on_start_conversion)
        right_layout.addWidget(self._settings_panel)

        self._progress_panel = ProgressPanel()
        self._progress_panel.cancel_requested.connect(self._on_cancel)
        right_layout.addWidget(self._progress_panel)

        right_layout.addStretch()
        main_splitter.addWidget(right)

        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)

        page_layout.addWidget(main_splitter)

        # Error log (collapsible)
        self._error_toggle_btn = QPushButton("Show Error Log (0)")
        self._error_toggle_btn.setCheckable(True)
        self._error_toggle_btn.setChecked(False)
        self._error_toggle_btn.toggled.connect(self._toggle_error_log)
        page_layout.addWidget(self._error_toggle_btn)

        self._error_log = QTextEdit()
        self._error_log.setReadOnly(True)
        self._error_log.setMaximumHeight(100)
        self._error_log.setVisible(False)
        page_layout.addWidget(self._error_log)

        return page

    def _on_videos_loaded(self, paths: List[str]) -> None:
        if paths and not self._current_video_info:
            self._probe_video(paths[0])

    def _on_video_selected(self, path: str) -> None:
        self._probe_video(path)

    def _probe_video(self, path: str) -> None:
        try:
            info = VideoService.probe(path)
            self._current_video_info = info
            self._info_panel.display(info)
            self._settings_panel.set_video_info(info)
        except Exception as e:
            self._log_error(f"Probe failed for {os.path.basename(path)}: {e}")

    def _on_start_conversion(self, config) -> None:
        if self._extraction_worker and self._extraction_worker.isRunning():
            return

        paths = self._input_panel.get_all_paths()
        if not paths:
            QMessageBox.warning(self, "No Videos", "Please add at least one video first.")
            return

        self._video_queue = paths
        self._current_queue_index = 0
        self._settings_panel.set_enabled(False)
        self._start_next_in_queue()

    def _start_next_in_queue(self) -> None:
        if self._current_queue_index >= len(self._video_queue):
            self._settings_panel.set_enabled(True)
            self._progress_panel.reset()
            self._status_bar.showMessage("All videos processed.")
            return

        path = self._video_queue[self._current_queue_index]
        total = len(self._video_queue)
        self._status_bar.showMessage(
            f"Video {self._current_queue_index + 1} / {total} — {os.path.basename(path)}"
        )

        try:
            if path != (self._current_video_info.file_path if self._current_video_info else None):
                self._probe_video(path)
            config = self._settings_panel.build_config(path)
        except Exception as e:
            self._log_error(f"Config error for {os.path.basename(path)}: {e}")
            self._advance_queue()
            return

        self._progress_panel.set_phase("Extracting frames...")
        self._extraction_worker = ExtractionWorker(config)
        self._extraction_worker.progress.connect(self._progress_panel.update_progress)
        self._extraction_worker.eta_updated.connect(self._progress_panel.update_eta)
        self._extraction_worker.finished.connect(self._on_extraction_finished)
        self._extraction_worker.error.connect(self._on_extraction_error)
        self._extraction_worker.cancelled.connect(self._on_extraction_cancelled)
        self._extraction_worker.start()

    def _on_extraction_finished(self, paths: List[str]) -> None:
        self._extracted_paths = paths

        if not paths:
            self._log_error(
                f"No frames extracted from "
                f"{os.path.basename(self._video_queue[self._current_queue_index])}"
            )
            self._advance_queue()
            return

        video_fps = self._current_video_info.fps if self._current_video_info else 25.0
        src_path = self._video_queue[self._current_queue_index]

        self._frames = []
        config = self._extraction_worker._config if self._extraction_worker else None
        extraction_fps = config.extraction_fps if config else 1.0
        for i, p in enumerate(paths):
            ts = i / extraction_fps
            self._frames.append(FrameData(
                frame_index=i,
                source_frame_number=i,
                timestamp_seconds=ts,
                file_path=p,
                sharpness_score=0.0,
                is_selected=True,
            ))

        self._stack.setCurrentIndex(1)
        self._gallery.load_frames(self._frames)

        self._progress_panel.set_phase("Analyzing sharpness...")
        self._sharpness_worker = SharpnessWorker(paths)
        self._sharpness_worker.score_ready.connect(self._on_score_ready)
        self._sharpness_worker.progress.connect(self._progress_panel.update_progress)
        self._sharpness_worker.device_detected.connect(self._progress_panel.set_device)
        self._sharpness_worker.finished.connect(self._on_sharpness_finished)
        self._sharpness_worker.error.connect(self._on_sharpness_error)
        self._sharpness_worker.start()

    def _on_score_ready(self, frame_index: int, score: float) -> None:
        self._gallery.update_one_score(frame_index, score)

    def _on_sharpness_finished(self, scores) -> None:
        self._progress_panel.reset()
        self._gallery.update_all_scores(scores)
        self._status_bar.showMessage(
            f"Done. {len(self._frames):,} frames extracted and analyzed."
        )

    def _on_sharpness_error(self, msg: str) -> None:
        self._log_error(f"Sharpness analysis error: {msg}")
        self._progress_panel.reset()

    def _on_extraction_error(self, msg: str) -> None:
        self._log_error(
            f"Extraction error for "
            f"{os.path.basename(self._video_queue[self._current_queue_index])}: {msg}"
        )
        self._advance_queue()

    def _on_extraction_cancelled(self) -> None:
        self._progress_panel.reset()
        self._settings_panel.set_enabled(True)
        self._status_bar.showMessage("Extraction cancelled.")

    def _advance_queue(self) -> None:
        self._current_queue_index += 1
        self._progress_panel.reset()
        self._start_next_in_queue()

    def _on_cancel(self) -> None:
        if self._extraction_worker and self._extraction_worker.isRunning():
            self._extraction_worker.cancel()
        if self._sharpness_worker and self._sharpness_worker.isRunning():
            self._sharpness_worker.cancel()

    def _on_save_requested(self) -> None:
        frames = self._gallery.get_frames()
        selected = [f for f in frames if f.is_selected]
        if not selected:
            QMessageBox.information(self, "Nothing to Save", "No frames are selected.")
            return

        dialog = SaveDialog(len(selected), self)
        if dialog.exec_() != dialog.Accepted:
            return

        choices = dialog.get_choices()
        output_folder = QFileDialog.getExistingDirectory(self, "Select Save Folder")
        if not output_folder:
            return

        try:
            if choices["save_frames"]:
                count = SaveService.save_selected_frames(frames, output_folder)
                self._status_bar.showMessage(f"Saved {count:,} frames to {output_folder}")

            if choices["save_clip"] and self._current_video_info:
                clip_path = SaveService.save_video_clip(
                    self._current_video_info.file_path, output_folder, frames
                )
                self._status_bar.showMessage(
                    self._status_bar.currentMessage() + f" | Clip: {os.path.basename(clip_path)}"
                )

            QMessageBox.information(self, "Save Complete", "Files saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))
            self._log_error(f"Save error: {e}")

    def _go_back_to_setup(self) -> None:
        if (self._extraction_worker and self._extraction_worker.isRunning()) or \
           (self._sharpness_worker and self._sharpness_worker.isRunning()):
            reply = QMessageBox.question(
                self, "Processing in Progress",
                "Analysis is still running. Go back anyway?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.No:
                return
            self._on_cancel()
        self._stack.setCurrentIndex(0)

    def _log_error(self, msg: str) -> None:
        self._errors.append(msg)
        self._error_log.append(msg)
        self._error_toggle_btn.setText(f"Show Error Log ({len(self._errors)})")
        if not self._error_toggle_btn.isChecked():
            self._error_toggle_btn.setChecked(True)

    def _toggle_error_log(self, visible: bool) -> None:
        self._error_log.setVisible(visible)

    def closeEvent(self, event) -> None:
        self._on_cancel()
        if self._extraction_worker:
            self._extraction_worker.wait(3000)
        if self._sharpness_worker:
            self._sharpness_worker.wait(3000)
        event.accept()
