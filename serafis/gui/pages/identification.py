from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QTableWidget

from ...core.models import Candidate
from ...identification.engine import Identifier, YaraEngine, RuleEngine
from ...core.paths import app_data_dir
from ...localization.i18n import tr
from ..state import AppState
from ..style import LEVEL_COLORS
from ..widgets import Card, Page, button, clear_layout, confirm, label, open_url_confirmed, row
from .assessment import fill_table

ID_RANSOMWARE = "https://id-ransomware.malwarehunterteam.com/"
CRYPTO_SHERIFF = "https://www.nomoreransom.org/crypto-sheriff.php"


def run_identification(state: AppState):
    outcome = state.d.scan
    engines = [RuleEngine(state.rules), YaraEngine(app_data_dir() / "yara")]
    return Identifier(state.rules, engines).identify(outcome.result, outcome.note_texts)


class IdentificationPage(Page):
    step_index = 2
    finished = Signal()
    go_back = Signal()

    def __init__(self, state: AppState) -> None:
        super().__init__(tr("ident.title"), tr("ident.intro"))
        self.state = state
        self.empty = Card(None, "Info")
        self.empty.add(label(tr("ident.need_scan")))
        back = button(tr("ident.go_assessment"))
        back.clicked.connect(self.go_back.emit)
        self.empty.add(row(back))
        self.add(self.empty)

        self.best = Card(tr("ident.best"))
        self.add(self.best)
        self.alts_card = Card(tr("ident.alternatives"))
        self.alts = QTableWidget()
        self.alts_card.add(self.alts)
        self.add(self.alts_card)
        self.missing = Card(tr("ident.missing_title"), "Warning")
        self.add(self.missing)

        manual = Card(tr("ident.manual.title"))
        manual.add(label(tr("ident.manual.help"), "Muted"))
        self.combo = QComboBox()
        self.combo.addItem(tr("ident.manual.placeholder"), None)
        for fid, f in sorted(state.catalog.families.items(), key=lambda kv: kv[1]["name"].lower()):
            self.combo.addItem(f["name"], fid)
        use = button(tr("ident.manual.use"))
        use.clicked.connect(self.use_manual)
        manual.add(row(self.combo, use))
        ext = button(tr("ident.external.idr"))
        ext.clicked.connect(lambda: open_url_confirmed(self, ID_RANSOMWARE))
        sheriff = button(tr("ident.external.sheriff"))
        sheriff.clicked.connect(lambda: open_url_confirmed(self, CRYPTO_SHERIFF))
        manual.add(label(tr("ident.external.help"), "Muted"))
        manual.add(row(ext, sheriff))
        self.add(manual)

        self.next_btn = button(tr("ident.next"), primary=True)
        self.next_btn.clicked.connect(self.finished.emit)
        self.add(row(self.next_btn))
        self.add(label(tr("ident.disclaimer"), "Muted"))
        self.finish()
        self.refresh()

    def ensure_identified(self) -> None:
        if self.state.d.scan is not None and self.state.d.identification is None:
            res = run_identification(self.state)
            self.state.d.identification = res
            if not self.state.d.user_selected_family:
                self.state.d.chosen = res.best
            self.state.notify("identification")

    def use_manual(self) -> None:
        fid = self.combo.currentData()
        if not fid:
            return
        if not confirm(self, tr("ident.manual.title"), tr("ident.manual.confirm")):
            return
        name = self.state.catalog.family_name(fid)
        cand = Candidate(family_id=fid, family_name=name, score=0.0, level="user", catalog_ids=[fid], engine="user")
        self.state.d.chosen = cand
        self.state.d.user_selected_family = True
        self.state.d.selected_solution_id = None
        self.state.notify("identification")
        self.refresh()

    def refresh(self) -> None:
        self.ensure_identified()
        res = self.state.d.identification
        has = res is not None
        self.empty.setVisible(not has)
        for w in (self.best, self.alts_card, self.missing, self.next_btn):
            w.setVisible(has)
        if not has:
            return
        clear_layout(self.best.lay)
        best = self.state.d.chosen
        if best is None:
            self.best.add(label(tr("ident.best"), "CardTitle"))
            self.best.add(label(tr("ident.none")))
        else:
            self.best.add(label(tr("ident.chosen_user") if best.level == "user" else tr("ident.best"), "CardTitle"))
            self.best.add(label(best.family_name, "PageTitle"))
            color = LEVEL_COLORS.get(best.level, "#173a6b")
            lv = label(tr("level." + best.level) + (f"  ·  {round(best.score * 100)}%" if best.level != "user" else ""))
            lv.setStyleSheet(f"color:{color}; font-weight:700; font-size:12pt;")
            self.best.add(lv)
            self.best.add(label(tr("level." + best.level + ".explain"), "Muted"))
            self.best.add(label(tr("ident.variant") + ": " + (best.variant or tr("common.unknown"))))
            if best.evidence:
                self.best.add(label(tr("ident.evidence"), "CardTitle"))
                for e in best.evidence:
                    self.best.add(label(f"• {tr('evidence.' + e.kind)}: {e.value}  ({tr('ident.weight')} {e.weight:.2f})"))
        alts = [c for c in res.candidates if best is None or c.family_id != best.family_id]
        self.alts_card.setVisible(bool(alts))
        fill_table(self.alts, [tr("report.family"), tr("report.confidence"), tr("report.evidence")],
                   [(c.family_name, f"{tr('level.' + c.level)} ({round(c.score * 100)}%)", "; ".join(e.value for e in c.evidence[:3])) for c in alts])
        clear_layout(self.missing.lay)
        self.missing.add(label(tr("ident.missing_title"), "CardTitle"))
        for k in res.missing_information:
            self.missing.add(label("• " + tr(k)))
        if res.engines_unavailable:
            self.missing.add(label(tr("ident.engines_unavailable", engines=", ".join(res.engines_unavailable)), "Muted"))
