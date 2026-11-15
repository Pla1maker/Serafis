from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QLineEdit, QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView

from ...localization.i18n import tr
from ...verification.download import DownloadError, download_official
from ...verification.origin import url_is_official
from ...verification.verifier import Verifier, launch_allowed
from ..state import AppState
from ..style import STATUS_ICONS
from ..widgets import Card, Page, button, clear_layout, confirm, error, label, row
from ..workers import Task, run_task


class VerificationPage(Page):
    step_index = 4
    finished = Signal()
    go_back = Signal()

    def __init__(self, state: AppState) -> None:
        super().__init__(tr("verify.title"), tr("verify.intro"))
        self.state = state
        self.verifier = Verifier()
        self.need = Card(None, "Info")
        self.need.add(label(tr("verify.need_solution")))
        b = button(tr("verify.go_options"))
        b.clicked.connect(self.go_back.emit)
        self.need.add(row(b))
        self.add(self.need)

        never = Card(None, "Info")
        never.add(label("🛡 " + tr("verify.never_auto")))
        self.add(never)

        self.sol_card = Card(tr("verify.selected"))
        self.sol_label = label("")
        self.sol_card.add(self.sol_label)
        self.add(self.sol_card)

        self.get_card = Card(tr("verify.get.title"))
        self.get_card.add(label(tr("verify.get.help")))
        self.dl_btn = button(tr("verify.get.download"))
        self.dl_btn.clicked.connect(self.download)
        self.pick_btn = button(tr("verify.get.pick"))
        self.pick_btn.clicked.connect(self.pick)
        self.get_card.add(row(self.dl_btn, self.pick_btn))
        self.dl_progress = QProgressBar()
        self.dl_progress.setVisible(False)
        self.get_card.add(self.dl_progress)
        self.get_card.add(label(tr("verify.get.url_label"), "Muted"))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://…")
        self.url_edit.setMaxLength(2000)
        self.get_card.add(self.url_edit)
        self.file_label = label("", "Muted")
        self.get_card.add(self.file_label)
        self.verify_btn = button(tr("verify.run"), primary=True)
        self.verify_btn.clicked.connect(self.run_verify)
        self.get_card.add(row(self.verify_btn))
        self.add(self.get_card)

        self.result_card = Card(tr("verify.result"))
        self.add(self.result_card)
        self.next_btn = button(tr("verify.next"), primary=True)
        self.next_btn.clicked.connect(self.finished.emit)
        self.add(row(self.next_btn))
        self.finish()
        self.refresh()

    # ------------------------------------------------------------------
    def download(self) -> None:
        sol = self.state.selected_solution()
        if not sol or not sol.get("download_url"):
            error(self, tr("download.err.not_official"))
            return
        if not confirm(self, tr("verify.get.download"), tr("verify.download.confirm", url=sol["download_url"], vendor=sol["vendor"])):
            return
        dest = QFileDialog.getExistingDirectory(self, tr("verify.download.dest"))
        if not dest:
            return
        self.dl_btn.setEnabled(False)
        self.dl_progress.setVisible(True)
        self.dl_progress.setRange(0, 0)
        run_task(Task(download_official, sol, Path(dest), with_progress=True), self._downloaded, self._dl_failed,
                 lambda a: self.dl_progress.setFormat(f"{a[0] // 1024} KiB"))

    def _downloaded(self, res) -> None:
        path, final_url = res
        self.dl_btn.setEnabled(True)
        self.dl_progress.setVisible(False)
        self.state.d.downloaded_file = str(path)
        self.state.d.download_url = final_url
        self.url_edit.setText(final_url)
        self.refresh()

    def _dl_failed(self, exc) -> None:
        self.dl_btn.setEnabled(True)
        self.dl_progress.setVisible(False)
        key = exc.key if isinstance(exc, DownloadError) else "download.err.network"
        self.state.d.user_problems.append(tr(key))
        error(self, tr(key))

    def pick(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, tr("verify.get.pick"))
        if f:
            self.state.d.downloaded_file = f
            self.state.d.download_url = None
            self.refresh()

    def run_verify(self) -> None:
        sol = self.state.selected_solution()
        f = self.state.d.downloaded_file
        if not sol or not f:
            error(self, tr("verify.err.no_file"))
            return
        url = self.url_edit.text().strip() or None
        if url and not url.startswith(("https://", "http://")):
            error(self, tr("verify.err.bad_url"))
            return
        self.verify_btn.setEnabled(False)
        self.file_label.setText(tr("verify.running"))
        run_task(Task(self.verifier.verify, f, sol, url, self.state.d.chosen), self._verified, self._verify_failed)

    def _verified(self, rep) -> None:
        self.verify_btn.setEnabled(True)
        self.state.d.verifications.append(rep)
        self.state.notify("verification")
        self.refresh()
        if rep.has_failure:
            error(self, tr("verify.alert.failure"))

    def _verify_failed(self, exc) -> None:
        self.verify_btn.setEnabled(True)
        self.file_label.setText("")
        error(self, tr("verify.err.failed"), type(exc).__name__)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        sol = self.state.selected_solution()
        self.need.setVisible(sol is None)
        for w in (self.sol_card, self.get_card):
            w.setVisible(sol is not None)
        if sol is None:
            self.result_card.setVisible(False)
            self.next_btn.setVisible(False)
            return
        self.sol_label.setText(f"{sol['name']} — {sol['vendor']}\n{tr('options.official_page')}: {sol['official_page']}")
        self.dl_btn.setEnabled(bool(sol.get("download_url")) and url_is_official(sol.get("download_url"), sol.get("official_domains", [])))
        f = self.state.d.downloaded_file
        self.file_label.setText(tr("verify.file", name=Path(f).name) if f else tr("verify.no_file"))
        self.verify_btn.setEnabled(bool(f))
        reps = [r for r in self.state.d.verifications if r.solution_id == sol["id"]]
        self.result_card.setVisible(bool(reps))
        self.next_btn.setVisible(bool(reps))
        if not reps:
            return
        rep = reps[-1]
        clear_layout(self.result_card.lay)
        self.result_card.add(label(tr("verify.result"), "CardTitle"))
        self.result_card.add(label(f"{rep.file_name}\nSHA-256: {rep.sha256}", "Muted"))
        t = QTableWidget(len(rep.checks), 3)
        t.setHorizontalHeaderLabels([tr("verify.col.check"), tr("verify.col.status"), tr("verify.col.detail")])
        for i, c in enumerate(rep.checks):
            t.setItem(i, 0, QTableWidgetItem(tr("check." + c.check)))
            t.setItem(i, 1, QTableWidgetItem(f"{STATUS_ICONS.get(c.status, '')} {tr('status.' + c.status)}"))
            it = QTableWidgetItem(tr(c.detail_key, **c.detail_args))
            it.setToolTip(it.text())
            t.setItem(i, 2, it)
        t.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setWordWrap(True)
        t.resizeRowsToContents()
        t.setMinimumHeight(60 + 34 * len(rep.checks))
        self.result_card.add(t)
        ok, key = launch_allowed(rep)
        verdict = Card(None, "Success" if ok else ("Danger" if rep.has_failure else "Warning"))
        verdict.add(label(tr("verify.verdict." + ("ok" if ok else ("fail" if rep.has_failure else "partial")))))
        verdict.add(label(tr(key), "Muted"))
        unavailable = [tr("check." + c.check) for c in rep.checks if c.status == "unavailable"]
        if unavailable:
            verdict.add(label(tr("verify.unavailable_list", checks=", ".join(dict.fromkeys(unavailable))), "Muted"))
        self.result_card.add(verdict)
