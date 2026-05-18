from PyQt5.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout,
)


class SaveDialog(QDialog):
    def __init__(self, selected_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save Options")
        self.setMinimumWidth(300)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"<b>{selected_count:,} frames selected</b>"))
        layout.addSpacing(8)

        self._cb_frames = QCheckBox("Save selected frames as images")
        self._cb_frames.setChecked(True)
        layout.addWidget(self._cb_frames)

        self._cb_clip = QCheckBox("Also save video clip (start → end of selected frames)")
        self._cb_clip.setChecked(False)
        layout.addWidget(self._cb_clip)

        layout.addSpacing(8)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_choices(self) -> dict:
        return {
            "save_frames": self._cb_frames.isChecked(),
            "save_clip": self._cb_clip.isChecked(),
        }
