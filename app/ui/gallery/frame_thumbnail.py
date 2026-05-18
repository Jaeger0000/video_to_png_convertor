from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPixmap
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout

from app.constants import THUMBNAIL_SIZE_PX
from app.models.frame_data import FrameData


class FrameThumbnailWidget(QFrame):
    toggled = pyqtSignal(int, bool)

    def __init__(self, frame_data: FrameData, parent=None):
        super().__init__(parent)
        self._frame_data = frame_data
        self._build_ui()
        self._update_border()

    def _build_ui(self) -> None:
        self.setFixedSize(THUMBNAIL_SIZE_PX + 12, THUMBNAIL_SIZE_PX + 48)
        self.setFrameShape(QFrame.Box)
        self.setLineWidth(2)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._img_label = QLabel()
        self._img_label.setFixedSize(THUMBNAIL_SIZE_PX, THUMBNAIL_SIZE_PX)
        self._img_label.setAlignment(Qt.AlignCenter)
        self._img_label.setStyleSheet("background-color: #2a2a2a;")
        placeholder = QPixmap(THUMBNAIL_SIZE_PX, THUMBNAIL_SIZE_PX)
        placeholder.fill(QColor("#2a2a2a"))
        self._img_label.setPixmap(placeholder)
        layout.addWidget(self._img_label)

        self._frame_label = QLabel(f"F-{self._frame_data.frame_index:06d}")
        self._frame_label.setAlignment(Qt.AlignCenter)
        self._frame_label.setStyleSheet("font-size: 10px; color: #ccc;")
        layout.addWidget(self._frame_label)

        score = self._frame_data.sharpness_score
        score_text = f"{score:.1f}" if score > 0 else "—"
        self._sharp_label = QLabel(f"Sharp: {score_text}")
        self._sharp_label.setAlignment(Qt.AlignCenter)
        self._sharp_label.setStyleSheet("font-size: 10px; color: #aaa;")
        layout.addWidget(self._sharp_label)

    def set_pixmap(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(
            THUMBNAIL_SIZE_PX, THUMBNAIL_SIZE_PX,
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        self._img_label.setPixmap(scaled)

    def set_sharpness(self, score: float) -> None:
        self._frame_data.sharpness_score = score
        self._sharp_label.setText(f"Sharp: {score:.1f}")

    def refresh_selection(self) -> None:
        self._update_border()

    def _update_border(self) -> None:
        color = "#2ecc71" if self._frame_data.is_selected else "#444"
        self.setStyleSheet(f"QFrame {{ border: 2px solid {color}; border-radius: 3px; }}")

    def mousePressEvent(self, event) -> None:
        self._frame_data.is_selected = not self._frame_data.is_selected
        self._update_border()
        self.toggled.emit(self._frame_data.frame_index, self._frame_data.is_selected)
