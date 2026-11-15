from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout

from ...localization.i18n import tr, translator
from ..state import AppState
from ..widgets import Card, Page, button, clear_layout, label, open_url_confirmed, row

NO_DECRYPTOR_RECS = ("keep_encrypted", "keep_notes", "no_delete", "isolate", "professional", "export_tip", "recheck", "no_promise")


class OptionsPage(Page):
    step_index = 3
    finished = Signal()
    go_back = Signal()
    export_requested = Signal()
    check_catalog = Signal()

    def __init__(self, state: AppState) -> None:
        super().__init__(tr("options.title"), tr("options.intro"))
        self.state = state
        self.container = QVBoxLayout()
        self.add(self.container)
        self.cat_info = label("", "Muted")
        upd = button(tr("catalog.check_updates"))
        upd.clicked.connect(self.check_catalog.emit)
        self.add(row(self.cat_info, upd))
        self.finish()
        self.refresh()

    def refresh(self) -> None:
        clear_layout(self.container)
        c = self.state.catalog
        self.cat_info.setText(tr("options.catalog_info", version=c.version, date=c.generated_at[:10]))
        d = self.state.d
        if d.identification is None:
            card = Card(None, "Info")
            card.add(label(tr("options.need_identification")))
            b = button(tr("ident.go_assessment"))
            b.clicked.connect(self.go_back.emit)
            card.add(row(b))
            self.container.addWidget(card)
            return
        chosen = d.chosen
        sols = self.state.solutions()
        if chosen:
            self.container.addWidget(label(tr("options.for_family", family=chosen.family_name), "CardTitle"))
        if not sols:
            self.container.addWidget(self._no_decryptor())
            return
        self.container.addWidget(label(tr("options.found", n=len(sols)), "PageIntro"))
        warn = Card(None, "Warning")
        warn.add(label(tr("options.not_guaranteed")))
        self.container.addWidget(warn)
        for s in sols:
            self.container.addWidget(self._solution_card(s))

    def _solution_card(self, s: dict) -> Card:
        selected = self.state.d.selected_solution_id == s["id"]
        card = Card(("✔ " if selected else "") + s["name"], "Success" if selected else "Card")
        card.add(label(tr("options.vendor") + ": " + s["vendor"]))
        card.add(label(tr("options.status") + ": " + tr("status." + s["verification_status"])))
        card.add(label(tr("options.version") + ": " + (s.get("version") or tr("options.not_published"))))
        card.add(label("SHA-256: " + (s.get("sha256") or tr("options.sha_not_published")), "Muted"))
        sig = s.get("signature", {})
        sig_txt = tr("options.sig." + sig.get("type", "unknown"))
        if sig.get("expected_signer_keywords"):
            sig_txt += " — " + tr("options.sig.expected", names=", ".join(sig["expected_signer_keywords"]))
        card.add(label(tr("options.signature") + ": " + sig_txt, "Muted"))
        comp = s.get("compatibility", {})
        card.add(label(tr("options.compat") + ": " + translator.i18n(comp.get("description"))))
        if comp.get("variants"):
            card.add(label(tr("options.variants") + ": " + ", ".join(comp["variants"])))
        if comp.get("os"):
            card.add(label(tr("options.os") + ": " + ", ".join(comp["os"])))
        for lim in s.get("limitations", []):
            card.add(label("⚠ " + translator.i18n(lim)))
        card.add(label(tr("options.official_page") + ": " + s["official_page"], "Muted"))
        card.add(label(tr("options.download_url") + ": " + (s.get("download_url") or "—"), "Muted"))
        card.add(label(tr("options.sources") + ": " + ", ".join(s.get("sources", [])), "Muted"))
        card.add(label(tr("options.last_verified") + ": " + s["last_verified"], "Muted"))
        page = button(tr("options.open_page"))
        page.clicked.connect(lambda: open_url_confirmed(self, s["official_page"]))
        btns = [page]
        if s.get("howto_url"):
            how = button(tr("options.open_howto"))
            how.clicked.connect(lambda: open_url_confirmed(self, s["howto_url"]))
            btns.append(how)
        sel = button(tr("options.select"), primary=True)
        sel.clicked.connect(lambda: self._select(s["id"]))
        btns.append(sel)
        card.add(row(*btns))
        return card

    def _select(self, sid: str) -> None:
        self.state.d.selected_solution_id = sid
        self.state.d.downloaded_file = None
        self.state.notify("solution")
        self.finished.emit()

    def _no_decryptor(self) -> Card:
        card = Card(None, "Warning")
        card.add(label(tr("nodecryptor.title"), "NoDecryptor"))
        card.add(label(tr("nodecryptor.intro")))
        for k in NO_DECRYPTOR_RECS:
            card.add(label("• " + tr("nodecryptor." + k)))
        exp = button(tr("nodecryptor.export"), primary=True)
        exp.clicked.connect(self.export_requested.emit)
        rc = button(tr("catalog.check_updates"))
        rc.clicked.connect(self.check_catalog.emit)
        card.add(row(exp, rc))
        return card
