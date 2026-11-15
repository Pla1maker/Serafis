from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QFileDialog, QLineEdit, QVBoxLayout

from ...core.models import TestFileResult
from ...localization.i18n import tr
from ...recovery import workflow
from ...verification.verifier import launch_allowed
from ..state import AppState
from ..widgets import Card, Page, button, clear_layout, confirm, error, info, label, open_url_confirmed, row


class RecoveryPage(Page):
    step_index = 5
    finished = Signal()

    def __init__(self, state: AppState) -> None:
        super().__init__(tr("recovery.title"), tr("recovery.intro"))
        self.state = state
        rs = state.d.recovery

        # 1. backup
        c1 = Card(tr("recovery.s1.title"))
        for k in ("a", "b", "c", "d"):
            c1.add(label("• " + tr("recovery.s1." + k)))
        self.backup_cb = QCheckBox(tr("recovery.s1.confirm"))
        self.backup_cb.setChecked(rs.backup_confirmed)
        self.backup_cb.toggled.connect(self._backup_toggled)
        c1.add(self.backup_cb)
        self.add(c1)

        # 2. workspace
        self.c2 = Card(tr("recovery.s2.title"))
        self.c2.add(label(tr("recovery.s2.help")))
        self.ws_label = label("", "Muted")
        self.c2.add(self.ws_label)
        self.ws_btn = button(tr("recovery.s2.create"))
        self.ws_btn.clicked.connect(self.create_ws)
        self.c2.add(row(self.ws_btn))
        self.add(self.c2)

        # 3. test files
        self.c3 = Card(tr("recovery.s3.title"))
        self.c3.add(label(tr("recovery.s3.help")))
        self.pick_btn = button(tr("recovery.s3.pick"))
        self.pick_btn.clicked.connect(self.pick_tests)
        self.c3.add(row(self.pick_btn))
        self.tests_label = label("", "Muted")
        self.c3.add(self.tests_label)
        self.add(self.c3)

        # 4. run tool
        self.c4 = Card(tr("recovery.s4.title"))
        self.c4_body = QVBoxLayout()
        self.c4.add(self.c4_body)
        self.add(self.c4)

        # 5. check results
        self.c5 = Card(tr("recovery.s5.title"))
        self.c5.add(label(tr("recovery.s5.help")))
        self.c5_body = QVBoxLayout()
        self.c5.add(self.c5_body)
        self.c5.add(label(tr("recovery.s5.problems"), "Muted"))
        self.problem_edit = QLineEdit()
        self.problem_edit.setMaxLength(500)
        add_p = button(tr("recovery.s5.add_problem"))
        add_p.clicked.connect(self.add_problem)
        self.c5.add(row(self.problem_edit, add_p, stretch=False))
        self.add(self.c5)

        # 6. full recovery
        self.c6 = Card(tr("recovery.s6.title"))
        self.c6_body = QVBoxLayout()
        self.c6.add(self.c6_body)
        self.add(self.c6)
        self.next_btn = button(tr("recovery.next"), primary=True)
        self.next_btn.clicked.connect(self.finished.emit)
        self.add(row(self.next_btn))
        self.finish()
        self.refresh()

    # ------------------------------------------------------------------
    def _backup_toggled(self, v: bool) -> None:
        self.state.d.recovery.backup_confirmed = v
        self.refresh()

    def create_ws(self) -> None:
        base = QFileDialog.getExistingDirectory(self, tr("recovery.s2.choose"))
        if not base:
            return
        try:
            ws = workflow.create_workspace(Path(base))
        except OSError as exc:
            error(self, tr("recovery.err.workspace"), type(exc).__name__)
            return
        self.state.d.recovery.workspace = str(ws)
        self.refresh()

    def pick_tests(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, tr("recovery.s3.pick"))
        if not files:
            return
        try:
            workflow.copy_test_files(self.state.d.recovery, files)
        except workflow.RecoveryError as exc:
            error(self, tr(exc.key))
        except OSError as exc:
            error(self, tr("recovery.err.copy"), type(exc).__name__)
        self.state.notify("recovery")
        self.refresh()

    def launch(self, path: str) -> None:
        if not confirm(self, tr("recovery.s4.launch"), tr("recovery.s4.launch_confirm"), danger=True):
            return
        try:
            workflow.open_tool_visibly(path)
            self.state.d.recovery.test_started = True
        except workflow.RecoveryError as exc:
            error(self, tr(exc.key))
        except OSError as exc:
            error(self, tr("recovery.err.launch"), type(exc).__name__)
        self.refresh()

    def mark_started(self) -> None:
        if confirm(self, tr("recovery.s4.title"), tr("recovery.s4.manual_confirm")):
            self.state.d.recovery.test_started = True
            self.refresh()

    def check_output(self, tf: TestFileResult) -> None:
        start = str(Path(self.state.d.recovery.workspace or "") / "2_decrypted_output")
        f, _ = QFileDialog.getOpenFileName(self, tr("recovery.s5.pick_output", name=tf.original_name), start)
        if not f:
            return
        workflow.check_decrypted(tf, f)
        workflow.evaluate(self.state.d.recovery)
        self.state.notify("recovery")
        self.refresh()

    def add_problem(self) -> None:
        text = self.problem_edit.text().strip()
        if text:
            self.state.d.recovery.errors.append(text)
            self.problem_edit.clear()
            info(self, tr("recovery.s5.problem_added"))

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        rs = self.state.d.recovery
        self.c2.setEnabled(rs.backup_confirmed)
        self.ws_label.setText(tr("recovery.s2.current", path=rs.workspace) if rs.workspace else tr("recovery.s2.none"))
        self.c3.setEnabled(rs.backup_confirmed and bool(rs.workspace))
        self.tests_label.setText("\n".join(f"• {t.original_name} → {Path(t.working_copy).name}" for t in rs.test_files) or tr("recovery.s3.none"))

        clear_layout(self.c4_body)
        sol = self.state.selected_solution()
        self.c4.setEnabled(bool(rs.test_files))
        if not sol:
            self.c4_body.addWidget(label(tr("recovery.s4.no_solution")))
        else:
            self.c4_body.addWidget(label(tr("recovery.s4.manual", name=sol["name"], vendor=sol["vendor"])))
            for k in ("a", "b", "c", "d", "e"):
                self.c4_body.addWidget(label(f"{k}) " + tr("recovery.s4.step." + k)))
            btns = []
            if sol.get("howto_url"):
                hb = button(tr("options.open_howto"))
                hb.clicked.connect(lambda: open_url_confirmed(self, sol["howto_url"]))
                btns.append(hb)
            reps = [r for r in self.state.d.verifications if r.solution_id == sol["id"]]
            rep = reps[-1] if reps else None
            allowed, key = launch_allowed(rep) if rep else (False, "launch.blocked.not_verified")
            lb = button(tr("recovery.s4.launch"), primary=True)
            lb.setEnabled(allowed)
            if rep:
                lb.clicked.connect(lambda: self.launch(rep.file_path))
            btns.append(lb)
            mb = button(tr("recovery.s4.manual_done"))
            mb.clicked.connect(self.mark_started)
            btns.append(mb)
            self.c4_body.addLayout(row(*btns))
            self.c4_body.addWidget(label(tr(key), "Muted"))
            if rs.test_started:
                self.c4_body.addWidget(label("✔ " + tr("recovery.s4.started")))

        clear_layout(self.c5_body)
        self.c5.setEnabled(rs.test_started and bool(rs.test_files))
        for tf in rs.test_files:
            status = tr("test." + tf.status) + (f" — {tr(tf.detail_key)}" if tf.detail_key else "")
            b = button(tr("recovery.s5.check"))
            b.clicked.connect(lambda _=False, tf=tf: self.check_output(tf))
            self.c5_body.addLayout(row(label(f"{tf.original_name}: {status}"), b))

        clear_layout(self.c6_body)
        unlocked = workflow.evaluate(rs)
        if unlocked:
            box = Card(None, "Success")
            box.add(label(tr("recovery.s6.unlocked")))
            for k in ("a", "b", "c", "d", "e"):
                box.add(label("• " + tr("recovery.s6." + k)))
            self.c6_body.addWidget(box)
        else:
            self.c6_body.addWidget(label(tr("recovery.s6.locked")))
            if any(t.status == "failed" for t in rs.test_files):
                w = Card(None, "Danger")
                w.add(label(tr("recovery.s6.failed")))
                self.c6_body.addWidget(w)
