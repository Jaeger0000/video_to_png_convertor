import threading
from typing import Dict, List

from PyQt5.QtCore import QThread, pyqtSignal

from app.services.dataset_service import build_dataset


class DatasetWorker(QThread):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(
        self,
        source_dir: str,
        output_dir: str,
        name: str,
        class_names: List[str],
        split_mode: str,
        train_pct: float,
        val_pct: float,
        test_pct: float,
        prefix_rules: List[Dict],
        remainder_split: str,
    ):
        super().__init__()
        self._source_dir = source_dir
        self._output_dir = output_dir
        self._name = name
        self._class_names = class_names
        self._split_mode = split_mode
        self._train_pct = train_pct
        self._val_pct = val_pct
        self._test_pct = test_pct
        self._prefix_rules = prefix_rules
        self._remainder_split = remainder_split
        self._cancel_flag = threading.Event()

    def cancel(self) -> None:
        self._cancel_flag.set()

    def run(self) -> None:
        try:
            result = build_dataset(
                source_dir=self._source_dir,
                output_dir=self._output_dir,
                name=self._name,
                class_names=self._class_names,
                split_mode=self._split_mode,
                train_pct=self._train_pct,
                val_pct=self._val_pct,
                test_pct=self._test_pct,
                prefix_rules=self._prefix_rules,
                remainder_split=self._remainder_split,
                progress_cb=lambda cur, tot: self.progress.emit(cur, tot),
                cancel_flag=self._cancel_flag,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
