from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QFileDialog, QPlainTextEdit

from ...localization.i18n import tr
from ...reporting.report import ReportData, build_report, default_recommendations, export_html, export_json, export_pdf
from ..state import AppState
from ..widgets import Card, Page, button, error, info, label, row


def make_report(state: AppState) -> dict:
    d = state.d
    ident = d.identification.to_dict() if d.identification else None
    if ident is not None and d.chosen is not None and d.user_selected_family:
        ident["user_selected_family"] = d.chosen.family_name
    c = state.catalog
    problems = list(d.user_problems) + list(d.recovery.errors)
    if d.scan:
        problems += [f"scan: {e}" for e in d.scan.result.errors[:20]]
    identified = bool(d.chosen and d.chosen.level in ("strong", "probable", "user"))
    data = ReportData(
        language=state.settings.language or "en",
        scan=asdict(d.scan.result) if d.scan else None,
        identification=ident,
        solutions=state.solutions(),
        no_decryptor=state.no_decryptor(),
        verifications=[v.to_dict() for v in d.verifications],
        recovery=d.recovery.to_dict(),
        catalog={"version": c.version, "origin": c.origin, "sha256": c.sha256, "generated_at": c.generated_at},
        problems=problems,
        recommendations=default_recommendations(state.no_decryptor() or not d.identification, identified),
        include_file_names=state.settings.include_file_names_in_report,
    )
    return build_report(data)


class ResultsPage(Page):
    step_index = 6

    def __init__(self, state: AppState) -> None:
        super().__init__(tr("results.title"), tr("results.intro"))
        self.state = state
        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setMinimumHeight(260)
        sc = Card(tr("results.summary"))
        sc.add(self.summary)
        self.add(sc)

        ex = Card(tr("results.export.title"))
        ex.add(label(tr("results.export.privacy"), "Muted"))
        self.names_cb = QCheckBox(tr("results.export.include_names"))
        self.names_cb.setChecked(state.settings.include_file_names_in_report)
        self.names_cb.toggled.connect(self._names_toggled)
        ex.add(self.names_cb)
        bj = button(tr("results.export.json"), primary=True)
        bh = button(tr("results.export.html"), primary=True)
        bp = button(tr("results.export.pdf"), primary=True)
        bj.clicked.connect(lambda: self.export("json"))
        bh.clicked.connect(lambda: self.export("html"))
        bp.clicked.connect(lambda: self.export("pdf"))
        ex.add(row(bj, bh, bp))
        self.add(ex)
        self.finish()
        self.refresh()

    def _names_toggled(self, v: bool) -> None:
        self.state.settings.include_file_names_in_report = v
        try:
            self.state.settings.save()
        except OSError:
            pass

    def export(self, kind: str, path: str | None = None) -> Path | None:
        report = make_report(self.state)
        if path is None:
            default = f"Serafis_report_{datetime.now():%Y%m%d_%H%M}.{kind}"
            filt = {"json": "JSON (*.json)", "html": "HTML (*.html)", "pdf": "PDF (*.pdf)"}[kind]
            path, _ = QFileDialog.getSaveFileName(self, tr("results.export.title"), str(Path.home() / default), filt)
            if not path:
                return None
        try:
            out = {"json": lambda: export_json(report, path),
                   "html": lambda: export_html(report, path, tr),
                   "pdf": lambda: export_pdf(report, path, tr)}[kind]()
        except OSError as exc:
            error(self, tr("results.export.error"), type(exc).__name__)
            return None
        self.state.d.reports_exported = True
        self.state.notify("results")
        if path is not None and not getattr(self, "_silent", False):
            info(self, tr("results.export.done", path=str(out)))
        return out

    def refresh(self) -> None:
        d = self.state.d
        lines = [tr("results.date") + ": " + datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")]
        if d.scan:
            r = d.scan.result
            lines.append(tr("report.directories") + ": " + "; ".join(r.directories))
            lines.append(tr("results.files", total=r.total_files, suspicious=r.suspicious_files, notes=len(r.ransom_notes)))
        else:
            lines.append(tr("results.no_scan"))
        if d.chosen:
            lv = tr("level." + d.chosen.level)
            lines.append(tr("results.family", family=d.chosen.family_name, level=lv, variant=d.chosen.variant or tr("common.unknown")))
        elif d.identification:
            lines.append(tr("ident.none"))
        sols = self.state.solutions()
        if d.identification is not None:
            if sols:
                lines.append(tr("results.solutions", n=len(sols)))
                for s in sols:
                    lines.append(f"  • {s['name']} — {s['vendor']} — {s['official_page']}")
            else:
                lines.append("⚠ " + tr("nodecryptor.title"))
        for v in d.verifications:
            st = tr("verify.verdict." + ("fail" if v.has_failure else ("ok" if v.strong_pass else "partial")))
            lines.append(f"{tr('report.section.verification')}: {v.file_name} — {st}")
        for t in d.recovery.test_files:
            lines.append(f"{tr('report.section.tests')}: {t.original_name} — {tr('test.' + t.status)}")
        lines.append("")
        lines.append(tr("report.section.recommendations") + ":")
        identified = bool(d.chosen and d.chosen.level in ("strong", "probable", "user"))
        for k in default_recommendations(self.state.no_decryptor() or not d.identification, identified):
            lines.append("  • " + tr(k))
        self.summary.setPlainText("\n".join(lines))
