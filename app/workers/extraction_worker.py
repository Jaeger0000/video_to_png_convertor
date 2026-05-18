import os
import threading
import time
from typing import List

from PyQt5.QtCore import QThread, pyqtSignal

from app.models.extraction_config import ExtractionConfig
from app.services.video_service import VideoService


class ExtractionWorker(QThread):
    progress = pyqtSignal(int, int)
    eta_updated = pyqtSignal(float)
    frame_extracted = pyqtSignal(str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, config: ExtractionConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._cancel_flag = threading.Event()
        self._saved_paths: List[str] = []

    def run(self) -> None:
        try:
            start_time = time.monotonic()
            last_count = [0]

            def progress_cb(current: int, total: int) -> None:
                if self._cancel_flag.is_set():
                    return
                last_count[0] = current
                self.progress.emit(current, total)
                self.frame_extracted.emit(
                    f"{self._config.filename_prefix}_{current - 1:06d}"
                )
                elapsed = time.monotonic() - start_time
                if current > 0:
                    eta = elapsed / current * (total - current)
                    self.eta_updated.emit(eta)

            paths = VideoService.extract_frames(
                self._config, progress_cb, self._cancel_flag
            )
            self._saved_paths = paths

            if self._cancel_flag.is_set():
                self._cleanup_partial(paths)
                self.cancelled.emit()
            else:
                self.finished.emit(paths)

        except Exception as e:
            self.error.emit(str(e))

    def cancel(self) -> None:
        self._cancel_flag.set()

    def _cleanup_partial(self, paths: List[str]) -> None:
        for p in paths:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
