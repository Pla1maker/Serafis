from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QMainWindow, QMenu, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from .. import __version__
from ..catalog.catalog import load_catalog
from ..catalog.updater import update_catalog
from ..core.paths import resource_path
from ..localization.i18n import FLAGS, LANGUAGES, tr, translator
from .language import LanguageScreen
from .pages.assessment import AssessmentPage
from .pages.dashboard import DashboardPage
from .pages.identification import IdentificationPage
from .pages.options import OptionsPage
from .pages.recovery import RecoveryPage
from .pages.results import ResultsPage
from .pages.verification import VerificationPage
from .state import STEPS, AppState
from .widgets import confirm, error, info, label
from .workers import Task, run_task

log = logging.getLogger(__name__)
PAGES = ("dashboard",) + STEPS


class MainWindow(QMainWindow):
    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state
        self.setWindowTitle("SERAFIS — Ransomware Recovery Companion")
        icon = resource_path("resources", "serafis.png")
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self.resize(1200, 820)
        self.setMinimumSize(980, 640)
        self.pages: dict[str, QWidget] = {}
        self.nav: dict[str, QPushButton] = {}
        state.changed.connect(self._on_state_changed)
        if state.settings.language:
            translator.set_language(state.settings.language)
            self.build()
        else:
            self.show_language_screen()

    # ------------------------------------------------------------------
    def show_language_screen(self) -> None:
        scr = LanguageScreen()
        scr.chosen.connect(self.set_language)
        self.setCentralWidget(scr)

    def set_language(self, lang: str) -> None:
        current = self.current_page_name() if self.pages else "dashboard"
        translator.set_language(lang)
        self.state.settings.language = lang
        try:
            self.state.settings.save()
        except OSError as exc:
            log.warning("cannot save settings: %s", type(exc).__name__)
        self.build(current)

    def build(self, start: str = "dashboard") -> None:
        root = QWidget()
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(250)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(14, 20, 14, 14)
        sv.setSpacing(4)
        sv.addWidget(label("SERAFIS", "Brand", wrap=False))
        sv.addWidget(label(tr("app.subtitle"), "BrandSub"))
        sv.addSpacing(18)
        group = QButtonGroup(self)
        group.setExclusive(True)
        self.nav = {}
        for i, name in enumerate(PAGES):
            text = tr("nav." + name) if i == 0 else f"{i}.  {tr('nav.' + name)}"
            b = QPushButton(text)
            b.setObjectName("NavButton")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, n=name: self.go(n))
            group.addButton(b)
            sv.addWidget(b)
            self.nav[name] = b
        sv.addStretch(1)
        lang_btn = QPushButton(f"{FLAGS[translator.lang]}  {LANGUAGES[translator.lang]} ▾")
        lang_btn.setObjectName("LangButton")
        menu = QMenu(lang_btn)
        for code in LANGUAGES:
            act = menu.addAction(f"{FLAGS[code]}  {LANGUAGES[code]}")
            act.triggered.connect(lambda _=False, c=code: self.set_language(c))
        lang_btn.setMenu(menu)
        sv.addWidget(lang_btn)
        sv.addWidget(label(f"v{__version__} · {tr('app.no_telemetry')}", "BrandSub"))
        h.addWidget(side)

        self.stack = QStackedWidget()
        h.addWidget(self.stack, 1)
        self.pages = {
            "dashboard": DashboardPage(self.state),
            "assessment": AssessmentPage(self.state),
            "identification": IdentificationPage(self.state),
            "options": OptionsPage(self.state),
            "verification": VerificationPage(self.state),
            "recovery": RecoveryPage(self.state),
            "results": ResultsPage(self.state),
        }
        for p in self.pages.values():
            self.stack.addWidget(p)
        pg = self.pages
        pg["dashboard"].go_to.connect(self.go)
        pg["dashboard"].check_catalog.connect(self.check_catalog)
        pg["assessment"].finished.connect(lambda: self.go("identification"))
        pg["identification"].finished.connect(lambda: self.go("options"))
        pg["identification"].go_back.connect(lambda: self.go("assessment"))
        pg["options"].finished.connect(lambda: self.go("verification"))
        pg["options"].go_back.connect(lambda: self.go("assessment"))
        pg["options"].export_requested.connect(lambda: self.go("results"))
        pg["options"].check_catalog.connect(self.check_catalog)
        pg["verification"].finished.connect(lambda: self.go("recovery"))
        pg["verification"].go_back.connect(lambda: self.go("options"))
        pg["recovery"].finished.connect(lambda: self.go("results"))
        self.setCentralWidget(root)
        self.go(start)

    def current_page_name(self) -> str:
        w = self.stack.currentWidget()
        return next((n for n, p in self.pages.items() if p is w), "dashboard")

    def go(self, name: str) -> None:
        page = self.pages[name]
        page.refresh()
        self.stack.setCurrentWidget(page)
        self.nav[name].setChecked(True)
        self._update_nav()

    def _update_nav(self) -> None:
        for i, name in enumerate(PAGES[1:], start=1):
            done = self.state.step_done(name)
            self.nav[name].setText(f"✓   {tr('nav.' + name)}" if done else f"{i}.  {tr('nav.' + name)}")

    def _on_state_changed(self, what: str) -> None:
        if what == "scan":
            self.state.d.identification = None
            if not self.state.d.user_selected_family:
                self.state.d.chosen = None
            self.state.d.selected_solution_id = None
        self._update_nav()

    # ------------------------------------------------------------------
    def check_catalog(self) -> None:
        if not confirm(self, tr("catalog.check_updates"), tr("catalog.confirm_network")):
            return
        url = self.state.settings.catalog_update_url
        run_task(Task(update_catalog, self.state.catalog, url), self._catalog_done, self._catalog_failed)

    def _catalog_done(self, res) -> None:
        self.state.settings.last_catalog_check = datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            self.state.settings.save()
        except OSError:
            pass
        if res.status == "updated":
            self.state.catalog = load_catalog()
            info(self, tr("catalog.updated", version=res.new_version))
            self.build(self.current_page_name())
        elif res.status == "up_to_date":
            info(self, tr("catalog.up_to_date"))
        else:
            error(self, tr(res.key), res.detail)

    def _catalog_failed(self, exc) -> None:
        error(self, tr("catalog.err.network"), type(exc).__name__)
