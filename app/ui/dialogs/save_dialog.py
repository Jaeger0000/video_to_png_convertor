from PyQt5.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout,
)


class SaveDialog(QDialog):
    def __init__(self, selected_count: int, save_folder: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save Selected Frames")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(QLabel(f"<b>{selected_count:,} frames selected</b>"))

        path_label = QLabel(f"Save location:\n<code>{save_folder}</code>")
        path_label.setWordWrap(True)
        path_label.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(path_label)

        layout.addSpacing(4)

        self._cb_frames = QCheckBox("Save selected frames as images")
        self._cb_frames.setChecked(True)
        layout.addWidget(self._cb_frames)

        self._cb_clip = QCheckBox("Also save video clip (start → end of selection)")
        self._cb_clip.setChecked(False)
        layout.addWidget(self._cb_clip)

        layout.addSpacing(4)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_choices(self) -> dict:
        return {
            "save_frames": self._cb_frames.isChecked(),
            "save_clip": self._cb_clip.isChecked(),
        }
