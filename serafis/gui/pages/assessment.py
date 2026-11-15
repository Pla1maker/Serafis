from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QHeaderView, QListWidget, QPlainTextEdit, QProgressBar, QTableWidget, QTableWidgetItem,
)

from ...analysis.scanner import Scanner
from ...core.paths import validate_directory
from ...localization.i18n import tr
from ..state import AppState
from ..widgets import Card, Page, button, clear_layout, confirm, error, label, row, stat_card
from ..workers import Task, run_task


def fill_table(table: QTableWidget, headers: list[str], rows: list[tuple]) -> None:
    table.clear()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    for r, values in enumerate(rows):
        for c, v in enumerate(values):
            it = QTableWidgetItem(str(v))
            table.setItem(r, c, it)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setMinimumHeight(min(320, 40 + 30 * max(1, len(rows))))


class AssessmentPage(Page):
    step_index = 1
    finished = Signal()

    def __init__(self, state: AppState) -> None:
        super().__init__(tr("assess.title"), tr("assess.intro"))
        self.state = state
        self.scanner: Scanner | None = None

        ro = Card(None, "Info")
        ro.add(label("🔒 " + tr("assess.readonly")))
        self.add(ro)

        dirs = Card(tr("assess.dirs.title"))
        dirs.add(label(tr("assess.dirs.help"), "Muted"))
        self.list = QListWidget()
        self.list.setMinimumHeight(110)
        dirs.add(self.list)
        self.add_btn = button(tr("assess.dirs.add"))
        self.rm_btn = button(tr("assess.dirs.remove"))
        self.add_btn.clicked.connect(self.add_dir)
        self.rm_btn.clicked.connect(self.remove_dir)
        dirs.add(row(self.add_btn, self.rm_btn))
        self.add(dirs)

        self.start_btn = button(tr("assess.start"), primary=True)
        self.cancel_btn = button(tr("common.cancel"))
        self.cancel_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_scan)
        self.cancel_btn.clicked.connect(self.cancel_scan)
        self.add(row(self.start_btn, self.cancel_btn))
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress_label = label("", "Muted")
        self.add(self.progress)
        self.add(self.progress_label)

        self.results = Card(tr("assess.results.title"))
        self.results_lay = QHBoxLayout()
        self.results.add(self.results_lay)
        self.ext_table = QTableWidget()
        self.dir_table = QTableWidget()
        self.notes_box = QPlainTextEdit()
        self.notes_box.setReadOnly(True)
        self.notes_box.setMinimumHeight(140)
        self.results.add(label(tr("assess.results.extensions"), "CardTitle"))
        self.results.add(self.ext_table)
        self.results.add(label(tr("assess.results.distribution"), "CardTitle"))
        self.results.add(self.dir_table)
        self.results.add(label(tr("assess.results.notes"), "CardTitle"))
        self.results.add(label(tr("assess.results.notes_warning"), "Muted"))
        self.results.add(self.notes_box)
        self.issues = label("", "Muted")
        self.results.add(self.issues)
        self.next_btn = button(tr("assess.next"), primary=True)
        self.next_btn.clicked.connect(self.finished.emit)
        self.results.add(row(self.next_btn))
        self.add(self.results)
        self.finish()
        for d in state.d.directories:
            self.list.addItem(d)
        self.refresh()

    # ------------------------------------------------------------------
    def add_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, tr("assess.dirs.add"))
        if not d:
            return
        try:
            p = str(validate_directory(d))
        except (OSError, ValueError):
            error(self, tr("assess.err.invalid_dir"))
            return
        if p not in self.state.d.directories:
            self.state.d.directories.append(p)
            self.list.addItem(p)

    def remove_dir(self) -> None:
        for it in self.list.selectedItems():
            self.state.d.directories.remove(it.text())
            self.list.takeItem(self.list.row(it))

    def start_scan(self) -> None:
        if not self.state.d.directories:
            error(self, tr("assess.err.no_dirs"))
            return
        if not confirm(self, tr("assess.confirm.title"), tr("assess.confirm.text")):
            return
        self.scanner = Scanner(self.state.rules)
        self.start_btn.setEnabled(False)
        self.add_btn.setEnabled(False)
        self.rm_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.progress_label.setText(tr("assess.running", files=0, suspicious=0))
        task = Task(self.scanner.scan, list(self.state.d.directories), with_progress=True)
        run_task(task, self._done, self._failed, self._progress)

    def cancel_scan(self) -> None:
        if self.scanner:
            self.scanner.cancel()

    def _progress(self, args) -> None:
        files, susp, _ = args
        self.progress_label.setText(tr("assess.running", files=files, suspicious=susp))

    def _reset_controls(self) -> None:
        self.start_btn.setEnabled(True)
        self.add_btn.setEnabled(True)
        self.rm_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress.setVisible(False)

    def _done(self, outcome) -> None:
        self._reset_controls()
        self.state.d.scan = outcome
        r = outcome.result
        self.progress_label.setText(tr("assess.cancelled") if r.cancelled else tr("assess.done", files=r.total_files))
        self.state.notify("scan")
        self.refresh()

    def _failed(self, exc) -> None:
        self._reset_controls()
        self.progress_label.setText("")
        error(self, tr("assess.err.failed"), type(exc).__name__)

    def refresh(self) -> None:
        outcome = self.state.d.scan
        self.results.setVisible(outcome is not None)
        if not outcome:
            return
        r = outcome.result
        clear_layout(self.results_lay)
        self.results_lay.addWidget(stat_card(tr("assess.stat.files"), f"{r.total_files:,}"))
        self.results_lay.addWidget(stat_card(tr("assess.stat.suspicious"), f"{r.suspicious_files:,}"))
        self.results_lay.addWidget(stat_card(tr("assess.stat.notes"), str(len(r.ransom_notes))))
        pct = (100.0 * r.suspicious_files / r.total_files) if r.total_files else 0
        self.results_lay.addWidget(stat_card(tr("assess.stat.share"), f"{pct:.1f}%"))
        fill_table(self.ext_table, [tr("report.extension"), tr("report.count")],
                   list(r.suspicious_extension_counts.items())[:50] or [(tr("assess.none_found"), "")])
        fill_table(self.dir_table, [tr("report.directory"), tr("report.count")],
                   list(r.directory_distribution.items())[:30] or [(tr("assess.none_found"), "")])
        lines = []
        for n in r.ransom_notes:
            lines.append(f"■ {n.name}  (×{n.occurrences}, {n.size} B)")
            if n.emails:
                lines.append("  " + tr("assess.note.emails") + ": " + ", ".join(n.emails))
            if n.onion_urls:
                lines.append("  " + tr("assess.note.onion") + ": " + ", ".join(n.onion_urls))
            if n.excerpt:
                lines.append("  " + n.excerpt.replace("\n", "\n  "))
            lines.append("")
        self.notes_box.setPlainText("\n".join(lines) or tr("assess.no_notes"))
        issues = []
        if r.truncated:
            issues.append(tr("assess.truncated"))
        if r.cancelled:
            issues.append(tr("assess.cancelled"))
        if r.errors:
            issues.append(tr("assess.errors", n=len(r.errors)))
        if r.skipped:
            issues.append(tr("assess.skipped", n=r.skipped))
        self.issues.setText("\n".join(issues))
