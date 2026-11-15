"""Shared application state (survives language changes)."""
from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal

from ..analysis.scanner import ScanOutcome
from ..catalog.catalog import Catalog
from ..core.models import Candidate, IdentificationResult, RecoverySession, VerificationReport
from ..core.settings import Settings
from ..identification.rules import RuleSet

STEPS = ("assessment", "identification", "options", "verification", "recovery", "results")


@dataclass
class _Data:
    directories: list[str] = field(default_factory=list)
    scan: ScanOutcome | None = None
    identification: IdentificationResult | None = None
    chosen: Candidate | None = None          # family the user works on
    user_selected_family: bool = False
    selected_solution_id: str | None = None
    downloaded_file: str | None = None
    download_url: str | None = None
    verifications: list[VerificationReport] = field(default_factory=list)
    recovery: RecoverySession = field(default_factory=RecoverySession)
    user_problems: list[str] = field(default_factory=list)
    reports_exported: bool = False


class AppState(QObject):
    changed = Signal(str)   # name of the part that changed

    def __init__(self, settings: Settings, rules: RuleSet, catalog: Catalog) -> None:
        super().__init__()
        self.settings = settings
        self.rules = rules
        self.catalog = catalog
        self.d = _Data()

    def notify(self, what: str) -> None:
        self.changed.emit(what)

    # -- derived ----------------------------------------------------------
    def solutions(self) -> list[dict]:
        c = self.d.chosen
        return self.catalog.solutions_for(c.catalog_ids) if c and c.catalog_ids else []

    def selected_solution(self) -> dict | None:
        sid = self.d.selected_solution_id
        return self.catalog.solution(sid) if sid else None

    def no_decryptor(self) -> bool:
        return self.d.identification is not None and not self.solutions()

    def step_done(self, step: str) -> bool:
        d = self.d
        return {
            "assessment": d.scan is not None,
            "identification": d.identification is not None,
            "options": d.selected_solution_id is not None or (d.identification is not None and self.no_decryptor()),
            "verification": bool(d.verifications),
            "recovery": any(t.status != "pending" for t in d.recovery.test_files),
            "results": d.reports_exported,
        }[step]
