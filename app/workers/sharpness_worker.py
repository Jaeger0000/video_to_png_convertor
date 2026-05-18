import threading
from typing import List

from PyQt5.QtCore import QThread, pyqtSignal

from app.constants import DEFAULT_CPU_WORKERS
from app.services.sharpness_service import SharpnessService


class SharpnessWorker(QThread):
    progress = pyqtSignal(int, int)
    score_ready = pyqtSignal(int, float)
    device_detected = pyqtSignal(str)   # e.g. "CUDA (RTX 3080)" / "CPU · 8 cores"
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
            device = SharpnessService.best_device()
            device_label = self._make_device_label(device)
            self.device_detected.emit(device_label)

            total = len(self._file_paths)

            def progress_cb(completed: int, _total: int) -> None:
                self.progress.emit(completed, total)

            if device in ("cuda", "mps"):
                scores = SharpnessService.score_batch_gpu(
                    self._file_paths,
                    progress_cb,
                    self._cancel_flag,
                    device=device,
                    io_workers=self._max_workers,
                )
            else:
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

    @staticmethod
    def _make_device_label(device: str) -> str:
        if device == "cuda":
            try:
                import torch
                name = torch.cuda.get_device_name(0)
                return f"GPU · CUDA ({name})"
            except Exception:
                return "GPU · CUDA"
        if device == "mps":
            return "GPU · MPS (Apple Silicon)"
        import os
        cores = os.cpu_count() or 1
        return f"CPU · {cores} cores"
