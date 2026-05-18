import threading
from typing import List

from PyQt5.QtCore import QThread, pyqtSignal

from app.constants import DEFAULT_CPU_WORKERS
from app.services.sharpness_service import SharpnessService


class SharpnessWorker(QThread):
    progress = pyqtSignal(int, int)
    score_ready = pyqtSignal(int, float)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, file_paths: List[str], max_workers: int = DEFAULT_CPU_WORKERS, parent=None):
        super().__init__(parent)
        self._file_paths = file_paths
        self._max_workers = max_workers
        self._cancel_flag = threading.Event()
        self._scores: List[float] = []

    def run(self) -> None:
        try:
            total = len(self._file_paths)
            completed_count = [0]
            partial_scores = [0.0] * total

            def progress_cb(completed: int, _total: int) -> None:
                completed_count[0] = completed
                self.progress.emit(completed, total)

            scores = SharpnessService.score_batch_parallel(
                self._file_paths,
                progress_cb,
                self._cancel_flag,
                self._max_workers,
            )

            for i, score in enumerate(scores):
                self.score_ready.emit(i, score)

            if self._cancel_flag.is_set():
                self.cancelled.emit()
            else:
                self._scores = scores
                self.finished.emit(scores)

        except Exception as e:
            self.error.emit(str(e))

    def cancel(self) -> None:
        self._cancel_flag.set()
