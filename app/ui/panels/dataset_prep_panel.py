import os
import re
from typing import Dict, List, Optional

from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QProgressBar, QPushButton, QRadioButton, QSpinBox,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.workers.dataset_worker import DatasetWorker


class DatasetPrepPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = QSettings("VideoToPng", "App")
        self._worker: Optional[DatasetWorker] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("Dataset Prep")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

        # ── folder + name inputs ─────────────────────────────────────────────
        src_row = QHBoxLayout()
        src_row.addWidget(QLabel("Source (labeled):    "))
        self._source_input = QLineEdit()
        self._source_input.setPlaceholderText("Folder with labeled images + .txt files…")
        src_row.addWidget(self._source_input)
        btn_src = QPushButton("Browse")
        btn_src.setFixedWidth(70)
        btn_src.clicked.connect(self._browse_source)
        src_row.addWidget(btn_src)
        layout.addLayout(src_row)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Output folder:       "))
        self._output_input = QLineEdit()
        self._output_input.setPlaceholderText("Where to create the dataset…")
        out_row.addWidget(self._output_input)
        btn_out = QPushButton("Browse")
        btn_out.setFixedWidth(70)
        btn_out.clicked.connect(self._browse_output)
        out_row.addWidget(btn_out)
        layout.addLayout(out_row)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Dataset name:        "))
        self._name_input = QLineEdit("my_dataset")
        name_row.addWidget(self._name_input)
        name_row.addStretch()
        layout.addLayout(name_row)

        cls_row = QHBoxLayout()
        cls_row.addWidget(QLabel("Classes:             "))
        self._classes_input = QLineEdit()
        self._classes_input.setPlaceholderText("dog, cat, person  (comma-separated)")
        cls_row.addWidget(self._classes_input)
        btn_load_cls = QPushButton("Load file")
        btn_load_cls.setFixedWidth(80)
        btn_load_cls.clicked.connect(self._load_classes_file)
        cls_row.addWidget(btn_load_cls)
        layout.addLayout(cls_row)

        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setStyleSheet("color: #444;")
        layout.addWidget(line1)

        # ── split mode ───────────────────────────────────────────────────────
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Split mode:"))
        self._radio_random = QRadioButton("Random")
        self._radio_prefix = QRadioButton("By Prefix")
        self._radio_random.setChecked(True)
        self._radio_random.toggled.connect(self._on_mode_changed)
        mode_row.addWidget(self._radio_random)
        mode_row.addWidget(self._radio_prefix)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        self._mode_stack = QStackedWidget()

        # Random page
        rand_widget = QWidget()
        rand_layout = QHBoxLayout(rand_widget)
        rand_layout.setContentsMargins(0, 0, 0, 0)
        for lbl, attr, default in [("Train %", "_train_spin", 70),
                                    ("Val %",   "_val_spin",   20),
                                    ("Test %",  "_test_spin",  10)]:
            rand_layout.addWidget(QLabel(lbl))
            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.setValue(default)
            spin.setFixedWidth(60)
            setattr(self, attr, spin)
            rand_layout.addWidget(spin)
            rand_layout.addSpacing(16)
        rand_layout.addStretch()
        self._mode_stack.addWidget(rand_widget)

        # Prefix page
        prefix_widget = QWidget()
        prefix_layout = QVBoxLayout(prefix_widget)
        prefix_layout.setContentsMargins(0, 0, 0, 0)
        prefix_layout.setSpacing(4)

        self._prefix_table = QTableWidget(0, 3)
        self._prefix_table.setHorizontalHeaderLabels(["Prefix (filename starts with)", "Split", ""])
        self._prefix_table.horizontalHeader().setStretchLastSection(False)
        self._prefix_table.setColumnWidth(0, 280)
        self._prefix_table.setColumnWidth(1, 90)
        self._prefix_table.setColumnWidth(2, 36)
        self._prefix_table.setMaximumHeight(200)
        self._prefix_table.verticalHeader().setVisible(False)
        prefix_layout.addWidget(self._prefix_table)

        prefix_btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add row")
        btn_add.setFixedWidth(90)
        btn_add.clicked.connect(self._add_prefix_row)
        prefix_btn_row.addWidget(btn_add)
        prefix_btn_row.addSpacing(20)
        prefix_btn_row.addWidget(QLabel("Remaining unmatched →"))
        self._remainder_combo = QComboBox()
        self._remainder_combo.addItems(["train", "val", "test"])
        self._remainder_combo.setFixedWidth(80)
        prefix_btn_row.addWidget(self._remainder_combo)
        prefix_btn_row.addStretch()
        prefix_layout.addLayout(prefix_btn_row)

        self._mode_stack.addWidget(prefix_widget)
        layout.addWidget(self._mode_stack)

        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setStyleSheet("color: #444;")
        layout.addWidget(line2)

        # ── build button + progress ──────────────────────────────────────────
        build_row = QHBoxLayout()
        self._btn_build = QPushButton("Build Dataset")
        self._btn_build.setStyleSheet(
            "QPushButton { background-color: #2d7d46; color: white; "
            "font-weight: bold; padding: 8px 20px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #3a9e5c; }"
            "QPushButton:disabled { background-color: #333; color: #666; }"
        )
        self._btn_build.clicked.connect(self._start_build)
        build_row.addWidget(self._btn_build)
        self._btn_cancel_build = QPushButton("Cancel")
        self._btn_cancel_build.setVisible(False)
        self._btn_cancel_build.clicked.connect(self._cancel_build)
        build_row.addWidget(self._btn_cancel_build)
        build_row.addStretch()
        layout.addLayout(build_row)

        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._result_label = QLabel("")
        self._result_label.setStyleSheet("color: #aaa; font-size: 11px;")
        self._result_label.setWordWrap(True)
        layout.addWidget(self._result_label)

        layout.addStretch()

    # ── mode switch ──────────────────────────────────────────────────────────

    def _on_mode_changed(self) -> None:
        self._mode_stack.setCurrentIndex(0 if self._radio_random.isChecked() else 1)

    # ── browse helpers ───────────────────────────────────────────────────────

    def _browse_source(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Labeled Images Folder")
        if folder:
            self._source_input.setText(folder)

    def _browse_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self._output_input.setText(folder)

    def _load_classes_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Classes File", "",
            "Text/YAML files (*.txt *.yaml *.names);;All files (*)",
        )
        if not path:
            return
        try:
            with open(path) as f:
                content = f.read()
            m = re.search(r"names\s*:\s*\[([^\]]+)\]", content)
            if m:
                names = [n.strip().strip("'\"") for n in m.group(1).split(",")]
            else:
                names = [l.strip() for l in content.splitlines() if l.strip()]
            self._classes_input.setText(", ".join(names))
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load classes: {e}")

    # ── prefix table ─────────────────────────────────────────────────────────

    def _add_prefix_row(self) -> None:
        row = self._prefix_table.rowCount()
        self._prefix_table.insertRow(row)
        self._prefix_table.setItem(row, 0, QTableWidgetItem(""))
        combo = QComboBox()
        combo.addItems(["train", "val", "test"])
        self._prefix_table.setCellWidget(row, 1, combo)
        btn_rm = QPushButton("−")
        btn_rm.setFixedWidth(30)
        btn_rm.clicked.connect(lambda: self._remove_prefix_row(btn_rm))
        self._prefix_table.setCellWidget(row, 2, btn_rm)

    def _remove_prefix_row(self, btn: QPushButton) -> None:
        for row in range(self._prefix_table.rowCount()):
            if self._prefix_table.cellWidget(row, 2) is btn:
                self._prefix_table.removeRow(row)
                return

    def _get_prefix_rules(self) -> List[Dict]:
        rules = []
        for row in range(self._prefix_table.rowCount()):
            item = self._prefix_table.item(row, 0)
            combo = self._prefix_table.cellWidget(row, 1)
            if item and item.text().strip() and combo:
                rules.append({"prefix": item.text().strip(), "split": combo.currentText()})
        return rules

    # ── build ────────────────────────────────────────────────────────────────

    def _start_build(self) -> None:
        source = self._source_input.text().strip()
        output = self._output_input.text().strip()
        name = self._name_input.text().strip() or "my_dataset"
        classes_raw = self._classes_input.text().strip()
        class_names = [c.strip() for c in classes_raw.split(",") if c.strip()] if classes_raw else []

        if not source or not os.path.isdir(source):
            QMessageBox.warning(self, "Missing Source", "Please select a valid source folder.")
            return
        if not output:
            QMessageBox.warning(self, "Missing Output", "Please select an output folder.")
            return
        if not class_names:
            reply = QMessageBox.question(
                self, "No Classes",
                "No class names specified. Continue with an empty class list?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        split_mode = "random" if self._radio_random.isChecked() else "prefix"
        prefix_rules = self._get_prefix_rules() if split_mode == "prefix" else []

        self._btn_build.setEnabled(False)
        self._btn_cancel_build.setVisible(True)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._result_label.setText("Building dataset…")

        self._worker = DatasetWorker(
            source_dir=source,
            output_dir=output,
            name=name,
            class_names=class_names,
            split_mode=split_mode,
            train_pct=self._train_spin.value(),
            val_pct=self._val_spin.value(),
            test_pct=self._test_spin.value(),
            prefix_rules=prefix_rules,
            remainder_split=self._remainder_combo.currentText(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _cancel_build(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        self._reset_ui()
        self._result_label.setText("Cancelled.")

    def _on_progress(self, current: int, total: int) -> None:
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(current)

    def _on_finished(self, counts: Dict) -> None:
        self._reset_ui()
        output = self._output_input.text().strip()
        name = self._name_input.text().strip() or "my_dataset"
        total = sum(counts.values())
        self._result_label.setText(
            f"Dataset built: {total:,} images  "
            f"(train {counts['train']:,}  val {counts['val']:,}  test {counts['test']:,})\n"
            f"→ {os.path.join(output, name)}"
        )

    def _on_error(self, msg: str) -> None:
        self._reset_ui()
        self._result_label.setText(f"Error: {msg}")
        QMessageBox.critical(self, "Dataset Error", msg)

    def _reset_ui(self) -> None:
        self._btn_build.setEnabled(True)
        self._btn_cancel_build.setVisible(False)
        self._progress_bar.setVisible(False)
