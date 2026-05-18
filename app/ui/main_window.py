import os
import shutil
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPushButton, QSplitter, QStackedWidget,
    QStatusBar, QTextEdit, QVBoxLayout, QWidget,
)

from app.constants import APP_NAME, APP_VERSION
from app.models.frame_data import FrameData
from app.models.video_info import VideoInfo
from app.services.save_service import SaveService
from app.services.video_service import VideoService
from app.ui.dialogs.save_dialog import SaveDialog
from app.ui.gallery.gallery_widget import GalleryWidget
from app.ui.panels.dataset_prep_panel import DatasetPrepPanel
from app.ui.panels.info_panel import InfoPanel
from app.ui.panels.input_panel import InputPanel
from app.ui.panels.label_sampler_panel import LabelSamplerPanel
from app.ui.panels.label_viewer_panel import LabelViewerPanel
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
QListWidget::item { padding: 6px 8px; border-bottom: 1px solid #333; }
QListWidget::item:hover { background-color: #2a3a4a; }
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
        self.resize(1200, 860)

        self._current_video_info: Optional[VideoInfo] = None
        self._video_queue: List[str] = []
        self._current_queue_index: int = 0
        self._extraction_worker: Optional[ExtractionWorker] = None
        self._sharpness_worker: Optional[SharpnessWorker] = None
        self._errors: List[str] = []

        # Per-video results: {video_path, video_name, output_folder, frames, analyzed}
        self._completed_results: List[Dict] = []
        self._gallery_result_index: int = -1   # which result is in the gallery right now

        self.setStyleSheet(STYLESHEET)
        self._build_ui()
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

    # ──────────────────────────────────────────────── UI construction ──────

    def _build_ui(self) -> None:
        # Inner extraction stack (setup + gallery)
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_setup_page())   # page 0
        self._stack.addWidget(self._build_gallery_page()) # page 1

        # New workflow panels
        self._label_sampler = LabelSamplerPanel()
        self._label_viewer = LabelViewerPanel()
        self._dataset_prep = DatasetPrepPanel()

        # Outer stack: extraction | sampler | viewer | dataset
        self._outer_stack = QStackedWidget()
        self._outer_stack.addWidget(self._stack)          # 0
        self._outer_stack.addWidget(self._label_sampler)  # 1
        self._outer_stack.addWidget(self._label_viewer)   # 2
        self._outer_stack.addWidget(self._dataset_prep)   # 3

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._build_nav_bar())
        central_layout.addWidget(self._outer_stack)
        self.setCentralWidget(central)

    def _build_nav_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(44)
        bar.setStyleSheet(
            "QWidget { background-color: #161616; border-bottom: 1px solid #3a3a3a; }"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        nav_btn_style = (
            "QPushButton {"
            "  background-color: #2a2a2a; border: 1px solid #444;"
            "  border-radius: 3px; padding: 4px 16px; color: #bbb;"
            "  font-size: 12px;"
            "}"
            "QPushButton:hover { background-color: #3a3a3a; color: #eee; }"
            "QPushButton:checked {"
            "  background-color: #1a4a7a; border: 1px solid #2d7fbd;"
            "  color: white; font-weight: bold;"
            "}"
        )
        self._nav_buttons = []
        for label in ("Extract", "Label Sampler", "Label Viewer", "Dataset Prep"):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            btn.setStyleSheet(nav_btn_style)
            layout.addWidget(btn)
            self._nav_buttons.append(btn)

        self._nav_buttons[0].setChecked(True)
        for i, btn in enumerate(self._nav_buttons):
            btn.clicked.connect(lambda _checked, idx=i: self._switch_section(idx))

        layout.addStretch()
        return bar

    def _switch_section(self, index: int) -> None:
        self._outer_stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)

    def _build_setup_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(6, 6, 6, 6)
        page_layout.setSpacing(6)

        # ── top: left/right splitter ──────────────────────────────────────
        main_splitter = QSplitter(Qt.Horizontal)

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

        # ── completed videos list ─────────────────────────────────────────
        self._completed_box = QGroupBox("Completed Videos")
        self._completed_box.setVisible(False)
        box_layout = QVBoxLayout(self._completed_box)
        box_layout.setContentsMargins(6, 6, 6, 6)
        box_layout.setSpacing(4)

        hint = QLabel("Click a video to review and select frames  ·  Queue continues in background")
        hint.setStyleSheet("color: #777; font-size: 10px;")
        box_layout.addWidget(hint)

        self._completed_list = QListWidget()
        self._completed_list.setMaximumHeight(180)
        self._completed_list.itemClicked.connect(self._on_completed_item_clicked)
        box_layout.addWidget(self._completed_list)

        page_layout.addWidget(self._completed_box)

        # ── error log ─────────────────────────────────────────────────────
        self._error_toggle_btn = QPushButton("Show Error Log (0)")
        self._error_toggle_btn.setCheckable(True)
        self._error_toggle_btn.setChecked(False)
        self._error_toggle_btn.toggled.connect(self._toggle_error_log)
        page_layout.addWidget(self._error_toggle_btn)

        self._error_log = QTextEdit()
        self._error_log.setReadOnly(True)
        self._error_log.setMaximumHeight(90)
        self._error_log.setVisible(False)
        page_layout.addWidget(self._error_log)

        return page

    def _build_gallery_page(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        self._btn_back = QPushButton("← Back to Queue")
        self._btn_back.setFixedWidth(150)
        self._btn_back.clicked.connect(self._go_back_to_setup)
        self._gallery_title = QLabel("")
        self._gallery_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #ddd;")
        top_row.addWidget(self._btn_back)
        top_row.addSpacing(12)
        top_row.addWidget(self._gallery_title)
        top_row.addStretch()

        self._btn_dismiss = QPushButton("Dismiss (delete raw)")
        self._btn_dismiss.setFixedWidth(170)
        self._btn_dismiss.setStyleSheet(
            "QPushButton { background-color: #5a2a2a; color: #ffaaaa; "
            "border: 1px solid #7a3a3a; border-radius: 3px; padding: 4px 10px; }"
            "QPushButton:hover { background-color: #7a3a3a; }"
        )
        self._btn_dismiss.setToolTip("Delete all raw frames for this video without saving")
        self._btn_dismiss.clicked.connect(self._on_dismiss_requested)
        top_row.addWidget(self._btn_dismiss)

        layout.addLayout(top_row)

        self._gallery = GalleryWidget()
        self._gallery.save_requested.connect(self._on_save_requested)
        layout.addWidget(self._gallery)

        return container

    # ──────────────────────────────────────────────── video probing ────────

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

    # ──────────────────────────────────────────────── queue control ────────

    def _on_start_conversion(self, config) -> None:
        if self._extraction_worker and self._extraction_worker.isRunning():
            return
        paths = self._input_panel.get_all_paths()
        if not paths:
            QMessageBox.warning(self, "No Videos", "Please add at least one video first.")
            return
        self._video_queue = paths
        self._current_queue_index = 0
        self._completed_results.clear()
        self._completed_list.clear()
        self._completed_box.setVisible(False)
        self._settings_panel.set_enabled(False)
        self._start_next_in_queue()

    def _start_next_in_queue(self) -> None:
        if self._current_queue_index >= len(self._video_queue):
            self._settings_panel.set_enabled(True)
            self._progress_panel.reset()
            n = len(self._completed_results)
            self._status_bar.showMessage(f"All done — {n} video{'s' if n != 1 else ''} ready to review.")
            return

        path = self._video_queue[self._current_queue_index]
        total = len(self._video_queue)
        self._status_bar.showMessage(
            f"Processing {self._current_queue_index + 1} / {total} — {os.path.basename(path)}"
        )

        try:
            if path != (self._current_video_info.file_path if self._current_video_info else None):
                self._probe_video(path)
            config = self._settings_panel.build_config(path)
        except Exception as e:
            self._log_error(f"Config error for {os.path.basename(path)}: {e}")
            self._advance_queue()
            return

        self._progress_panel.set_phase(
            f"Extracting  [{self._current_queue_index + 1}/{total}]  {os.path.basename(path)}"
        )
        self._extraction_worker = ExtractionWorker(config)
        self._extraction_worker.progress.connect(self._progress_panel.update_progress)
        self._extraction_worker.eta_updated.connect(self._progress_panel.update_eta)
        self._extraction_worker.finished.connect(self._on_extraction_finished)
        self._extraction_worker.error.connect(self._on_extraction_error)
        self._extraction_worker.cancelled.connect(self._on_extraction_cancelled)
        self._extraction_worker.start()

    def _advance_queue(self) -> None:
        self._current_queue_index += 1
        self._progress_panel.reset()
        self._start_next_in_queue()

    def _on_cancel(self) -> None:
        if self._extraction_worker and self._extraction_worker.isRunning():
            self._extraction_worker.cancel()
        if self._sharpness_worker and self._sharpness_worker.isRunning():
            self._sharpness_worker.cancel()

    # ──────────────────────────────────────────── extraction callbacks ─────

    def _on_extraction_finished(self, paths: List[str]) -> None:
        video_path = self._video_queue[self._current_queue_index]
        video_name = os.path.splitext(os.path.basename(video_path))[0]

        if not paths:
            self._log_error(f"No frames extracted from {video_name}")
            self._advance_queue()
            return

        config = self._extraction_worker._config if self._extraction_worker else None
        extraction_fps = config.extraction_fps if config else 1.0
        output_folder = config.output_folder if config else ""

        frames = [
            FrameData(
                frame_index=i,
                source_frame_number=i,
                timestamp_seconds=i / extraction_fps,
                file_path=p,
                sharpness_score=0.0,
                is_selected=True,
            )
            for i, p in enumerate(paths)
        ]

        result = {
            "video_path": video_path,
            "video_name": video_name,
            "output_folder": output_folder,
            "frames": frames,
            "analyzed": False,
        }
        result_index = len(self._completed_results)
        self._completed_results.append(result)
        self._add_completed_item(result_index, analyzing=True)

        total = len(self._video_queue)
        self._progress_panel.set_phase(
            f"Analyzing  [{self._current_queue_index + 1}/{total}]  {video_name}"
        )
        self._sharpness_worker = SharpnessWorker(paths)
        self._sharpness_worker.score_ready.connect(
            lambda idx, score, ri=result_index: self._on_score_ready(ri, idx, score)
        )
        self._sharpness_worker.progress.connect(self._progress_panel.update_progress)
        self._sharpness_worker.device_detected.connect(self._progress_panel.set_device)
        self._sharpness_worker.finished.connect(
            lambda scores, ri=result_index: self._on_sharpness_finished(ri, scores)
        )
        self._sharpness_worker.error.connect(self._on_sharpness_error)
        self._sharpness_worker.start()

    def _on_score_ready(self, result_index: int, frame_index: int, score: float) -> None:
        result = self._completed_results[result_index]
        if frame_index < len(result["frames"]):
            result["frames"][frame_index].sharpness_score = score
        # If this result is currently open in gallery, push live update
        if self._gallery_result_index == result_index:
            self._gallery.update_one_score(frame_index, score)

    def _on_sharpness_finished(self, result_index: int, scores: List[float]) -> None:
        result = self._completed_results[result_index]
        for i, score in enumerate(scores):
            if i < len(result["frames"]):
                result["frames"][i].sharpness_score = score
        result["analyzed"] = True
        self._update_completed_item(result_index)

        # If gallery is open for this result, do a full chart refresh
        if self._gallery_result_index == result_index:
            self._gallery.update_all_scores(scores)

        self._progress_panel.reset()
        self._advance_queue()

    def _on_sharpness_error(self, msg: str) -> None:
        self._log_error(f"Sharpness analysis error: {msg}")
        self._progress_panel.reset()
        self._advance_queue()

    def _on_extraction_error(self, msg: str) -> None:
        video_name = os.path.basename(self._video_queue[self._current_queue_index])
        self._log_error(f"Extraction error for {video_name}: {msg}")
        self._advance_queue()

    def _on_extraction_cancelled(self) -> None:
        self._progress_panel.reset()
        self._settings_panel.set_enabled(True)
        self._status_bar.showMessage("Cancelled.")

    # ──────────────────────────────────────── completed list management ────

    def _add_completed_item(self, result_index: int, analyzing: bool) -> None:
        result = self._completed_results[result_index]
        n = len(result["frames"])
        text = (
            f"⏳  {result['video_name']}   —   {n:,} frames   —   Analyzing sharpness…"
            if analyzing else
            f"✓   {result['video_name']}   —   {n:,} frames   —   Click to review"
        )
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, result_index)
        if not analyzing:
            item.setForeground(Qt.white)
        else:
            item.setForeground(Qt.darkGray)   # type: ignore[arg-type]
        self._completed_list.addItem(item)
        self._completed_box.setVisible(True)

    def _update_completed_item(self, result_index: int) -> None:
        result = self._completed_results[result_index]
        n = len(result["frames"])
        for i in range(self._completed_list.count()):
            item = self._completed_list.item(i)
            if item.data(Qt.UserRole) == result_index:
                item.setText(f"✓   {result['video_name']}   —   {n:,} frames   —   Click to review")
                item.setForeground(Qt.white)   # type: ignore[arg-type]
                break

    def _on_completed_item_clicked(self, item: QListWidgetItem) -> None:
        result_index = item.data(Qt.UserRole)
        result = self._completed_results[result_index]
        if not result["analyzed"]:
            self._status_bar.showMessage("Sharpness analysis still running — you can already browse frames.")
        self._open_result_in_gallery(result_index)

    def _open_result_in_gallery(self, result_index: int) -> None:
        result = self._completed_results[result_index]
        self._gallery_result_index = result_index
        self._gallery_title.setText(result["video_name"])
        self._gallery.load_frames(result["frames"])
        self._stack.setCurrentIndex(1)

    # ──────────────────────────────────────────────── gallery / save ───────

    def _go_back_to_setup(self) -> None:
        self._gallery_result_index = -1
        self._stack.setCurrentIndex(0)

    def _on_save_requested(self) -> None:
        if self._gallery_result_index < 0:
            return
        result = self._completed_results[self._gallery_result_index]
        frames = result["frames"]
        selected = [f for f in frames if f.is_selected]
        if not selected:
            QMessageBox.information(self, "Nothing to Save", "No frames are selected.")
            return

        raw_folder = result["output_folder"]
        selected_folder = raw_folder.replace(
            os.sep + "raw_frames" + os.sep,
            os.sep + "frames" + os.sep,
            1,
        )
        if selected_folder == raw_folder:
            selected_folder = raw_folder + "_selected"

        dialog = SaveDialog(len(selected), selected_folder, self)
        if dialog.exec_() != dialog.Accepted:
            return

        choices = dialog.get_choices()
        try:
            if choices["save_frames"]:
                count = SaveService.save_selected_frames(frames, selected_folder)
                self._status_bar.showMessage(f"Saved {count:,} frames → {selected_folder}")

            if choices["save_clip"]:
                clip_path = SaveService.save_video_clip(
                    result["video_path"], selected_folder, frames
                )
                self._status_bar.showMessage(
                    self._status_bar.currentMessage() + f"  |  clip: {os.path.basename(clip_path)}"
                )

            self._delete_raw_folder(result["output_folder"])
            self._remove_completed_item(self._gallery_result_index)
            # Update label sampler source to the frames/ root when a save completes
            frames_root = os.path.dirname(selected_folder)
            if os.path.isdir(frames_root):
                self._label_sampler.set_source_folder(frames_root)
            self._go_back_to_setup()
            QMessageBox.information(
                self, "Save Complete",
                f"Saved {len(selected):,} frames to:\n{selected_folder}\n\nRaw frames deleted."
            )
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))
            self._log_error(f"Save error: {e}")

    def _on_dismiss_requested(self) -> None:
        if self._gallery_result_index < 0:
            return
        result = self._completed_results[self._gallery_result_index]
        reply = QMessageBox.question(
            self, "Dismiss",
            f"Delete all raw frames for '{result['video_name']}'?\n"
            f"Folder: {result['output_folder']}\n\n"
            "Selected frames will NOT be saved.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._delete_raw_folder(result["output_folder"])
        self._remove_completed_item(self._gallery_result_index)
        self._go_back_to_setup()
        self._status_bar.showMessage(f"Dismissed — raw frames deleted: {result['video_name']}")

    def _delete_raw_folder(self, folder: str) -> None:
        if folder and os.path.isdir(folder):
            try:
                shutil.rmtree(folder)
            except Exception as e:
                self._log_error(f"Could not delete raw folder {folder}: {e}")

    def _remove_completed_item(self, result_index: int) -> None:
        for i in range(self._completed_list.count()):
            if self._completed_list.item(i).data(Qt.UserRole) == result_index:
                self._completed_list.takeItem(i)
                break
        if self._completed_list.count() == 0:
            self._completed_box.setVisible(False)

    # ──────────────────────────────────────────────── error log ───────────

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
