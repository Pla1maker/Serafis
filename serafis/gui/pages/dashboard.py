from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QProgressBar

from ...localization.i18n import tr
from ..state import STEPS, AppState
from ..widgets import Card, Page, button, label, row


class DashboardPage(Page):
    go_to = Signal(str)
    check_catalog = Signal()

    def __init__(self, state: AppState) -> None:
        super().__init__(tr("dash.title"), tr("dash.intro"))
        self.state = state

        first = Card(tr("dash.first_aid.title"), "Warning")
        for k in ("isolate", "no_delete", "no_pay", "keep_notes", "no_restart_tools"):
            first.add(label("• " + tr(f"dash.first_aid.{k}")))
        self.add(first)

        prog = Card(tr("dash.progress.title"))
        self.bar = QProgressBar()
        self.bar.setRange(0, len(STEPS))
        prog.add(self.bar)
        self.grid = QGridLayout()
        prog.add(self.grid)
        self.step_labels = {}
        for i, s in enumerate(STEPS):
            lb = label("")
            self.step_labels[s] = lb
            b = button(tr("dash.open"))
            b.clicked.connect(lambda _=False, s=s: self.go_to.emit(s))
            self.grid.addWidget(label(f"{i + 1}. {tr('nav.' + s)}"), i, 0)
            self.grid.addWidget(lb, i, 1)
            self.grid.addWidget(b, i, 2)
        self.add(prog)

        self.start = button(tr("dash.start"), primary=True)
        self.start.clicked.connect(lambda: self.go_to.emit("assessment"))
        self.add(row(self.start))

        cat = Card(tr("dash.catalog.title"))
        self.cat_label = label("")
        cat.add(self.cat_label)
        upd = button(tr("catalog.check_updates"))
        upd.clicked.connect(self.check_catalog.emit)
        cat.add(row(upd))
        self.add(cat)

        about = Card(tr("dash.about.title"), "Info")
        about.add(label(tr("dash.about.text")))
        self.add(about)
        self.finish()
        self.refresh()

    def refresh(self) -> None:
        done = 0
        for s, lb in self.step_labels.items():
            ok = self.state.step_done(s)
            done += ok
            lb.setText("✅ " + tr("dash.done") if ok else "○ " + tr("dash.todo"))
        self.bar.setValue(done)
        self.bar.setFormat(tr("dash.progress.format", done=done, total=len(STEPS)))
        c = self.state.catalog
        self.cat_label.setText(tr("dash.catalog.status", version=c.version, date=c.generated_at[:10],
                                  n=len(c.solutions), families=len(c.families), origin=tr("catalog.origin." + c.origin)))
