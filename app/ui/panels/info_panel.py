from PyQt5.QtWidgets import QFormLayout, QLabel, QWidget

from app.models.video_info import VideoInfo
from app.utils.format_utils import bytes_to_human, kbps_to_human
from app.utils.time_utils import seconds_to_hms


class InfoPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._labels = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel("Video Information")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addRow(title)

        fields = [
            ("file", "File"),
            ("resolution", "Resolution"),
            ("fps", "Frame Rate"),
            ("duration", "Duration"),
            ("frames", "Total Frames"),
            ("size", "File Size"),
            ("bitrate", "Bitrate"),
            ("codec", "Codec"),
        ]
        for key, label in fields:
            lbl = QLabel("—")
            lbl.setWordWrap(True)
            self._labels[key] = lbl
            layout.addRow(f"{label}:", lbl)

    def display(self, info: VideoInfo) -> None:
        self._labels["file"].setText(info.file_name)
        self._labels["resolution"].setText(f"{info.width} × {info.height}")
        self._labels["fps"].setText(f"{info.fps:.3f} fps")
        self._labels["duration"].setText(seconds_to_hms(info.duration_seconds))
        self._labels["frames"].setText(f"{info.total_frames:,}")
        self._labels["size"].setText(bytes_to_human(info.file_size_bytes))
        self._labels["bitrate"].setText(kbps_to_human(info.bitrate_kbps))
        self._labels["codec"].setText(info.codec or "unknown")

    def clear(self) -> None:
        for lbl in self._labels.values():
            lbl.setText("—")
