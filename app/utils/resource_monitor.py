from PyQt5.QtCore import QObject, QTimer, pyqtSignal


class ResourceMonitor(QObject):
    # cpu_pct, gpu_pct, gpu_mem_used_gb, gpu_mem_total_gb
    stats_updated = pyqtSignal(float, float, float, float)

    def __init__(self, interval_ms: int = 1000, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._poll)
        self._nvml_handle = None
        self._init_nvml()

    def _init_nvml(self) -> None:
        try:
            import pynvml
            pynvml.nvmlInit()
            self._nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:
            self._nvml_handle = None

    def has_gpu(self) -> bool:
        return self._nvml_handle is not None

    def start(self) -> None:
        try:
            import psutil
            psutil.cpu_percent(interval=None)   # prime — first call always returns 0
        except ImportError:
            pass
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _poll(self) -> None:
        cpu = self._cpu_percent()
        gpu_pct, mem_used, mem_total = self._gpu_stats()
        self.stats_updated.emit(cpu, gpu_pct, mem_used, mem_total)

    def _cpu_percent(self) -> float:
        try:
            import psutil
            return float(psutil.cpu_percent(interval=None))
        except Exception:
            return 0.0

    def _gpu_stats(self):
        if self._nvml_handle is None:
            return 0.0, 0.0, 0.0
        try:
            import pynvml
            util = pynvml.nvmlDeviceGetUtilizationRates(self._nvml_handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(self._nvml_handle)
            return (
                float(util.gpu),
                mem.used / 1024 ** 3,
                mem.total / 1024 ** 3,
            )
        except Exception:
            return 0.0, 0.0, 0.0
